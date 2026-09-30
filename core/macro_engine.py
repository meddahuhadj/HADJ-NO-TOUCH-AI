import os
import json
import time
import threading
from typing import List, Dict, Any, Optional
from core.event_bus import EventBus, EventType
from core.security_engine import SecurityEngine

MACROS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "macros.json")


class MacroEngine:
    """Records, persists, and executes custom multi-step automation workflows."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MacroEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, event_bus: Optional[EventBus] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.event_bus = event_bus or EventBus()
        self.macros: Dict[str, List[Dict[str, Any]]] = {}
        self.is_recording: bool = False
        self.current_recording_name: Optional[str] = None
        self.recorded_steps: List[Dict[str, Any]] = []
        self._load_macros()

    def _load_macros(self) -> None:
        if os.path.exists(MACROS_FILE):
            try:
                with open(MACROS_FILE, "r", encoding="utf-8") as f:
                    self.macros = json.load(f)
            except Exception as e:
                print(f"[MacroEngine] Error loading macros: {e}")
                self.macros = {}
        else:
            # Seed default helpful macros
            self.macros = {
                "Morning Setup": [
                    {"action": "LAUNCH_APP", "target": "chrome", "delay": 1.0},
                    {"action": "LAUNCH_APP", "target": "notepad", "delay": 1.0},
                    {"action": "VOLUME_SET", "target": 50, "delay": 0.5}
                ],
                "Coding Setup": [
                    {"action": "LAUNCH_APP", "target": "code", "delay": 1.5},
                    {"action": "LAUNCH_APP", "target": "cmd", "delay": 1.0},
                    {"action": "BRIGHTNESS_SET", "target": 80, "delay": 0.5}
                ],
                "Relax Mode": [
                    {"action": "LAUNCH_APP", "target": "spotify", "delay": 1.0},
                    {"action": "VOLUME_SET", "target": 35, "delay": 0.5}
                ]
            }
            self.save_macros()

    def save_macros(self) -> bool:
        try:
            os.makedirs(os.path.dirname(MACROS_FILE), exist_ok=True)
            with open(MACROS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.macros, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[MacroEngine] Error saving macros: {e}")
            return False

    def start_recording(self, macro_name: str) -> bool:
        if self.is_recording:
            return False
        self.is_recording = True
        self.current_recording_name = macro_name.strip()
        self.recorded_steps = []
        self.event_bus.publish(EventType.MACRO_RECORD_START, {"name": self.current_recording_name})
        return True

    def record_step(self, action: str, target: Any = None, delay: float = 0.5) -> None:
        if not self.is_recording:
            return
        step = {
            "action": action,
            "target": target,
            "delay": delay
        }
        self.recorded_steps.append(step)

    def stop_recording(self) -> Optional[str]:
        if not self.is_recording:
            return None
        self.is_recording = False
        name = self.current_recording_name
        if name and self.recorded_steps:
            self.macros[name] = self.recorded_steps
            self.save_macros()
        self.event_bus.publish(EventType.MACRO_RECORD_STOP, {
            "name": name,
            "steps_count": len(self.recorded_steps)
        })
        self.current_recording_name = None
        self.recorded_steps = []
        return name

    def execute_macro(self, macro_name: str, step_executor: Any) -> bool:
        """Executes the macro in a background thread."""
        matched_name = None
        for name in self.macros:
            if name.lower() == macro_name.lower():
                matched_name = name
                break

        if not matched_name:
            return False

        steps = list(self.macros[matched_name])

        def _run():
            for step in steps:
                if getattr(SecurityEngine(), "is_emergency_stopped", False):
                    print(f"[MacroEngine] Execution aborted by emergency stop.")
                    break
                try:
                    action = step.get("action")
                    target = step.get("target")
                    delay = step.get("delay", 0.5)

                    if callable(step_executor):
                        step_executor(action, target)

                    time.sleep(delay)
                except Exception as e:
                    print(f"[MacroEngine] Error executing step {step}: {e}")

            self.event_bus.publish(EventType.MACRO_EXECUTED, {"name": matched_name})

        threading.Thread(target=_run, daemon=True).start()
        return True

    def get_all_macros(self) -> Dict[str, List[Dict[str, Any]]]:
        return dict(self.macros)

    def delete_macro(self, macro_name: str) -> bool:
        if macro_name in self.macros:
            del self.macros[macro_name]
            self.save_macros()
            return True
        return False
