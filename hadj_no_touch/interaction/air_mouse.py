"""Air mouse: computes real cursor targets from the fingertip.

Movement itself is applied by the app core only when the gesture engine
approves a MOVE/DRAG_UPDATE event, so the cursor never runs away when the
user's hand is in a resting pose.
"""

from __future__ import annotations

import time

from ..config import CursorSettings, SETTINGS
from ..logging_setup import get_logger
from ..windows import mouse_control
from .interaction_plane import InteractionPlane

log = get_logger("interaction.air_mouse")


class AirMouse:
    def __init__(self, plane: InteractionPlane, cursor_settings: CursorSettings = SETTINGS.cursor):
        self.plane = plane
        self.settings = cursor_settings
        self.enabled = True
        self.current_screen: tuple[float, float] | None = None
        self.last_update_time = time.monotonic()

    def compute(self, fingertip_norm: tuple[float, float] | None) -> tuple[int, int] | None:
        """Map a normalized fingertip to sanitized screen pixel coords."""
        now = time.monotonic()
        self.last_update_time = now
        if not self.enabled or fingertip_norm is None:
            return None
        pt = self.plane.process(fingertip_norm)
        if pt is None:
            return None
        self.current_screen = (int(pt[0]), int(pt[1]))
        return self.current_screen

    def apply(self) -> None:
        """Physically move the cursor to the latest computed target."""
        if self.current_screen is not None:
            mouse_control.move_to(self.current_screen[0], self.current_screen[1])

    def large_cursor(self, on: bool) -> None:
        try:
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(0x0071, 0, 10 if on else 1, 0)
        except Exception:
            pass

    def reset(self) -> None:
        self.plane.reset()
        self.current_screen = None