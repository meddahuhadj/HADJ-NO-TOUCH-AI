import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Tuple, Optional
import pyautogui

# Configure pyautogui safety and responsiveness.
# FAILSAFE stays enabled: slamming the cursor into a screen corner raises
# FailSafeException, which is the one escape hatch that still works if the
# camera thread wedges and the gesture-based emergency stop never fires.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

try:
    import win32api
    import win32con
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import screen_brightness_control as sbc
    HAS_SBC = True
except ImportError:
    HAS_SBC = False

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False


class WindowsControlEngine:
    """Provides high-speed, direct Windows system, mouse, and keyboard automation."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WindowsControlEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.screen_width, self.screen_height = pyautogui.size()
        self._audio_endpoint = None
        self._init_audio()

    def _init_audio(self):
        if HAS_PYCAW:
            try:
                speakers = AudioUtilities.GetSpeakers()
                # Modern pycaw (2024+) provides EndpointVolume directly on the device
                if hasattr(speakers, 'EndpointVolume'):
                    self._audio_endpoint = speakers.EndpointVolume
                elif hasattr(speakers, 'Activate'):
                    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self._audio_endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            except Exception as e:
                print(f"[WindowsControl] Pycaw audio init notice: {e}")

    # ==========================
    # MOUSE CONTROLS
    # ==========================
    def get_cursor_position(self) -> Tuple[int, int]:
        return pyautogui.position()

    def move_mouse(self, x: int, y: int) -> None:
        """
        Instantly moves the cursor to (x, y), clamped to the screen bounds.

        The explicit failsafe check matters because the fast path below uses
        win32api.SetCursorPos, which bypasses pyautogui's own corner detection.
        Without this call a virtual pointer pushed into a corner would never
        raise FailSafeException and the escape hatch would be dead code.
        """
        if pyautogui.FAILSAFE:
            pyautogui.failSafeCheck()

        clamped_x = max(0, min(self.screen_width - 1, int(x)))
        clamped_y = max(0, min(self.screen_height - 1, int(y)))
        if HAS_WIN32:
            try:
                win32api.SetCursorPos((clamped_x, clamped_y))
            except Exception:
                pyautogui.moveTo(clamped_x, clamped_y, _pause=False)
        else:
            pyautogui.moveTo(clamped_x, clamped_y, _pause=False)

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None:
        if x is not None and y is not None:
            self.move_mouse(x, y)
        if HAS_WIN32:
            down_flag = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
            up_flag = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP
            win32api.mouse_event(down_flag, 0, 0, 0, 0)
            win32api.mouse_event(up_flag, 0, 0, 0, 0)
        else:
            pyautogui.click(button=button)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if x is not None and y is not None:
            self.move_mouse(x, y)
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        else:
            pyautogui.doubleClick()

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if x is not None and y is not None:
            self.move_mouse(x, y)
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        else:
            pyautogui.rightClick()

    def mouse_down(self, button: str = "left") -> None:
        if HAS_WIN32:
            flag = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
            win32api.mouse_event(flag, 0, 0, 0, 0)
        else:
            pyautogui.mouseDown(button=button)

    def mouse_up(self, button: str = "left") -> None:
        if HAS_WIN32:
            flag = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP
            win32api.mouse_event(flag, 0, 0, 0, 0)
        else:
            pyautogui.mouseUp(button=button)

    def scroll(self, amount: int) -> None:
        """Scrolls vertically. Positive amount scrolls UP, negative scrolls DOWN."""
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, int(amount * 3), 0)
        else:
            pyautogui.scroll(int(amount))

    # ==========================
    # KEYBOARD HOTKEYS & SHORTCUTS
    # ==========================
    def copy(self) -> None:
        pyautogui.hotkey("ctrl", "c")

    def paste(self) -> None:
        pyautogui.hotkey("ctrl", "v")

    def cut(self) -> None:
        pyautogui.hotkey("ctrl", "x")

    def undo(self) -> None:
        pyautogui.hotkey("ctrl", "z")

    def select_all(self) -> None:
        pyautogui.hotkey("ctrl", "a")

    def switch_app(self) -> None:
        """Simulates Alt+Tab task switching."""
        pyautogui.hotkey("alt", "tab")

    def show_desktop(self) -> None:
        """Simulates Win+D to toggle desktop."""
        pyautogui.hotkey("win", "d")

    def open_explorer(self) -> None:
        """Simulates Win+E to open File Explorer."""
        pyautogui.hotkey("win", "e")

    def lock_pc(self) -> None:
        """Simulates Win+L or LockWorkStation to lock the Windows PC."""
        if HAS_WIN32:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        else:
            pyautogui.hotkey("win", "l")

    def close_current_window(self) -> None:
        """Simulates Alt+F4 to close current window."""
        pyautogui.hotkey("alt", "f4")

    def minimize_window(self) -> None:
        """Simulates Win+Down to minimize or un-maximize current window."""
        pyautogui.hotkey("win", "down")

    def maximize_window(self) -> None:
        """Simulates Win+Up to maximize current window."""
        pyautogui.hotkey("win", "up")

    def snap_window_left(self) -> None:
        pyautogui.hotkey("win", "left")

    def snap_window_right(self) -> None:
        pyautogui.hotkey("win", "right")

    def open_task_view(self) -> None:
        """Simulates Win+Tab for Windows Task View."""
        pyautogui.hotkey("win", "tab")

    def new_virtual_desktop(self) -> None:
        """Simulates Win+Ctrl+D to create a new virtual desktop."""
        pyautogui.hotkey("win", "ctrl", "d")

    def close_virtual_desktop(self) -> None:
        """Simulates Win+Ctrl+F4 to close active virtual desktop."""
        pyautogui.hotkey("win", "ctrl", "f4")

    def next_virtual_desktop(self) -> None:
        """Simulates Win+Ctrl+Right to switch to next desktop."""
        pyautogui.hotkey("win", "ctrl", "right")

    def prev_virtual_desktop(self) -> None:
        """Simulates Win+Ctrl+Left to switch to previous desktop."""
        pyautogui.hotkey("win", "ctrl", "left")

    def open_task_manager(self) -> None:
        """Opens Windows Task Manager."""
        pyautogui.hotkey("ctrl", "shift", "esc")

    def zoom_in(self) -> None:
        pyautogui.hotkey("ctrl", "+")

    def zoom_out(self) -> None:
        pyautogui.hotkey("ctrl", "-")

    def zoom_reset(self) -> None:
        pyautogui.hotkey("ctrl", "0")

    def refresh(self) -> None:
        pyautogui.press("f5")

    def empty_recycle_bin(self) -> bool:
        """Empties Windows Recycle Bin safely using Shell32 API."""
        try:
            import ctypes
            # Flags: SHERB_NOCONFIRMATION = 0x00000001, SHERB_NOPROGRESSUI = 0x00000002, SHERB_NOSOUND = 0x00000004
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
            return True
        except Exception as e:
            print(f"[WindowsControl] Empty recycle bin notice: {e}")
            return False

    def type_text(self, text: str) -> None:
        """Types raw text into the currently focused window."""
        pyautogui.write(text, interval=0.01)

    def press_key(self, key_name: str) -> None:
        pyautogui.press(key_name)

    # ==========================
    # HISTORY NAVIGATION
    # ==========================
    def go_back(self) -> None:
        """Back navigation, as Alt+Left. Works in browsers and in Explorer."""
        pyautogui.hotkey("alt", "left")

    def go_forward(self) -> None:
        """Forward navigation, as Alt+Right."""
        pyautogui.hotkey("alt", "right")

    def go_home(self) -> None:
        """Home navigation, as Alt+Home."""
        pyautogui.hotkey("alt", "home")

    # ==========================
    # VOLUME & MEDIA CONTROLS
    # ==========================
    def volume_up(self, step: int = 6) -> None:
        if self._audio_endpoint:
            try:
                cur = self._audio_endpoint.GetMasterVolumeLevelScalar()
                self._audio_endpoint.SetMasterVolumeLevelScalar(min(1.0, cur + (step / 100.0)), None)
                return
            except Exception:
                pass
        pyautogui.press("volumeup")

    def volume_down(self, step: int = 6) -> None:
        if self._audio_endpoint:
            try:
                cur = self._audio_endpoint.GetMasterVolumeLevelScalar()
                self._audio_endpoint.SetMasterVolumeLevelScalar(max(0.0, cur - (step / 100.0)), None)
                return
            except Exception:
                pass
        pyautogui.press("volumedown")

    def volume_mute(self) -> None:
        if self._audio_endpoint:
            try:
                cur_mute = self._audio_endpoint.GetMute()
                self._audio_endpoint.SetMute(0 if cur_mute else 1, None)
                return
            except Exception:
                pass
        pyautogui.press("volumemute")

    def set_volume_percent(self, percent: int) -> None:
        scalar = max(0.0, min(1.0, percent / 100.0))
        if self._audio_endpoint:
            try:
                self._audio_endpoint.SetMasterVolumeLevelScalar(scalar, None)
                return
            except Exception:
                pass

    def media_play_pause(self) -> None:
        pyautogui.press("playpause")

    def media_next(self) -> None:
        pyautogui.press("nexttrack")

    def media_prev(self) -> None:
        pyautogui.press("prevtrack")

    # ==========================
    # BRIGHTNESS CONTROLS
    # ==========================
    def brightness_up(self, step: int = 10) -> None:
        if HAS_SBC:
            try:
                current = sbc.get_brightness()
                cur_val = current[0] if isinstance(current, list) and current else 70
                sbc.set_brightness(min(100, cur_val + step))
            except Exception as e:
                print(f"[WindowsControl] Brightness error: {e}")

    def brightness_down(self, step: int = 10) -> None:
        if HAS_SBC:
            try:
                current = sbc.get_brightness()
                cur_val = current[0] if isinstance(current, list) and current else 70
                sbc.set_brightness(max(0, cur_val - step))
            except Exception as e:
                print(f"[WindowsControl] Brightness error: {e}")

    def set_brightness_percent(self, percent: int) -> None:
        if HAS_SBC:
            try:
                sbc.set_brightness(max(0, min(100, percent)))
            except Exception as e:
                print(f"[WindowsControl] Brightness set error: {e}")

    # ==========================
    # SCREENSHOTS
    # ==========================
    def take_screenshot(self, save_dir: Optional[str] = None) -> str:
        """Captures a full screenshot and saves to pictures or screenshots folder."""
        if not save_dir:
            pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
            os.makedirs(pictures_dir, exist_ok=True)
            save_dir = pictures_dir

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"HADJ_Screenshot_{timestamp}.png"
        full_path = os.path.join(save_dir, filename)

        img = pyautogui.screenshot()
        img.save(full_path)
        return full_path

    # ==========================
    # POWER CONTROLS (Safety gated)
    # ==========================
    def shutdown_pc(self) -> None:
        subprocess.run(["shutdown", "/s", "/t", "10"], check=False)

    def restart_pc(self) -> None:
        subprocess.run(["shutdown", "/r", "/t", "10"], check=False)

    def sleep_pc(self) -> None:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
