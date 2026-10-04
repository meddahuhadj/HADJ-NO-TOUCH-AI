"""اختيار تنفيذ طبقة النظام حسب نظام التشغيل الحالي."""
from __future__ import annotations

import sys

from os_layer.base import OSBackend


def _app_sounds(volume: int):
    """أصوات التطبيق (في user_data/sounds). الاستيراد هنا فقط: المكتبة نفسها لا تعرف التطبيق."""
    from core import paths
    from core.sounds import ensure_sounds
    return ensure_sounds(paths.user_dir() / "sounds", volume)


def create_backend() -> OSBackend:
    if sys.platform == "win32":
        from os_layer.windows.backend import WindowsBackend
        return WindowsBackend(sound_provider=_app_sounds)
    raise NotImplementedError(
        f"النظام {sys.platform} غير مدعوم بعد. نفّذ os_layer.base.OSBackend لإضافته.")
