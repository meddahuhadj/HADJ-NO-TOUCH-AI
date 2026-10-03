"""
Global system-wide hotkey listener for Windows.
Enables emergency stop (Ctrl + Alt + Escape) even when the HADJ window is minimized or not in focus.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal


class GlobalHotkeyWorker(QObject):
    """
    Listens for Windows global hotkeys using Win32 API RegisterHotKey.
    Runs on a daemon thread with its own message pump.
    """

    hotkey_triggered = Signal()

    def __init__(self, key_id: int = 101, modifiers: int = 0x0001 | 0x0002, vk_code: int = 0x1B):
        """
        Default: MOD_ALT (0x0001) | MOD_CONTROL (0x0002) + VK_ESCAPE (0x1B) -> Ctrl + Alt + Esc
        """
        super().__init__()
        self.key_id = key_id
        self.modifiers = modifiers
        self.vk_code = vk_code
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        try:
            # Post WM_QUIT to unblock GetMessageW
            ctypes.windll.user32.PostQuitMessage(0)
        except Exception:
            pass

    def _run_loop(self) -> None:
        try:
            user32 = ctypes.windll.user32
            # MOD_NOREPEAT = 0x4000 to avoid machine-gun firing on hold
            flags = self.modifiers | 0x4000
            success = user32.RegisterHotKey(None, self.key_id, flags, self.vk_code)
            if not success:
                # Try without MOD_NOREPEAT (older Windows 7/8 support)
                user32.RegisterHotKey(None, self.key_id, self.modifiers, self.vk_code)

            msg = wintypes.MSG()
            while self._running:
                # GetMessageW blocks until a message arrives
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                if msg.message == 0x0312:  # WM_HOTKEY
                    if msg.wParam == self.key_id:
                        self.hotkey_triggered.emit()

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as e:
            print(f"[GlobalHotkey] Listener exited: {e}")
        finally:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.key_id)
            except Exception:
                pass
