"""HADJ Demo Mode.

A completely safe simulation layer: when enabled, every action that would
touch the computer is instead logged as "SIMULATED ACTION" and surfaced in
the UI. Nothing touches the OS. This is essential for presentations, tests
and letting new users explore the product without risk.
"""

from __future__ import annotations

import threading


class DemoMode:
    def __init__(self, enabled: bool = False) -> None:
        self._enabled = bool(enabled)
        self._lock = threading.RLock()

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def toggle(self) -> bool:
        with self._lock:
            self._enabled = not self._enabled
            return self._enabled

    def simulate(self, label: str) -> str:
        """Return the text describing a simulated action."""
        return f"[DEMO] {label}"


# Intent ids that manipulate the app itself (not the computer). These stay
# fully functional in demo mode so the user always keeps control: emergency
# stop, pause, profile switching, help and calibration are not "simulated".
DEMO_EXEMPT_ACTIONS = {
    "EMERGENCY_STOP", "PAUSE_CONTROL", "RESUME_CONTROL",
    "PAUSE_INTERACTION", "FIST_LOCK", "PROFILE_SWITCH",
    "HANDS_BUSY_ON", "HANDS_BUSY_OFF", "HELP", "CALIBRATE",
    "TOGGLE_KEYBOARD", "SHOW_UI", "HIDE_UI", "OPEN_SETTINGS",
}