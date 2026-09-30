"""اختيار تنفيذ طبقة النظام حسب نظام التشغيل الحالي."""
from __future__ import annotations

import sys

from os_layer.base import OSBackend


def create_backend() -> OSBackend:
    if sys.platform == "win32":
        from os_layer.windows.backend import WindowsBackend
        return WindowsBackend()
    raise NotImplementedError(
        f"النظام {sys.platform} غير مدعوم بعد. نفّذ os_layer.base.OSBackend لإضافته.")
