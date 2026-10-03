"""
HADJ NO-TOUCH AI — Presentation & Kiosk Mode Guard
Restricts system-level actions (Alt+Tab, window close, shell commands)
retaining only navigation (Page Up/Down, Scroll, Next/Prev Slide).
"""

from typing import Set


class KioskModeManager:
    """
    Kiosk / Presentation Mode Guard.
    Filters actions to prevent accidental desktop/window manipulation during presentations.
    """

    ALLOWED_ACTIONS: Set[str] = {
        "media_next", "media_prev", "media_play_pause",
        "scroll_up", "scroll_down",
        "page_up", "page_down", "press_key"
    }

    def __init__(self):
        self.is_kiosk: bool = False

    def toggle(self) -> bool:
        self.is_kiosk = not self.is_kiosk
        return self.is_kiosk

    def is_action_allowed(self, action_name: str) -> bool:
        if not self.is_kiosk:
            return True
        return action_name.lower() in self.ALLOWED_ACTIONS
