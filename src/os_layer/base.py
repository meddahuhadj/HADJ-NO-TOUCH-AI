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

    def play_sound(self, kind: str) -> None:
        """kind: ok | error | wake | confirm. اختياري."""

    def register_hotkey(self, combo: str, callback) -> bool:
        """اختصار عام للنظام. اختياري؛ يرجع False إن لم يكن مدعوماً."""
        return False

    def prepare_process(self) -> None:
        """إعدادات تُطبَّق مرة عند بدء كل عملية (مثل وعي DPI)."""

    def close(self) -> None:
        """تحرير موارد الطبقة (خيوط الاختصارات...) قبل الخروج."""

    def hard_exit(self, code: int) -> None:
        """الخروج النهائي من العملية بعد انتهاء التنظيف."""
        import os
        os._exit(code)
