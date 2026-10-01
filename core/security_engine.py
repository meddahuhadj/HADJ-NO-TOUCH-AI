import time
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any
from core.event_bus import EventBus, EventType


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityEngine:
    """Evaluates command risks and enforces confirmation gates for safety."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SecurityEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, event_bus: Optional[EventBus] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.event_bus = event_bus or EventBus()
        self.pending_command: Optional[Dict[str, Any]] = None
        self.pending_timestamp: float = 0.0
        self.timeout_seconds: float = 10.0
        self.is_emergency_stopped: bool = False

        # Intent risk mappings
        self._risk_map: Dict[str, RiskLevel] = {
            "LAUNCH_APP": RiskLevel.LOW,
            "SWITCH_APP": RiskLevel.LOW,
            "CLOSE_WINDOW": RiskLevel.MEDIUM,
            "MINIMIZE_WINDOW": RiskLevel.LOW,
            "MAXIMIZE_WINDOW": RiskLevel.LOW,
            "RESTORE_WINDOW": RiskLevel.LOW,
            "VOLUME_UP": RiskLevel.LOW,
            "VOLUME_DOWN": RiskLevel.LOW,
            "VOLUME_MUTE": RiskLevel.LOW,
            "MEDIA_PLAY_PAUSE": RiskLevel.LOW,
            "MEDIA_NEXT": RiskLevel.LOW,
            "MEDIA_PREVIOUS": RiskLevel.LOW,
            "BRIGHTNESS_UP": RiskLevel.LOW,
            "BRIGHTNESS_DOWN": RiskLevel.LOW,
            "SCREENSHOT": RiskLevel.LOW,
            "SCROLL_UP": RiskLevel.LOW,
            "SCROLL_DOWN": RiskLevel.LOW,
            "NAVIGATE_BACK": RiskLevel.LOW,
            "NAVIGATE_FORWARD": RiskLevel.LOW,
            "BROWSER_NEW_TAB": RiskLevel.LOW,
            "BROWSER_CLOSE_TAB": RiskLevel.LOW,
            "BROWSER_SEARCH": RiskLevel.LOW,
            "CLIPBOARD_COPY": RiskLevel.LOW,
            "CLIPBOARD_PASTE": RiskLevel.LOW,
            "CLIPBOARD_CUT": RiskLevel.LOW,
            "SELECT_ALL": RiskLevel.LOW,
            "UNDO": RiskLevel.LOW,
            "DICTATION": RiskLevel.LOW,
            "VIRTUAL_KEYBOARD": RiskLevel.LOW,
            "OPEN_FOLDER": RiskLevel.LOW,
            "CREATE_FOLDER": RiskLevel.MEDIUM,
            "RENAME_FILE": RiskLevel.MEDIUM,
            "DELETE_FILE": RiskLevel.MEDIUM,
            "DELETE_FOLDER": RiskLevel.HIGH,
            "EMPTY_RECYCLE_BIN": RiskLevel.HIGH,
            "SYSTEM_LOCK": RiskLevel.LOW,
            "SYSTEM_RESTART": RiskLevel.HIGH,
            "SYSTEM_SHUTDOWN": RiskLevel.HIGH,
            "SYSTEM_SLEEP": RiskLevel.HIGH,
            "FORMAT_DISK": RiskLevel.CRITICAL,
            "EXECUTE_MACRO": RiskLevel.LOW,
        }

    def evaluate_risk(self, intent_name: str) -> RiskLevel:
        return self._risk_map.get(intent_name, RiskLevel.MEDIUM)

    def requires_confirmation(self, intent_name: str) -> bool:
        if self.is_emergency_stopped:
            return True
        risk = self.evaluate_risk(intent_name)
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True
        return False

    def request_confirmation(
        self,
        intent_name: str,
        command_text: str,
        action_fn: Callable[[], Any],
        on_cancel: Optional[Callable[[], Any]] = None
    ) -> bool:
        """Starts a confirmation countdown for a risky action."""
        if self.is_emergency_stopped:
            print("[SecurityEngine] Emergency stop is active. Action blocked.")
            return False

        risk = self.evaluate_risk(intent_name)
        self.pending_command = {
            "intent": intent_name,
            "command": command_text,
            "risk": risk.value,
            "action": action_fn,
            "cancel": on_cancel,
            "timestamp": time.time()
        }
        self.pending_timestamp = time.time()

        self.event_bus.publish(EventType.SECURITY_CONFIRM_REQUEST, {
            "intent": intent_name,
            "command": command_text,
            "risk": risk.value,
            "timeout": self.timeout_seconds
        })
        return True

    def is_waiting_confirmation(self) -> bool:
        if self.pending_command is None:
            return False
        if time.time() - self.pending_timestamp > self.timeout_seconds:
            self.cancel_pending("TIMEOUT")
            return False
        return True

    def confirm_pending(self, source: str = "VOICE") -> bool:
        """Confirms and executes the pending risky action."""
        if not self.is_waiting_confirmation():
            return False

        cmd = self.pending_command
        self.pending_command = None
        self.event_bus.publish(EventType.SECURITY_CONFIRMED, {
            "intent": cmd["intent"],
            "command": cmd["command"],
            "source": source
        })

        try:
            if callable(cmd.get("action")):
                cmd["action"]()
            return True
        except Exception as e:
            print(f"[SecurityEngine] Error executing confirmed action: {e}")
            return False

    def cancel_pending(self, reason: str = "USER_REJECT") -> None:
        """Cancels any pending confirmation."""
        if self.pending_command:
            cmd = self.pending_command
            self.pending_command = None
            if callable(cmd.get("cancel")):
                try:
                    cmd["cancel"]()
                except Exception:
                    pass
            self.event_bus.publish(EventType.SECURITY_REJECTED, {
                "intent": cmd["intent"],
                "reason": reason
            })

    def trigger_emergency_stop(self, reason: str = "USER_TRIGGERED") -> None:
        """Halts all automation immediately."""
        self.is_emergency_stopped = True
        self.cancel_pending("EMERGENCY_STOP")
        self.event_bus.publish(EventType.EMERGENCY_STOP, {"reason": reason})
        try:
            from core.qt_bridge import QtBridge
            QtBridge().emergency_stop.emit(reason)
        except Exception:
            pass
        print(f"[SecurityEngine] [EMERGENCY STOP ACTIVATED]: {reason}")

    def reset_emergency_stop(self) -> None:
        """Restores normal operation."""
        self.is_emergency_stopped = False
        self.event_bus.publish(EventType.EMERGENCY_RESTORED, {})
        try:
            from core.qt_bridge import QtBridge
            QtBridge().emergency_stop.emit("RESTORED")
        except Exception:
            pass
        print("[SecurityEngine] Emergency stop reset. Normal operations resumed.")
