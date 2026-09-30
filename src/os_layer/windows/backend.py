"""تنفيذ OSBackend لنظام Windows 10/11."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import threading
import time
import winsound
from ctypes import wintypes

from core import paths
from core.sounds import ensure_sounds
from os_layer.base import AppEntry, OSBackend
from os_layer.windows import input as win_input
from os_layer.windows.apps import list_installed_apps

log = logging.getLogger(__name__)
user32 = win_input.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_CLOSE, WM_HOTKEY, WM_QUIT = 0x0010, 0x0312, 0x0012
SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
MOD = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000

user32.GetForegroundWindow.restype = wintypes.HWND
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.IsZoomed.argtypes = (wintypes.HWND,)
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


class WindowsBackend(OSBackend):
    def __init__(self):
        self._held_buttons: set[str] = set()
        self._sounds = None
        self._hotkey_threads: list[tuple[threading.Thread, int]] = []   # (الخيط، معرّفه في Windows)

    # ---- إعداد العملية ----
    def prepare_process(self) -> None:
        try:  # PER_MONITOR_AWARE_V2: إحداثيات فعلية على كل الشاشات
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                pass

    # ---- لوحة المفاتيح ----
    def key(self, key: str, times: int = 1) -> None:
        for _ in range(max(1, times)):
            win_input.press_keys([key])

    def hotkey(self, *keys: str) -> None:
        win_input.press_keys(list(keys))

    def type_text(self, text: str) -> None:
        win_input.type_unicode(text)

    # ---- الفأرة ----
    def mouse_position(self) -> tuple[int, int]:
        return win_input.get_cursor()

    def mouse_move(self, x: int, y: int) -> None:
        win_input.set_cursor(x, y)

    def mouse_button(self, button: str = "left", action: str = "click", count: int = 1) -> None:
        if action == "down":
            win_input.mouse_button(button, "down")
            self._held_buttons.add(button)
        elif action == "up":
            win_input.mouse_button(button, "up")
            self._held_buttons.discard(button)
        else:
            for i in range(max(1, count)):
                win_input.mouse_button(button, "down")
                win_input.mouse_button(button, "up")
                if i + 1 < count:
                    time.sleep(0.05)

    def scroll(self, notches: int, horizontal: bool = False, ctrl: bool = False) -> None:
        win_input.mouse_wheel(notches, horizontal, ctrl)

    def screen_rect(self) -> tuple[int, int, int, int]:
        gsm = user32.GetSystemMetrics
        return gsm(76), gsm(77), gsm(78), gsm(79)

    def release_all(self) -> None:
        # يشمل الأزرار التي ضغطتها عملية أخرى (مثل عملية الرؤية إن توقفت أثناء السحب)
        held = set(self._held_buttons)
        for button, vk in (("left", 0x01), ("right", 0x02), ("middle", 0x04)):
            if user32.GetAsyncKeyState(vk) & 0x8000:
                held.add(button)
        for b in held:
            try:
                win_input.mouse_button(b, "up")
            except OSError:
                pass
        self._held_buttons.clear()
        try:
            win_input.key_up(["ctrl", "shift", "alt", "win"])
        except OSError:
            pass

    # ---- النوافذ ----
    def _target_window(self):
        hwnd = user32.GetForegroundWindow()
        if not hwnd or _class_name(hwnd) in SHELL_CLASSES:
            return None
        return hwnd

    def close_window(self) -> bool:
        hwnd = self._target_window()
        return bool(hwnd) and bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))

    def minimize_window(self) -> bool:
        hwnd = self._target_window()
        return bool(hwnd) and (user32.ShowWindow(hwnd, SW_MINIMIZE) or True)

    def maximize_window(self) -> bool:
        hwnd = self._target_window()
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, SW_RESTORE if user32.IsZoomed(hwnd) else SW_MAXIMIZE)
        return True

    def switch_window(self) -> None:
        self.hotkey("alt", "tab")

    def show_desktop(self) -> None:
        self.hotkey("win", "d")

    def active_window_title(self) -> str:
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value

    # ---- النظام ----
    def volume(self, change: str, steps: int = 1) -> None:
        if change == "mute":
            self.key("volume_mute")
        else:
            self.key(f"volume_{change}", times=steps)

    def lock_screen(self) -> None:
        user32.LockWorkStation()

    def screenshot(self) -> None:
        # يحفظ تلقائياً في "الصور\لقطات الشاشة"
        self.hotkey("win", "printscreen")

    def power(self, action: str) -> None:
        flag = {"shutdown": "/s", "restart": "/r"}[action]
        subprocess.Popen(["shutdown", flag, "/t", "5"], creationflags=0x08000000)

    def open_search(self) -> None:
        self.hotkey("win", "s")

    def launch(self, entry: AppEntry) -> None:
        try:  # السماح للتطبيق الجديد بأخذ التركيز
            user32.AllowSetForegroundWindow(-1)
        except OSError:
            pass
        if entry.kind == "appid":
            os.startfile(f"shell:AppsFolder\\{entry.target}")
        else:
            os.startfile(entry.target)

    def list_apps(self) -> list[AppEntry]:
        return list_installed_apps()

    # ---- الأصوات ----
    def play_sound(self, kind: str) -> None:
        if self._sounds is None:
            self._sounds = ensure_sounds(paths.user_dir() / "sounds")
        p = self._sounds.get(kind)
        if p:
            winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)

    # ---- اختصار عام ----
    def register_hotkey(self, combo: str, callback) -> bool:
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        mods = 0
        vk = None
        for p in parts:
            if p in MOD:
                mods |= MOD[p]
            else:
                vk = win_input.vk_code(p)
        if vk is None:
            return False
        ok = threading.Event()
        result = {"ok": False}

        def loop():
            hk_id = 0xB00 + len(self._hotkey_threads)
            result["ok"] = bool(user32.RegisterHotKey(None, hk_id, mods | MOD_NOREPEAT, vk))
            result["tid"] = kernel32.GetCurrentThreadId()
            ok.set()
            if not result["ok"]:
                return
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == hk_id:
                    try:
                        callback()
                    except Exception:  # noqa: BLE001
                        log.exception("خطأ في معالج الاختصار")
            user32.UnregisterHotKey(None, hk_id)

        t = threading.Thread(target=loop, daemon=True, name=f"hotkey-{combo}")
        t.start()
        ok.wait(2)
        if not result["ok"]:
            log.warning("تعذر تسجيل الاختصار %s (ربما مستخدم من برنامج آخر)", combo)
            return False
        self._hotkey_threads.append((t, result["tid"]))
        return True

    def close(self) -> None:
        """إنهاء خيوط الاختصارات (WM_QUIT يوقف GetMessageW ثم يُلغى التسجيل)."""
        for t, tid in self._hotkey_threads:
            user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
            t.join(timeout=1)
        self._hotkey_threads.clear()

    def hard_exit(self, code: int) -> None:
        """خروج دون تفريغ مكتبات DLL: بعض المكتبات الأصلية تنهار عند تفريغها في نهاية العملية."""
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
