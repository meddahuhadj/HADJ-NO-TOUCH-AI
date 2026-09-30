import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
EVENT_LOG_FILE = os.path.join(LOGS_DIR, "system_events.jsonl")


class EventLogger:
    """Privacy-first Event Logger that logs structured command events without storing raw biometric data."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EventLogger, cls).__new__(cls)
            cls._instance._recent_events: List[Dict[str, Any]] = []
            cls._instance._max_recent = 500
            cls._instance._ensure_dir()
        return cls._instance

    def _ensure_dir(self) -> None:
        if not os.path.exists(LOGS_DIR):
            try:
                os.makedirs(LOGS_DIR, exist_ok=True)
            except Exception as e:
                print(f"[EventLogger] Error creating logs dir: {e}")

    def log(
        self,
        command: str,
        intent: str,
        action: str,
        result: str = "SUCCESS",
        confidence: float = 1.0,
        risk_level: str = "LOW",
        source: str = "VOICE",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Logs a command execution event."""
        now = datetime.now()
        entry = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "iso_time": now.isoformat(),
            "epoch": time.time(),
            "source": source,
            "command": command,
            "intent": intent,
            "action": action,
            "result": result,
            "confidence": round(confidence, 3),
            "risk_level": risk_level,
            "details": details or {}
        }

        # Keep in-memory buffer
        self._recent_events.append(entry)
        if len(self._recent_events) > self._max_recent:
            self._recent_events.pop(0)

        # Append to offline jsonl file
        try:
            with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[EventLogger] Error writing event log: {e}")

        return entry

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._recent_events[-limit:]))

    def clear(self) -> None:
        self._recent_events.clear()
        if os.path.exists(EVENT_LOG_FILE):
            try:
                open(EVENT_LOG_FILE, "w").close()
            except Exception:
                pass
