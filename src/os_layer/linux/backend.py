"""طبقة النظام لـ Linux (جلسة X11): XTEST للوحة المفاتيح والفأرة، EWMH للنوافذ، وأدوات النظام المعيارية.

python-xlib (Python خالص، يتكلم بروتوكول X مباشرة عبر مقبس Unix محلي): لا مكتبات نظام إضافية.
لا خطاف لوحة مفاتيح ولا قراءة لما يُكتب (نفس قواعد Windows، يفحصها scripts/export_oss.py).
ما لا يتوفر أداته على الجهاز (السطوع، الصوت…) يُستبعد من capabilities() فتختفي أوامره.

Wayland: يعمل فقط داخل XWayland (نوافذ X11). الدعم الكامل خطة لاحقة (انظر docs/portage).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time

from os_layer.base import OPTIONAL, AppEntry, MonitorInfo, OSBackend, WindowInfo
from os_layer.geometry import snap_rect
from os_layer.linux import desktop
from os_layer.linux.keys import MODIFIERS, char_keysym, keysym_name

log = logging.getLogger(__name__)

BUTTONS = {"left": 1, "middle": 2, "right": 3}
WHEEL = {"up": 4, "down": 5, "left": 6, "right": 7}
_NET_WM_STATE_REMOVE, _NET_WM_STATE_ADD, _NET_WM_STATE_TOGGLE = 0, 1, 2


def _run(args: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess | None:
    """أداة نظام دون shell. None إن لم توجد أو فشلت."""
    if not shutil.which(args[0]):
        return None
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def _ok(args: list[str]) -> bool:
    r = _run(args)
    return r is not None and r.returncode == 0


class LinuxX11Backend(OSBackend):
    def __init__(self, sound_provider=None, display_name: str | None = None):
        from Xlib import display
        self._display_name = display_name
        self.d = display.Display(display_name)
        self.root = self.d.screen().root
        self._lock = threading.RLock()           # Display ليس آمناً بين الخيوط
        self._sound_provider = sound_provider
        self._sounds: dict | None = None
        self._sound_volume = None
        self._held_buttons: set[str] = set()
        self._hotkeys: list[tuple[threading.Thread, object]] = []
        self._spare_keycode: int | None = None
        # XWayland (جلسة Wayland): إعادة ربط المفاتيح قد تقطع اتصال X (لوحظ على WSLg): لا نستعملها
        self.xwayland = bool(os.environ.get("WAYLAND_DISPLAY")) or "XWAYLAND" in self.d.list_extensions()

    # ------------------------------------------------------------------ أدوات X
    def _atom(self, name: str) -> int:
        return self.d.intern_atom(name)

    def _prop(self, window, name: str):
        from Xlib import X
        try:
            p = window.get_full_property(self._atom(name), X.AnyPropertyType)
        except Exception:  # noqa: BLE001 - نافذة أُغلقت أثناء القراءة
            return None
        return p.value if p else None

    def _window(self, wid: int):
        return self.d.create_resource_object("window", wid)

    def _client_message(self, window, name: str, data: list[int]) -> None:
        from Xlib import X
        from Xlib.protocol import event
        data = (data + [0] * 5)[:5]
        ev = event.ClientMessage(window=window, client_type=self._atom(name), data=(32, data))
        self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.d.flush()

    def _keycode(self, keysym: int) -> int:
        return self.d.keysym_to_keycode(keysym)

    def _named_keycode(self, key: str) -> int:
        from Xlib import XK
        sym = XK.string_to_keysym(keysym_name(key))
        code = self._keycode(sym) if sym else 0
        if not code:
            raise ValueError(f"المفتاح {key!r} غير موجود في تخطيط لوحة المفاتيح الحالي")
        return code

    def _fake(self, kind, detail: int, **kw) -> None:
        from Xlib.ext import xtest
        xtest.fake_input(self.d, kind, detail, **kw)

    # ------------------------------------------------------------------ لوحة المفاتيح
    def _press_codes(self, codes: list[int]) -> None:
        from Xlib import X
        with self._lock:
            for c in codes:
                self._fake(X.KeyPress, c)
            for c in reversed(codes):
                self._fake(X.KeyRelease, c)
            self.d.sync()

    def key(self, key: str, times: int = 1) -> None:
        code = self._named_keycode(key)
        for _ in range(max(1, times)):
            self._press_codes([code])

    def hotkey(self, *keys: str) -> None:
        self._press_codes([self._named_keycode(k) for k in keys])

    def type_text(self, text: str) -> None:
        """أي محرف (العربية، الرموز…): إن لم يوجد في التخطيط يُربط مؤقتاً بمفتاح غير مستخدم ثم يُعاد.

        تحت XWayland لا إعادة ربط: إن احتوى النص محارف خارج التخطيط لا يُكتب شيء ويُرفع OSError
        (نص مبتور بصمت أسوأ من رسالة خطأ، خاصة في الإملاء)."""
        from Xlib import X
        if self.xwayland:
            missing = sorted({ch for ch in text if not self._keycode(char_keysym(ch))})
            if missing:
                raise OSError(f"محارف خارج تخطيط لوحة المفاتيح لا تُكتب تحت Wayland: {''.join(missing)!r}")
        with self._lock:
            for ch in text:
                sym = char_keysym(ch)
                code = self._keycode(sym)
                shift = False
                if code:
                    # المحرف في المستوى الثاني (حرف كبير، !…) يحتاج Shift
                    shift = self.d.keycode_to_keysym(code, 0) != sym and self.d.keycode_to_keysym(code, 1) == sym
                else:
                    code = self._remap_spare(sym)
                    if not code:
                        log.warning("تعذر كتابة المحرف %r", ch)
                        continue
                shift_code = self._named_keycode("shift") if shift else None
                if shift_code:
                    self._fake(X.KeyPress, shift_code)
                self._fake(X.KeyPress, code)
                self._fake(X.KeyRelease, code)
                if shift_code:
                    self._fake(X.KeyRelease, shift_code)
                self.d.sync()
            self._restore_spare()

    def _remap_spare(self, keysym: int) -> int:
        """مفتاح بلا ربط (keysym=0) يُعطى المحرف المطلوب مؤقتاً (طريقة xdotool)."""
        if self._spare_keycode is None:
            first = self.d.display.info.min_keycode
            count = self.d.display.info.max_keycode - first + 1
            mapping = self.d.get_keyboard_mapping(first, count)
            for i, syms in enumerate(mapping):
                if not any(syms):
                    self._spare_keycode = first + i
                    break
            else:
                return 0
        self.d.change_keyboard_mapping(self._spare_keycode, [(keysym, keysym)])
        self.d.sync()
        time.sleep(0.01)    # بعض العملاء يقرأون التخطيط الجديد بعد إشعار MappingNotify
        return self._spare_keycode

    def _restore_spare(self) -> None:
        if self._spare_keycode is not None:
            self.d.change_keyboard_mapping(self._spare_keycode, [(0, 0)])
            self.d.sync()

    # ------------------------------------------------------------------ الفأرة
    def mouse_position(self) -> tuple[int, int]:
        with self._lock:
            p = self.root.query_pointer()
        return p.root_x, p.root_y

    def mouse_move(self, x: int, y: int) -> None:
        from Xlib import X
        with self._lock:
            self._fake(X.MotionNotify, 0, x=int(x), y=int(y))
            self.d.sync()

    def mouse_button(self, button: str = "left", action: str = "click", count: int = 1) -> None:
        from Xlib import X
        b = BUTTONS[button]
        with self._lock:
            if action == "down":
                self._fake(X.ButtonPress, b)
                self._held_buttons.add(button)
            elif action == "up":
                self._fake(X.ButtonRelease, b)
                self._held_buttons.discard(button)
            else:
                for i in range(max(1, count)):
                    self._fake(X.ButtonPress, b)
                    self._fake(X.ButtonRelease, b)
                    if i + 1 < count:
                        self.d.sync()
                        time.sleep(0.05)
            self.d.sync()

    def scroll(self, notches: int, horizontal: bool = False, ctrl: bool = False) -> None:
        from Xlib import X
        if not notches:
            return
        if horizontal:
            b = WHEEL["right" if notches > 0 else "left"]
        else:
            b = WHEEL["up" if notches > 0 else "down"]
        with self._lock:
            ctrl_code = self._named_keycode("ctrl") if ctrl else None
            if ctrl_code:
                self._fake(X.KeyPress, ctrl_code)
            for _ in range(abs(int(notches))):
                self._fake(X.ButtonPress, b)
                self._fake(X.ButtonRelease, b)
            if ctrl_code:
                self._fake(X.KeyRelease, ctrl_code)
            self.d.sync()

    def screen_rect(self) -> tuple[int, int, int, int]:
        s = self.d.screen()
        return 0, 0, s.width_in_pixels, s.height_in_pixels

    def release_all(self) -> None:
        """يحرر كل زر فأرة وكل مفتاح تعديل (حتى ما ضغطته عملية أخرى، مثل عملية الرؤية)."""
        from Xlib import X
        with self._lock:
            try:
                mask = self.root.query_pointer().mask
            except Exception:  # noqa: BLE001
                mask = 0
            held = set(self._held_buttons)
            for name, bit in (("left", X.Button1Mask), ("middle", X.Button2Mask), ("right", X.Button3Mask)):
                if mask & bit:
                    held.add(name)
            for name in held:
                self._fake(X.ButtonRelease, BUTTONS[name])
            self._held_buttons.clear()
            for m in MODIFIERS:
                try:
                    self._fake(X.KeyRelease, self._named_keycode(m))
                except ValueError:
                    pass
            self.d.sync()

    # ------------------------------------------------------------------ النوافذ (EWMH)
    def _active(self):
        v = self._prop(self.root, "_NET_ACTIVE_WINDOW")
        return self._window(v[0]) if v and v[0] else None

    def _title(self, w) -> str:
        v = self._prop(w, "_NET_WM_NAME") or self._prop(w, "WM_NAME")
        if isinstance(v, bytes):
            return v.decode("utf-8", "replace")
        return str(v or "")

    def _wm_state(self, w, add: bool, *states: str) -> None:
        atoms = [self._atom(s) for s in states] + [0]
        self._client_message(w, "_NET_WM_STATE",
                             [_NET_WM_STATE_ADD if add else _NET_WM_STATE_REMOVE, atoms[0], atoms[1], 1])

    def close_window(self) -> bool:
        w = self._active()
        if w is None:
            return False
        with self._lock:
            self._client_message(w, "_NET_CLOSE_WINDOW", [int(time.time()) & 0xFFFFFFFF, 1])
        return True

    def minimize_window(self) -> bool:
        w = self._active()
        if w is None:
            return False
        with self._lock:
            self._client_message(w, "WM_CHANGE_STATE", [3])   # IconicState
        return True

    def maximize_window(self) -> bool:
        w = self._active()
        if w is None:
            return False
        with self._lock:
            self._wm_state(w, True, "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ")
        return True

    def switch_window(self) -> None:
        self.hotkey("alt", "tab")

    def show_desktop(self) -> None:
        cur = self._prop(self.root, "_NET_SHOWING_DESKTOP")
        with self._lock:
            self._client_message(self.root, "_NET_SHOWING_DESKTOP", [0 if cur and cur[0] else 1])

    def active_window_title(self) -> str:
        w = self._active()
        return self._title(w) if w is not None else ""

    def list_windows(self) -> list[WindowInfo]:
        ids = self._prop(self.root, "_NET_CLIENT_LIST") or []
        hidden = self._atom("_NET_WM_STATE_HIDDEN")
        out = []
        for wid in ids:
            w = self._window(wid)
            title = self._title(w).strip()
            if not title:
                continue
            pid = (self._prop(w, "_NET_WM_PID") or [0])[0]
            states = self._prop(w, "_NET_WM_STATE") or []
            out.append(WindowInfo(hwnd=int(wid), title=title, pid=int(pid), minimized=hidden in states))
        return out

    def focus_window(self, query: str) -> bool:
        needle = query.strip().lower()
        wins = self.list_windows()
        exact = [w for w in wins if w.title.lower() == needle]
        partial = [w for w in wins if needle and needle in w.title.lower()]
        target = (exact or partial)
        if not target:
            return False
        with self._lock:
            self._client_message(self._window(target[0].hwnd), "_NET_ACTIVE_WINDOW", [2, 0, 0])
        return True

    def _geometry(self, w) -> tuple[int, int, int, int] | None:
        try:
            g = w.get_geometry()
            t = w.translate_coords(self.root, 0, 0)
            return -t.x, -t.y, g.width, g.height
        except Exception:  # noqa: BLE001
            return None

    def _move_resize(self, w, x: int, y: int, width: int, height: int) -> bool:
        # flags: الجاذبية الافتراضية + x,y,w,h محددة (بت 8-11) + المصدر = تطبيق تحكم (بت 12)
        flags = (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11) | (2 << 12)
        with self._lock:
            self._wm_state(w, False, "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ")
            self._client_message(w, "_NET_MOVERESIZE_WINDOW", [flags, int(x), int(y), max(1, int(width)),
                                                               max(1, int(height))])
        return True

    def set_window_rect(self, x: int, y: int, width: int, height: int) -> bool:
        w = self._active()
        return w is not None and self._move_resize(w, x, y, width, height)

    def move_window(self, dx: int, dy: int) -> bool:
        w = self._active()
        g = self._geometry(w) if w is not None else None
        return bool(g) and self._move_resize(w, g[0] + dx, g[1] + dy, g[2], g[3])

    def resize_window(self, dw: int, dh: int) -> bool:
        w = self._active()
        g = self._geometry(w) if w is not None else None
        return bool(g) and self._move_resize(w, g[0], g[1], g[2] + dw, g[3] + dh)

    def _work_area(self) -> tuple[int, int, int, int]:
        v = self._prop(self.root, "_NET_WORKAREA")
        return tuple(int(x) for x in v[:4]) if v and len(v) >= 4 else self.screen_rect()

    def center_window(self) -> bool:
        w = self._active()
        g = self._geometry(w) if w is not None else None
        if not g:
            return False
        left, top, width, height = self._work_area()
        return self._move_resize(w, left + (width - g[2]) // 2, top + (height - g[3]) // 2, g[2], g[3])

    def snap_window(self, position: str) -> bool:
        w = self._active()
        if w is None:
            return False
        if position == "maximize":
            return self.maximize_window()
        if position == "restore":
            with self._lock:
                self._wm_state(w, False, "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ")
            return True
        rect = snap_rect(position, self._work_area())
        return rect is not None and self._move_resize(w, *rect)

    def set_always_on_top(self, enabled: bool) -> bool:
        w = self._active()
        if w is None:
            return False
        with self._lock:
            self._wm_state(w, bool(enabled), "_NET_WM_STATE_ABOVE")
        return True

    # ------------------------------------------------------------------ الشاشات
    def list_monitors(self) -> list[MonitorInfo]:
        from Xlib.ext import randr
        try:
            with self._lock:
                mons = randr.get_monitors(self.root, True).monitors
        except Exception:  # noqa: BLE001 - خادم بلا RandR 1.5
            return [MonitorInfo(0, "screen", self.screen_rect(), True)]
        out = []
        for i, m in enumerate(mons):
            name = self.d.get_atom_name(m.name) if m.name else f"monitor {i + 1}"
            out.append(MonitorInfo(i, name, (m.x, m.y, m.width_in_pixels, m.height_in_pixels), bool(m.primary)))
        return out

    def move_window_to_monitor(self, index: int) -> bool:
        w = self._active()
        mons = self.list_monitors()
        g = self._geometry(w) if w is not None else None
        if not g or not 0 <= int(index) < len(mons):
            return False
        left, top, width, height = mons[int(index)].rect
        nw, nh = min(g[2], width), min(g[3], height)
        return self._move_resize(w, left + (width - nw) // 2, top + (height - nh) // 2, nw, nh)

    def switch_virtual_desktop(self, direction: str) -> bool:
        if direction not in ("left", "right"):
            return False
        n = (self._prop(self.root, "_NET_NUMBER_OF_DESKTOPS") or [1])[0]
        cur = (self._prop(self.root, "_NET_CURRENT_DESKTOP") or [0])[0]
        target = cur + (1 if direction == "right" else -1)
        if not 0 <= target < n:
            return False
        with self._lock:
            self._client_message(self.root, "_NET_CURRENT_DESKTOP", [target, int(time.time()) & 0xFFFFFFFF])
        return True

    # ------------------------------------------------------------------ العرض والصوت
    def brightness(self, change: str, steps: int = 10) -> bool:
        sign = "+" if change == "up" else "-"
        return _ok(["brightnessctl", "set", f"{abs(int(steps))}%{sign}"])

    def set_brightness(self, percent: int) -> bool:
        return _ok(["brightnessctl", "set", f"{max(1, min(100, int(percent)))}%"])

    def current_brightness(self) -> int | None:
        cur, mx = _run(["brightnessctl", "get"]), _run(["brightnessctl", "max"])
        try:
            return round(int(cur.stdout) * 100 / int(mx.stdout))
        except (AttributeError, ValueError, ZeroDivisionError):
            return None

    def monitor_power(self, on: bool) -> bool:
        return _ok(["xset", "dpms", "force", "on" if on else "off"])

    def set_dark_mode(self, enabled: bool) -> bool:
        return _ok(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
                    "prefer-dark" if enabled else "default"])

    def dark_mode_enabled(self) -> bool | None:
        r = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
        return None if r is None or r.returncode else "dark" in r.stdout

    def toggle_microphone_mute(self) -> bool:
        return _ok(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]) or \
            _ok(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"])

    def volume(self, change: str, steps: int = 1) -> None:
        pct = 5 * max(1, int(steps))
        if change == "mute":
            ok = _ok(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]) or \
                _ok(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
        else:
            sign = "+" if change == "up" else "-"
            ok = _ok(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{pct}%{sign}"]) or \
                _ok(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sign}{pct}%"])
        if not ok:   # بلا أدوات صوت: مفاتيح الوسائط يلتقطها سطح المكتب
            self.key({"mute": "volume_mute", "up": "volume_up"}.get(change, "volume_down"), steps if change != "mute" else 1)

    # ------------------------------------------------------------------ النظام
    def lock_screen(self) -> None:
        if not _ok(["loginctl", "lock-session"]):
            _ok(["xdg-screensaver", "lock"])

    def screenshot(self) -> None:
        self.key("printscreen")      # يلتقطها سطح المكتب (GNOME، KDE) ويحفظ في الصور

    def power(self, action: str) -> None:
        _ok(["systemctl", {"shutdown": "poweroff", "restart": "reboot"}[action]])

    def open_search(self) -> None:
        self.key("win")              # GNOME/KDE: مفتاح Super وحده يفتح البحث

    def open_path(self, path: str) -> None:
        for opener in (["xdg-open"], ["gio", "open"]):
            if shutil.which(opener[0]):
                subprocess.Popen([*opener, str(path)], start_new_session=True)
                return
        raise OSError("xdg-open/gio غير موجودين")

    def empty_recycle_bin(self) -> bool:
        return _ok(["gio", "trash", "--empty"])

    def launch(self, entry: AppEntry) -> None:
        if entry.kind == "appid" and shutil.which("gtk-launch"):
            subprocess.Popen(["gtk-launch", entry.target], start_new_session=True)
        elif entry.kind == "appid":
            app = next((a for a in desktop.list_desktop_apps() if a.id == entry.target), None)
            if app is None:
                raise OSError(f"تطبيق غير موجود: {entry.target}")
            subprocess.Popen(app.exec_args, start_new_session=True)
        else:
            self.open_path(entry.target)

    def list_apps(self) -> list[AppEntry]:
        langs = tuple(x for x in (os.environ.get("LANG", "")[:2],) if x)
        return [AppEntry(a.name, a.id, "appid") for a in desktop.list_desktop_apps(langs=langs)]

    def play_sound(self, kind: str, volume: int = 70) -> None:
        if self._sound_provider is None:
            return
        if self._sounds is None or self._sound_volume != volume:
            self._sounds = self._sound_provider(volume)
            self._sound_volume = volume
        p = self._sounds.get(kind)
        if p:
            from os_layer.posix_sound import play_wav
            play_wav(p)

    # ------------------------------------------------------------------ الاختصار العام
    def register_hotkey(self, combo: str, callback) -> bool:
        """XGrabKey على اتصال X خاص بخيط مستقل (لا يتأثر بانشغال الواجهة). لا يقرأ أي مفتاح آخر."""
        from Xlib import X, XK, display
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        mods_map = {"ctrl": X.ControlMask, "shift": X.ShiftMask, "alt": X.Mod1Mask, "win": X.Mod4Mask}
        mods = 0
        key = None
        for p in parts:
            if p in mods_map:
                mods |= mods_map[p]
            else:
                key = p
        if key is None:
            return False
        try:
            d = display.Display(self._display_name)
            code = d.keysym_to_keycode(XK.string_to_keysym(keysym_name(key)))
        except Exception:  # noqa: BLE001
            return False
        if not code:
            return False
        from Xlib import error
        root = d.screen().root
        # نفس الاختصار مع Caps Lock وNum Lock مفعّلين أو لا
        variants = [mods, mods | X.LockMask, mods | X.Mod2Mask, mods | X.LockMask | X.Mod2Mask]
        refused = error.CatchError(error.BadAccess)
        for m in variants:
            root.grab_key(code, m, True, X.GrabModeAsync, X.GrabModeAsync, onerror=refused)
        d.sync()
        if refused.get_error():
            # برنامج آخر يملك هذا الاختصار: نقول ذلك بصراحة (كما على Windows) بدل وعد كاذب
            log.warning("الاختصار %s محجوز لبرنامج آخر", combo)
            for m in variants:
                root.ungrab_key(code, m)
            d.close()
            return False
        stop = threading.Event()

        def loop():
            while not stop.is_set():
                if d.pending_events():
                    ev = d.next_event()
                    if ev.type == X.KeyPress and ev.detail == code:
                        try:
                            callback()
                        except Exception:  # noqa: BLE001
                            log.exception("فشل تنفيذ الاختصار")
                else:
                    time.sleep(0.05)
            for m in variants:
                root.ungrab_key(code, m)
            d.close()

        t = threading.Thread(target=loop, daemon=True, name=f"hotkey-{combo}")
        t.start()
        self._hotkeys.append((t, stop))
        return True

    def seconds_since_input(self) -> float | None:
        try:
            from Xlib.ext import screensaver
            with self._lock:
                return screensaver.query_info(self.root).idle / 1000.0
        except Exception:  # noqa: BLE001 - خادم بلا MIT-SCREEN-SAVER
            return None

    # ------------------------------------------------------------------ الإمكانات الفعلية
    def capabilities(self) -> set[str]:
        """ما ينفّذه الصنف، ناقص ما تغيب أداته عن هذا الجهاز (فتختفي أوامره بدل أن تفشل)."""
        caps = super().capabilities()
        if not shutil.which("brightnessctl"):
            caps -= {"brightness", "set_brightness", "current_brightness"}
        if not shutil.which("xset"):
            caps.discard("monitor_power")
        if not shutil.which("gsettings"):
            caps -= {"set_dark_mode", "dark_mode_enabled"}
        if not (shutil.which("wpctl") or shutil.which("pactl")):
            caps.discard("toggle_microphone_mute")
        if not shutil.which("gio"):
            caps.discard("empty_recycle_bin")
        if "MIT-SCREEN-SAVER" not in self.d.list_extensions():
            caps.discard("seconds_since_input")
        # لا إنشاء/حذف أسطح مكتب ولا أوضاع عرض: غير معيارية في EWMH
        return caps & set(OPTIONAL)

    # ------------------------------------------------------------------ دورة الحياة
    def close(self) -> None:
        for _t, stop in self._hotkeys:
            stop.set()
        self._hotkeys.clear()

    def hard_exit(self, code: int) -> None:
        os._exit(code)
