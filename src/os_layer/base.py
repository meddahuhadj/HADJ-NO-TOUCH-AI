"""الواجهة المجردة لطبقة نظام التشغيل.

كل ما يلمس النظام يمر من هنا. لدعم Linux/macOS لاحقاً يكفي تنفيذ هذه الواجهة
في os_layer/linux أو os_layer/macos وتسجيلها في factory.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AppEntry:
    name: str        # الاسم المعروض (مثل "Google Chrome")
    target: str      # ما يُمرَّر للتشغيل: مسار، أو AppID، أو URI
    kind: str = "path"   # path | appid | uri | command


@dataclass
class WindowInfo:
    """نافذة مفتوحة يمكن التعرّف عليها بالعنوان."""
    hwnd: int
    title: str
    pid: int = 0
    minimized: bool = False
    monitor: int = 0


@dataclass
class MonitorInfo:
    """شاشة فعلية (منفصلة عن سطح المكتب الافتراضي)."""
    index: int
    name: str
    rect: tuple[int, int, int, int]   # left, top, width, height
    primary: bool = False


class OSBackend(ABC):
    # ---- لوحة المفاتيح ----
    @abstractmethod
    def key(self, key: str, times: int = 1) -> None: ...

    @abstractmethod
    def hotkey(self, *keys: str) -> None: ...

    @abstractmethod
    def type_text(self, text: str) -> None: ...

    # ---- الفأرة ----
    @abstractmethod
    def mouse_position(self) -> tuple[int, int]: ...

    @abstractmethod
    def mouse_move(self, x: int, y: int) -> None: ...

    @abstractmethod
    def mouse_button(self, button: str = "left", action: str = "click", count: int = 1) -> None:
        """action: click | down | up"""

    @abstractmethod
    def scroll(self, notches: int, horizontal: bool = False, ctrl: bool = False) -> None:
        """notches > 0 للأعلى/لليمين. ctrl=True: Ctrl+عجلة (تكبير/تصغير)."""

    @abstractmethod
    def screen_rect(self) -> tuple[int, int, int, int]:
        """(left, top, width, height) لسطح المكتب الافتراضي (كل الشاشات)."""

    def release_all(self) -> None:
        """تحرير أي زر أو مفتاح مضغوط (يُستدعى عند الإيقاف الطارئ)."""

    # ---- النوافذ ----
    @abstractmethod
    def close_window(self) -> bool: ...

    @abstractmethod
    def minimize_window(self) -> bool: ...

    @abstractmethod
    def maximize_window(self) -> bool: ...

    @abstractmethod
    def switch_window(self) -> None: ...

    @abstractmethod
    def show_desktop(self) -> None: ...

    @abstractmethod
    def active_window_title(self) -> str: ...

    # ---- النوافذ: التحكّم الدقيق ----
    # كلها اختيارية (قيمة افتراضية صادقة كـ"غير مدعوم") حتى لا تتعطّل أي
    # خلفية نظام أخرى عند إضافة هذه الإمكانات تدريجياً.
    def list_windows(self) -> list[WindowInfo]:
        """كل النوافذ المرئية التي لها عنوان (بلا أشرطة النظام ومربعات الحوار)."""
        return []

    def focus_window(self, query: str) -> bool:
        """يجلب نافذة عنوانها يحتوي على `query` إلى الأمام."""
        return False

    def move_window(self, dx: int, dy: int) -> bool:
        """يزيح النافذة النشطة بمقدار نسبي (بكسل)."""
        return False

    def resize_window(self, dw: int, dh: int) -> bool:
        """يغيّر حجم النافذة النشطة بمقدار نسبي (بكسل)."""
        return False

    def set_window_rect(self, x: int, y: int, width: int, height: int) -> bool:
        """يضبط النافذة النشطة على إحداثيات مطلقة."""
        return False

    def center_window(self) -> bool:
        return False

    def snap_window(self, position: str) -> bool:
        """position: left | right | top | bottom | topleft | topright | bottomleft
        | bottomright | maximize | restore"""
        return False

    def set_always_on_top(self, enabled: bool) -> bool:
        return False

    # ---- الشاشات ----
    def list_monitors(self) -> list[MonitorInfo]:
        return []

    def move_window_to_monitor(self, index: int) -> bool:
        """ينقل النافذة النشطة إلى الشاشة رقم `index` (0 = الأساسية)."""
        return False

    def set_display_mode(self, mode: str) -> bool:
        """mode: extend | duplicate | next"""
        return False

    def switch_virtual_desktop(self, direction: str) -> bool:
        """direction: left | right"""
        return False

    def new_virtual_desktop(self) -> bool:
        return False

    def close_virtual_desktop(self) -> bool:
        return False

    # ---- العرض والصوت ----
    def brightness(self, change: str, steps: int = 10) -> bool:
        """change: up | down. يعمل على الشاشات الداخلية (أجهزة لوحية) غالباً."""
        return False

    def set_brightness(self, percent: int) -> bool:
        return False

    def current_brightness(self) -> int | None:
        """السطوع الحالي 0..100، أو None إن لم تدعمه الشاشة (شاشات مكتبية)."""
        return None

    def monitor_power(self, on: bool) -> bool:
        """إطفاء/تشغيل كل الشاشات (يوقظها أي إدخال)."""
        return False

    def set_dark_mode(self, enabled: bool) -> bool:
        """الوضع الداكن/الفاتح لتطبيقات النظام."""
        return False

    def dark_mode_enabled(self) -> bool | None:
        """الوضع الداكن الحالي، أو None إن تعذّرت القراءة."""
        return None

    def toggle_microphone_mute(self) -> bool:
        """يبدّل كتم الميكروفون.

        التبديل لا الضبط: واجهة Win32 لا تكشف حالة الكتم بلا مكتبة
        إضافية (pycaw)، فنبقيها أمراً واحداً صريحاً.
        """
        return False

    # ---- النظام ----
    @abstractmethod
    def volume(self, change: str, steps: int = 1) -> None:
        """change: up | down | mute"""

    @abstractmethod
    def lock_screen(self) -> None: ...

    @abstractmethod
    def screenshot(self) -> None: ...

    @abstractmethod
    def power(self, action: str) -> None:
        """action: shutdown | restart"""

    @abstractmethod
    def open_search(self) -> None: ...

    @abstractmethod
    def launch(self, entry: AppEntry) -> None: ...

    @abstractmethod
    def list_apps(self) -> list[AppEntry]: ...

    def play_sound(self, kind: str, volume: int = 70) -> None:
        """kind: ok | error | wake | confirm | pause | resume | hand | hand_lost. اختياري."""

    def open_path(self, path: str) -> None:
        """يفتح ملفاً أو مجلداً أو رابطاً محلياً بالتطبيق الافتراضي (macOS: open، Linux: xdg-open)."""
        import subprocess
        import sys
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])

    def empty_recycle_bin(self) -> bool:
        return False

    def capabilities(self) -> set[str]:
        """الإمكانات الاختيارية التي ينفّذها هذا النظام فعلاً (طريقة معاد تعريفها في الصنف الفرعي).
        التطبيق يُخفي الأوامر التي تحتاج إمكانية غير موجودة بدل أن يقبلها ثم يفشل."""
        return {name for name in OPTIONAL if getattr(type(self), name) is not getattr(OSBackend, name)}

    def register_hotkey(self, combo: str, callback) -> bool:
        """اختصار عام للنظام. اختياري؛ يرجع False إن لم يكن مدعوماً."""
        return False

    def seconds_since_input(self) -> float | None:
        """الثواني منذ آخر حركة فأرة/لوحة مفاتيح (None = غير مدعوم)."""
        return None

    def prepare_process(self) -> None:
        """إعدادات تُطبَّق مرة عند بدء كل عملية (مثل وعي DPI)."""

    def close(self) -> None:
        """تحرير موارد الطبقة (خيوط الاختصارات...) قبل الخروج."""

    def hard_exit(self, code: int) -> None:
        """الخروج النهائي من العملية بعد انتهاء التنظيف."""
        import os
        os._exit(code)


# طرق لها تنفيذ افتراضي "غير مدعوم": نظام جديد يستطيع تركها، فتختفي الأوامر المعتمدة عليها
OPTIONAL = ("list_windows", "focus_window", "move_window", "resize_window", "set_window_rect",
            "center_window", "snap_window", "set_always_on_top", "list_monitors",
            "move_window_to_monitor", "set_display_mode", "switch_virtual_desktop",
            "new_virtual_desktop", "close_virtual_desktop", "brightness", "set_brightness",
            "current_brightness", "monitor_power", "set_dark_mode", "dark_mode_enabled",
            "toggle_microphone_mute", "empty_recycle_bin", "register_hotkey", "seconds_since_input",
            "play_sound")
