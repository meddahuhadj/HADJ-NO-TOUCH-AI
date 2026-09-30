import sys
import os

# Auto-detect and re-exec with Python 3.12 if current Python is not Python 3.12
py312 = r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if os.path.exists(py312) and sys.executable.lower() != py312.lower():
    import subprocess
    sys.exit(subprocess.call([py312] + sys.argv))

import json
import time
import subprocess
import http.server
import socketserver
import psutil
from typing import Dict, Any

PORT = 8000
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "config", "auth_token.secret")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PY_EXE = r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if not os.path.exists(PY_EXE):
    PY_EXE = sys.executable

# Lazy instances
_win_control = None
_app_launcher = None
_orchestrator = None


def get_win_control():
    global _win_control
    if _win_control is None:
        try:
            from automation.windows_control import WindowsControlEngine
            _win_control = WindowsControlEngine()
        except Exception as e:
            print(f"[WebServer] WinControl init notice: {e}")
    return _win_control


def get_app_launcher():
    global _app_launcher
    if _app_launcher is None:
        try:
            from automation.app_launcher import AppLauncher
            _app_launcher = AppLauncher()
        except Exception as e:
            print(f"[WebServer] AppLauncher init notice: {e}")
    return _app_launcher


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        try:
            from core.command_orchestrator import CommandOrchestrator
            _orchestrator = CommandOrchestrator()
        except Exception as e:
            print(f"[WebServer] Orchestrator init notice: {e}")
    return _orchestrator


def get_auth_token():
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def is_desktop_running():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            if any('main.py' in str(arg) for arg in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


class CustomHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Hadj-Token, Authorization")
        self.end_headers()

    def do_HEAD(self):
        if self.path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/api/launch":
            self._handle_launch()
        elif clean_path == "/api/status":
            self._handle_status()
        elif clean_path == "/api/token":
            self._handle_token()
        elif clean_path == "/api/calibrate":
            self._handle_calibrate()
        else:
            super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/api/launch":
            self._handle_launch()
        elif clean_path == "/api/action":
            self._handle_action()
        elif clean_path == "/api/command":
            self._handle_command()
        elif clean_path == "/api/calibrate":
            self._handle_calibrate()
        else:
            super().do_POST()

    def _read_json_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length)
                return json.loads(raw_body.decode("utf-8"))
        except Exception:
            pass
        return {}

    def _send_json(self, status: int, data: Dict[str, Any]):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Hadj-Token, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _handle_launch(self):
        running = is_desktop_running()
        if running:
            self._send_json(200, {
                "success": True,
                "alreadyRunning": True,
                "message": "HADJ NO-TOUCH AI est déjà actif et en cours d'exécution sur votre PC."
            })
        else:
            try:
                main_path = os.path.join(PROJECT_ROOT, "main.py")
                if sys.platform == "win32":
                    subprocess.Popen(f'start "" "{PY_EXE}" "{main_path}"', shell=True, cwd=PROJECT_ROOT)
                else:
                    subprocess.Popen([PY_EXE, main_path], cwd=PROJECT_ROOT)
                self._send_json(200, {
                    "success": True,
                    "alreadyRunning": False,
                    "message": "Lancement de HADJ NO-TOUCH AI en cours..."
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

    def _handle_status(self):
        running = is_desktop_running()
        cpu_usage = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        data = {
            "app": "HADJ NO-TOUCH OFFLINE AI",
            "version": "1.0.0",
            "running": running,
            "status": "RUNNING" if running else "STANDBY",
            "telemetry": {
                "cpu_percent": cpu_usage,
                "memory_percent": ram.percent,
                "camera_fps": 30.0 if running else 0.0,
                "latency_ms": 32.5 if running else 0.0,
                "battery_percent": None
            },
            "companionPort": 8766
        }
        self._send_json(200, data)

    def _handle_token(self):
        token = get_auth_token()
        self._send_json(200, {"token": token})

    def _handle_calibrate(self):
        try:
            from core.auto_calibration import perform_one_click_auto_calibration
            res = perform_one_click_auto_calibration()
            self._send_json(200, res)
        except Exception as e:
            self._send_json(500, {"success": False, "error": str(e)})

    def _handle_command(self):
        body = self._read_json_body()
        cmd_text = body.get("command", "")
        if not cmd_text:
            self._send_json(400, {"error": "Missing 'command' parameter"})
            return

        orchestrator = get_orchestrator()
        if orchestrator:
            res = orchestrator.execute_command_text(cmd_text, source="WEB_CENTRAL")
            self._send_json(200, {"success": True, "result": res})
        else:
            self._send_json(500, {"error": "Command orchestrator unavailable"})

    def _handle_action(self):
        body = self._read_json_body()
        action = body.get("action", "")
        win = get_win_control()
        launcher = get_app_launcher()

        if not win:
            self._send_json(500, {"error": "Windows automation engine unavailable"})
            return

        try:
            if action == "volume_up":
                win.volume_up(step=body.get("step", 6))
            elif action == "volume_down":
                win.volume_down(step=body.get("step", 6))
            elif action in ("volume_mute", "mute"):
                win.volume_mute()
            elif action == "media_play_pause":
                win.media_play_pause()
            elif action == "media_next":
                win.media_next()
            elif action == "media_prev":
                win.media_prev()
            elif action == "brightness_up":
                win.brightness_up(step=body.get("step", 10))
            elif action == "brightness_down":
                win.brightness_down(step=body.get("step", 10))
            elif action == "show_desktop":
                win.show_desktop()
            elif action == "task_view":
                win.open_task_view()
            elif action in ("open_task_manager", "task_manager"):
                win.open_task_manager()
            elif action in ("open_explorer", "explorer"):
                win.open_explorer()
            elif action == "lock_pc":
                win.lock_pc()
            elif action == "take_screenshot":
                path = win.take_screenshot()
                self._send_json(200, {"success": True, "action": action, "path": path})
                return
            elif action == "snap_left":
                win.snap_window_left()
            elif action == "snap_right":
                win.snap_window_right()
            elif action == "maximize":
                win.maximize_window()
            elif action == "minimize":
                win.minimize_window()
            elif action == "close_window":
                win.close_current_window()
            elif action == "alt_tab":
                win.switch_app()
            elif action == "mouse_click":
                btn = body.get("button", "left")
                if btn == "double":
                    win.double_click()
                elif btn == "right":
                    win.right_click()
                else:
                    win.click(button=btn)
            elif action == "mouse_move":
                dx = int(body.get("dx", 0))
                dy = int(body.get("dy", 0))
                cur_x, cur_y = win.get_cursor_position()
                win.move_mouse(cur_x + dx, cur_y + dy)
            elif action == "mouse_scroll":
                amount = int(body.get("amount", -120))
                win.scroll(amount)
            elif action == "type_text":
                text = body.get("text", "")
                if text:
                    win.type_text(text)
            elif action == "press_key":
                key = body.get("key", "")
                if key:
                    win.press_key(key)
            elif action == "launch_app":
                app = body.get("app", "")
                if app and launcher:
                    launcher.launch(app)
            elif action == "auto_calibrate":
                from core.auto_calibration import perform_one_click_auto_calibration
                res = perform_one_click_auto_calibration()
                self._send_json(200, res)
                return
            else:
                self._send_json(400, {"success": False, "error": f"Unknown action: {action}"})
                return

            self._send_json(200, {"success": True, "action": action})
        except Exception as e:
            self._send_json(500, {"success": False, "error": str(e)})


def run_server():
    os.chdir(WEB_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), CustomHandler) as httpd:
        print(f"[HADJ Web Server] Serving web interface & remote control at http://127.0.0.1:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
