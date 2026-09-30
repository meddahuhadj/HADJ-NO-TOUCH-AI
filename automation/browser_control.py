import time
import pyautogui
from automation.windows_control import WindowsControlEngine


class BrowserControl:
    """Provides instant touchless browser navigation, tabs, scrolling, and search."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BrowserControl, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.win = WindowsControlEngine()

    def new_tab(self) -> None:
        pyautogui.hotkey("ctrl", "t")

    def close_tab(self) -> None:
        pyautogui.hotkey("ctrl", "w")

    def next_tab(self) -> None:
        pyautogui.hotkey("ctrl", "tab")

    def prev_tab(self) -> None:
        pyautogui.hotkey("ctrl", "shift", "tab")

    def reopen_closed_tab(self) -> None:
        pyautogui.hotkey("ctrl", "shift", "t")

    def go_back(self) -> None:
        pyautogui.hotkey("alt", "left")

    def go_forward(self) -> None:
        pyautogui.hotkey("alt", "right")

    def refresh(self) -> None:
        pyautogui.press("f5")

    def toggle_fullscreen(self) -> None:
        pyautogui.press("f11")

    def scroll_down(self, steps: int = 400) -> None:
        pyautogui.scroll(-steps)

    def scroll_up(self, steps: int = 400) -> None:
        pyautogui.scroll(steps)

    def focus_search_bar(self) -> None:
        pyautogui.hotkey("ctrl", "l")

    def search_query(self, query: str) -> None:
        """Focuses browser URL/search bar, writes the search query, and presses Enter."""
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.1)
        pyautogui.write(query, interval=0.01)
        time.sleep(0.05)
        pyautogui.press("enter")

    def zoom_in(self) -> None:
        pyautogui.hotkey("ctrl", "+")

    def zoom_out(self) -> None:
        pyautogui.hotkey("ctrl", "-")

    def zoom_reset(self) -> None:
        pyautogui.hotkey("ctrl", "0")
