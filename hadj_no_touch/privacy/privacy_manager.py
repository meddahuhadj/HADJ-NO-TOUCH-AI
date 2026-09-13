"""Privacy-first control and safety manager.

Camera and microphone are controlled here; processing stays local; no frames
are ever recorded by default. Provides camera/mic indicators, tracking pause,
privacy mode, emergency stop and a full "clear data" wipe.
"""

from __future__ import annotations

import threading
import time

from ..config import SETTINGS
from ..logging_setup import get_logger
from ..database.database import Database

log = get_logger("privacy")


class PrivacyManager:
    # Emergency stop shortcut: CTRL + ALT + H
    EMERGENCY_HOTKEY = 0x48  # 'H'
    EMERGENCY_MODS = 0x0002 | 0x0001  # MOD_ALT | MOD_CONTROL

    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self._lock = threading.RLock()

        self.camera_enabled = True
        self.mic_enabled = True
        self.tracking_paused = False
        self.privacy_mode = False
        self.control_enabled = True
        self.emergency_stopped = False

        self.emergency_stop_count = 0
        self.frame_policy = "local-only"
        self.activity_log_enabled = SETTINGS.privacy.activity_log_enabled

    # ---- toggles ------------------------------------------------------------
    def set_camera(self, on: bool) -> None:
        with self._lock:
            self.camera_enabled = on
        self.db.log_activity("INFO", f"camera {'on' if on else 'off'}")

    def set_mic(self, on: bool) -> None:
        with self._lock:
            self.mic_enabled = on
        self.db.log_activity("INFO", f"microphone {'on' if on else 'off'}")

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self.tracking_paused = paused
            if paused:
                self.frame_policy = "paused"
        self.db.log_activity("INFO", f"tracking {'paused' if paused else 'resumed'}")

    def set_privacy_mode(self, on: bool) -> None:
        with self._lock:
            self.privacy_mode = on
            self.frame_policy = "masked" if on else "local-only"
        self.db.log_activity("INFO", f"privacy mode {'on' if on else 'off'}")

    # ---- emergency stop -------------------------------------------------------
    def emergency_stop(self) -> None:
        with self._lock:
            self.control_enabled = False
            self.emergency_stopped = True
            self.emergency_stop_count += 1
        self.db.log_activity("WARN", "EMERGENCY STOP — no-touch control disabled")
        log.warning("Emergency stop engaged")

    def resume_control(self) -> None:
        with self._lock:
            self.control_enabled = True
            self.emergency_stopped = False
            self.tracking_paused = False
        self.db.log_activity("INFO", "control resumed")

    def can_act(self) -> bool:
        with self._lock:
            return (self.control_enabled and self.camera_enabled and not self.tracking_paused
                    and not self.privacy_mode)

    def indicators(self) -> dict:
        with self._lock:
            return {
                "camera": self.camera_enabled,
                "mic": self.mic_enabled,
                "paused": self.tracking_paused,
                "privacy": self.privacy_mode,
                "control": self.control_enabled,
                "emergency": self.emergency_stopped,
                "policy": self.frame_policy,
            }

    # ---- misc -----------------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        if self.activity_log_enabled:
            self.db.log_activity(level, message)

    def clear_all_user_data(self) -> None:
        self.db.clear_all_user_data()
        self.log("INFO", "all local user data cleared")

    def activity(self, limit: int = 40) -> list:
        return self.db.recent_activity(limit)