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

from os_layer.base import AppEntry, MonitorInfo, OSBackend, WindowInfo
from os_layer.windows import display as win_display
from os_layer.windows import input as win_input
from os_layer.windows import winapi
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
    def __init__(self, sound_provider=None):
        """sound_provider(volume) ← {kind: مسار wav}. اختياري: بدونه لا أصوات.
        (حقن من الخارج لكي لا تعتمد طبقة النظام على بقية التطبيق: انظر docs/oss.)"""
        self._sound_provider = sound_provider
        self._held_buttons: set[str] = set()
        self._sounds: dict | None = None
        self._sound_volume = None
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

    # ---- النوافذ: التحكّم الدقيق ----
    def list_windows(self) -> list[WindowInfo]:
        out: list[WindowInfo] = []
        for hwnd in winapi.enumerate_windows():
            title = winapi.window_title(hwnd).strip()
            if not title:
                continue
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append(WindowInfo(hwnd=hwnd, title=title, pid=pid.value,
                                  minimized=bool(user32.IsIconic(hwnd)),
                                  monitor=winapi.monitor_index_of(hwnd)))
        return out

    def focus_window(self, query: str) -> bool:
        """يجلب أول نافذة عنوانها يحتوي `query` إلى الأمام (أطول تطابق يُفضَّل)."""
        needle = query.strip().lower()
        if not needle:
            return False
        candidates = [(w, w.title.lower()) for w in self.list_windows()]
        exact = [w for w, t in candidates if t == needle]
        partial = [w for w, t in candidates if needle in t]
        target = (exact or partial)
        if not target:
            return False
        # عند تعدد الاحتواء نفضّل العنوان الأقصر (أدق عادةً)
        target.sort(key=lambda w: len(w.title))
        return winapi.bring_to_front(target[0].hwnd)

    def move_window(self, dx: int, dy: int) -> bool:
        hwnd = self._target_window()
        rect = winapi.window_rect(hwnd) if hwnd else None
        if not rect:
            return False
        left, top, width, height = rect
        return self._apply_rect(hwnd, left + int(dx), top + int(dy), width, height)

    def resize_window(self, dw: int, dh: int) -> bool:
        hwnd = self._target_window()
        rect = winapi.window_rect(hwnd) if hwnd else None
        if not rect:
            return False
        left, top, width, height = rect
        return self._apply_rect(hwnd, left, top,
                                max(200, width + int(dw)), max(120, height + int(dh)))

    def _apply_rect(self, hwnd, x: int, y: int, width: int, height: int) -> bool:
        """يحرّك/يعدّل نافذة محدّدة — يُستخدم بعد حلّ hwnd مرّة واحدة."""
        if not hwnd:
            return False
        if user32.IsIconic(hwnd):     # لا تقيس نافذة مصغّرة
            user32.ShowWindow(hwnd, winapi.SW_RESTORE)
        return bool(winapi.user32.MoveWindow(hwnd, int(x), int(y),
                                             max(1, int(width)), max(1, int(height)), True))

    def set_window_rect(self, x: int, y: int, width: int, height: int) -> bool:
        return self._apply_rect(self._target_window(), x, y, width, height)

    def center_window(self) -> bool:
        hwnd = self._target_window()
        rect = winapi.window_rect(hwnd) if hwnd else None
        if not rect:
            return False
        left, top, width, height = rect
        ax, ay, aw, ah = self._work_area_of(hwnd)
        return self._apply_rect(hwnd, ax + (aw - width) // 2,
                                ay + (ah - height) // 2, width, height)

    def _work_area_of(self, hwnd) -> tuple[int, int, int, int]:
        """مساحة عمل الشاشة التي فيها النافذة (بلا شريط المهام)."""
        handle = winapi.user32.MonitorFromWindow(hwnd, winapi.MONITOR_DEFAULTTONEAREST)
        for _h, mi in winapi.enumerate_monitors():
            if _h == handle:
                return mi.rcWork.as_tuple()
        return self.screen_rect()

    def snap_window(self, position: str) -> bool:
        hwnd = self._target_window()
        if not hwnd:
            return False
        if position == "maximize":
            user32.ShowWindow(hwnd, winapi.SW_MAXIMIZE)
            return True
        if position == "restore":
            user32.ShowWindow(hwnd, winapi.SW_RESTORE)
            return True
        rect = winapi.snap_rect(position, self._work_area_of(hwnd))
        if rect is None:
            return False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, winapi.SW_RESTORE)
        return bool(winapi.user32.MoveWindow(hwnd, rect[0], rect[1], rect[2], rect[3], True))

    def set_always_on_top(self, enabled: bool) -> bool:
        hwnd = self._target_window()
        return bool(hwnd) and winapi.set_always_on_top(hwnd, bool(enabled))

    # ---- الشاشات ----
    def list_monitors(self) -> list[MonitorInfo]:
        out: list[MonitorInfo] = []
        for index, (handle, mi) in enumerate(winapi.enumerate_monitors()):
            out.append(MonitorInfo(index=index, name=winapi.friendly_monitor_name(mi.szDevice),
                                   rect=mi.rcMonitor.as_tuple(),
                                   primary=bool(mi.dwFlags & winapi.MONITORINFOF_PRIMARY)))
        return out

    def move_window_to_monitor(self, index: int) -> bool:
        hwnd = self._target_window()
        monitors = self.list_monitors()
        if not hwnd or not monitors:
            return False
        if not 0 <= int(index) < len(monitors):
            return False            # لا صمت في Fallback: خطأ صريح
        monitor = monitors[int(index)]
        left, top, width, height = monitor.rect
        rect = winapi.window_rect(hwnd)
        if not rect:
            return False
        # نحافظ على أبعاد النافذة كما هي
        cur_w, cur_h = rect[2], rect[3]
        return self._apply_rect(hwnd, left + (width - cur_w) // 2,
                                top + (height - cur_h) // 2, cur_w, cur_h)

    def set_display_mode(self, mode: str) -> bool:
        """تبديل طريقة عرض الشاشات عبر اختصارات Windows الرسمية.

        Windows لا يوفّر اختصاراً لوضع «الشاشة الثانية فقط» (يحتاج زر F10
        عتادياً)، لذا لا ندّعي دعماً له.
        """
        if mode == "extend":
            self.hotkey("win", "shift", "right")     # ادفع إلى شاشة ثانية
            return True
        if mode == "duplicate":
            self.hotkey("win", "shift", "d")          # تكرار على الشاشتين
            return True
        if mode == "next":
            self.hotkey("win", "ctrl", "right")       # تبديل العرض للشاشة التالية
            return True
        return False

    def switch_virtual_desktop(self, direction: str) -> bool:
        if direction not in ("left", "right"):
            return False
        self.hotkey("win", "ctrl", "right" if direction == "right" else "left")
        return True

    def new_virtual_desktop(self) -> bool:
        self.hotkey("win", "ctrl", "d")
        return True

    def close_virtual_desktop(self) -> bool:
        self.hotkey("win", "ctrl", "f4")
        return True

    # ---- العرض والصوت ----
    def brightness(self, change: str, steps: int = 10) -> bool:
        delta = abs(int(steps)) * (1 if change == "up" else -1)
        return win_display.adjust_brightness(delta) is not None

    def set_brightness(self, percent: int) -> bool:
        return win_display.set_brightness(percent)

    def current_brightness(self) -> int | None:
        return win_display.get_brightness()

    def monitor_power(self, on: bool) -> bool:
        return winapi.monitor_power(bool(on))

    def set_dark_mode(self, enabled: bool) -> bool:
        return win_display.set_dark_mode(bool(enabled))

    def dark_mode_enabled(self) -> bool | None:
        return win_display.get_dark_mode()

    def toggle_microphone_mute(self) -> bool:
        """WM_APPCOMMAND يدعمها Windows رسمياً، بلا أي اعتماد إضافي."""
        return winapi.send_appcommand(winapi.APPCOMMAND_MICROPHONE_VOLUME_MUTE)

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

    # ---- الملفات ----
    def open_path(self, path: str) -> None:
        try:
            os.startfile(str(path))
        except OSError:
            subprocess.Popen(["explorer.exe", str(path)])

    def empty_recycle_bin(self) -> bool:
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                           timeout=10, capture_output=True, creationflags=0x08000000)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    # ---- آخر إدخال ----
    def seconds_since_input(self) -> float | None:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        tick = ctypes.windll.kernel32.GetTickCount()
        return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0

    # ---- الأصوات ----
    def play_sound(self, kind: str, volume: int = 70) -> None:
        if self._sound_provider is None:
            return
        if self._sounds is None or self._sound_volume != volume:
            self._sounds = self._sound_provider(volume)
            self._sound_volume = volume
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
