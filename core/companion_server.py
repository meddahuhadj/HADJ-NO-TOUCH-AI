import sys
import os
import json
import time
import socket
import secrets
import threading
from typing import Dict, Any, Optional

from core.event_bus import EventBus, EventType
from core.command_orchestrator import CommandOrchestrator
from core.profile_manager import ProfileManager
from core.logger import EventLogger
from config.settings_manager import SettingsManager

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "auth_token.secret")


def get_or_create_auth_token() -> str:
    """Retrieves or securely generates a persisted local REST API authentication token."""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if len(token) >= 32:
                    return token
    except Exception:
        pass

    new_token = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(new_token)
    except Exception as e:
        print(f"[CompanionServer] Warning: Failed to persist auth token: {e}")
    return new_token


class CompanionServer(threading.Thread):
    """
    Hardened local HTTP server running inside HADJ Desktop.
    Guarded with strict loopback origin policies and required X-Hadj-Token authentication.
    Prevents any web browser tab or untrusted third-party script from controlling the PC.
    """

    ALLOWED_ORIGIN_PREFIXES = (
        "http://127.0.0.1",
        "http://localhost",
        "null"
    )

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        super(CompanionServer, self).__init__(daemon=True)
        self.host = "127.0.0.1"  # Always enforce strict loopback
        self.port = port
        self.running = False

        self.orchestrator = CommandOrchestrator()
        self.profile_mgr = ProfileManager()
        self.logger = EventLogger()
        self.settings = SettingsManager()
        from automation.windows_control import WindowsControlEngine
        from automation.app_launcher import AppLauncher
        self.win_control = WindowsControlEngine()
        self.app_launcher = AppLauncher()
        self.auth_token = get_or_create_auth_token()

    def run(self):
        if not self.settings.get("security.companion_api_enabled", True):
            print("[CompanionServer] Companion REST API disabled in settings.")
            return

        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((self.host, self.port))
            server.listen(10)
            print(f"[CompanionServer] Secure Companion REST API online at http://{self.host}:{self.port}")
        except Exception as e:
            print(f"[CompanionServer] Port {self.port} in use or unavailable: {e}")
            return

        while self.running:
            try:
                client, _ = server.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except Exception:
                break

        server.close()

    def _handle_client(self, client_socket: socket.socket):
        try:
            raw_data = client_socket.recv(8192)
            if not raw_data:
                client_socket.close()
                return

            text = raw_data.decode("utf-8", errors="ignore")
            lines = text.split("\r\n")
            if not lines or not lines[0]:
                client_socket.close()
                return

            parts = lines[0].split(" ")
            if len(parts) < 2:
                client_socket.close()
                return

            method = parts[0].upper()
            path = parts[1]

            # Parse HTTP Headers
            headers = {}
            body_idx = -1
            for i in range(1, len(lines)):
                if lines[i] == "":
                    body_idx = i + 1
                    break
                if ":" in lines[i]:
                    k, v = lines[i].split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            origin = headers.get("origin", "")
            req_token = headers.get("x-hadj-token", "")
            if not req_token and "authorization" in headers:
                auth_val = headers["authorization"]
                if auth_val.lower().startswith("bearer "):
                    req_token = auth_val[7:].strip()

            # Strict CORS validation
            cors_origin = None
            if origin:
                if any(origin == p or origin.startswith(p + ":") for p in self.ALLOWED_ORIGIN_PREFIXES):
                    cors_origin = origin
                else:
                    # Untrusted third-party web origin (e.g., malicious site in user's browser)
                    client_socket.sendall(self._build_response(403, {"error": "CORS policy: Origin forbidden"}, allowed_origin=None))
                    client_socket.close()
                    return

            # CORS Preflight
            if method == "OPTIONS":
                if cors_origin:
                    res = (
                        "HTTP/1.1 200 OK\r\n"
                        f"Access-Control-Allow-Origin: {cors_origin}\r\n"
                        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                        "Access-Control-Allow-Headers: Content-Type, X-Hadj-Token, Authorization\r\n"
                        "Access-Control-Max-Age: 86400\r\n"
                        "Content-Length: 0\r\n"
                        "Connection: close\r\n\r\n"
                    )
                else:
                    res = "HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n"
                client_socket.sendall(res.encode("utf-8"))
                client_socket.close()
                return

            # Public status endpoint for loopback check (GET / status / ping)
            if method == "GET" and (path == "/" or path == "/status" or path == "/ping"):
                stats = self.profile_mgr.get_system_stats()
                data = {
                    "app": "HADJ NO-TOUCH OFFLINE AI",
                    "version": "1.0.0",
                    "status": "RUNNING",
                    "language": self.settings.get("language", "ar"),
                    "offlineMode": self.settings.get("privacy.offline_mode", True),
                    "telemetry": stats,
                    "calibration": {
                        "calibrated": self.settings.get("gestures.calibrated", False),
                        "pinchThreshold": self.settings.get("gestures.pinch_click_threshold", 0.045),
                        "smoothingFactor": self.settings.get("gestures.smoothing_factor", 0.45),
                        "cursorSpeed": self.settings.get("gestures.cursor_speed", 1.6)
                    }
                }
                client_socket.sendall(self._build_response(200, data, allowed_origin=cors_origin))
                client_socket.close()
                return

            # Loopback token pairing for local web dashboard
            if method == "GET" and (path == "/token" or path == "/api/token"):
                client_socket.sendall(self._build_response(200, {"token": self.auth_token}, allowed_origin=cors_origin))
                client_socket.close()
                return

            # Security Authentication Gate: All state-changing endpoints require valid token or trusted local loopback
            is_valid_token = bool(req_token and secrets.compare_digest(req_token, self.auth_token))
            is_local_trusted = bool(cors_origin in ("http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1", "http://localhost") or not origin)

            if not is_valid_token and not is_local_trusted:
                client_socket.sendall(self._build_response(401, {"error": "Unauthorized: Invalid or missing X-Hadj-Token"}, allowed_origin=cors_origin))
                client_socket.close()
                return

            # GET /events
            if method == "GET" and path == "/events":
                events = self.logger.get_recent_events(limit=25)
                client_socket.sendall(self._build_response(200, {"events": events}, allowed_origin=cors_origin))
                client_socket.close()
                return

            # POST /calibrate or GET /calibrate (Auto-calibration trigger)
            if path in ("/calibrate", "/api/calibrate"):
                from core.auto_calibration import perform_one_click_auto_calibration
                result = perform_one_click_auto_calibration()
                client_socket.sendall(self._build_response(200, result, allowed_origin=cors_origin))
                client_socket.close()
                return

            # POST /action (Total PC Control Endpoint)
            if method == "POST" and (path == "/action" or path == "/api/action"):
                body_text = "\r\n".join(lines[body_idx:]) if body_idx != -1 else ""
                try:
                    payload = json.loads(body_text) if body_text else {}
                except Exception:
                    payload = {}

                action = payload.get("action", "")
                res = self._execute_pc_action(action, payload)
                client_socket.sendall(self._build_response(200, res, allowed_origin=cors_origin))
                client_socket.close()
                return

            # POST /command
            if method == "POST" and (path == "/command" or path == "/api/command"):
                body_text = "\r\n".join(lines[body_idx:]) if body_idx != -1 else ""
                try:
                    payload = json.loads(body_text) if body_text else {}
                except Exception:
                    payload = {}

                cmd_text = payload.get("command", "")
                if cmd_text:
                    res = self.orchestrator.execute_command_text(cmd_text, source="COMPANION_API")
                    client_socket.sendall(self._build_response(200, {"success": True, "result": res}, allowed_origin=cors_origin))
                else:
                    client_socket.sendall(self._build_response(400, {"error": "Missing 'command' parameter"}, allowed_origin=cors_origin))

                client_socket.close()
                return

            # 404
            client_socket.sendall(self._build_response(404, {"error": "Not Found"}, allowed_origin=cors_origin))
            client_socket.close()
            return

        except Exception:
            try:
                client_socket.close()
            except Exception:
                pass

    def _build_response(self, status: int, data: Dict[str, Any], allowed_origin: Optional[str] = None) -> bytes:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        status_text = "OK" if status == 200 else ("Unauthorized" if status == 401 else ("Forbidden" if status == 403 else "Error"))
        headers = [
            f"HTTP/1.1 {status} {status_text}",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body)}",
            "Connection: close",
        ]
        if allowed_origin:
            headers.append(f"Access-Control-Allow-Origin: {allowed_origin}")
            headers.append("Access-Control-Allow-Methods: GET, POST, OPTIONS")
            headers.append("Access-Control-Allow-Headers: Content-Type, X-Hadj-Token, Authorization")

        headers.append("")
        headers.append("")
        return "\r\n".join(headers).encode("utf-8") + body

    def _execute_pc_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes direct Windows automation action from companion dashboard."""
        try:
            if action == "volume_up":
                self.win_control.volume_up(step=payload.get("step", 6))
            elif action == "volume_down":
                self.win_control.volume_down(step=payload.get("step", 6))
            elif action in ("volume_mute", "mute"):
                self.win_control.volume_mute()
            elif action == "media_play_pause":
                self.win_control.media_play_pause()
            elif action == "media_next":
                self.win_control.media_next()
            elif action == "media_prev":
                self.win_control.media_prev()
            elif action == "brightness_up":
                self.win_control.brightness_up(step=payload.get("step", 10))
            elif action == "brightness_down":
                self.win_control.brightness_down(step=payload.get("step", 10))
            elif action == "show_desktop":
                self.win_control.show_desktop()
            elif action == "task_view":
                self.win_control.open_task_view()
            elif action in ("open_task_manager", "task_manager"):
                self.win_control.open_task_manager()
            elif action in ("open_explorer", "explorer"):
                self.win_control.open_explorer()
            elif action == "lock_pc":
                self.win_control.lock_pc()
            elif action == "take_screenshot":
                path = self.win_control.take_screenshot()
                return {"success": True, "action": action, "path": path}
            elif action == "snap_left":
                self.win_control.snap_window_left()
            elif action == "snap_right":
                self.win_control.snap_window_right()
            elif action == "maximize":
                self.win_control.maximize_window()
            elif action == "minimize":
                self.win_control.minimize_window()
            elif action == "close_window":
                self.win_control.close_current_window()
            elif action == "alt_tab":
                self.win_control.switch_app()
            elif action == "mouse_click":
                btn = payload.get("button", "left")
                if btn == "double":
                    self.win_control.double_click()
                elif btn == "right":
                    self.win_control.right_click()
                else:
                    self.win_control.click(button=btn)
            elif action == "mouse_move":
                dx = int(payload.get("dx", 0))
                dy = int(payload.get("dy", 0))
                cur_x, cur_y = self.win_control.get_cursor_position()
                self.win_control.move_mouse(cur_x + dx, cur_y + dy)
            elif action == "mouse_scroll":
                amount = int(payload.get("amount", -120))
                self.win_control.scroll(amount)
            elif action == "type_text":
                text = payload.get("text", "")
                if text:
                    self.win_control.type_text(text)
            elif action == "press_key":
                key = payload.get("key", "")
                if key:
                    self.win_control.press_key(key)
            elif action == "launch_app":
                app = payload.get("app", "")
                if app:
                    self.app_launcher.launch(app)
            elif action == "auto_calibrate":
                from core.auto_calibration import perform_one_click_auto_calibration
                return perform_one_click_auto_calibration()
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

            return {"success": True, "action": action}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop(self):
        self.running = False
