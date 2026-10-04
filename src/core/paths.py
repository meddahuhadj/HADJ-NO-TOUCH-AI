"""مسارات التطبيق. النسخة محمولة (portable): كل شيء بجانب الملف التنفيذي."""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """ملفات مضمّنة للقراءة فقط (الإعدادات الافتراضية)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return Path(__file__).resolve().parents[1]


def help_dir() -> Path:
    """صفحة المساعدة المحلية (help/index.html): داخل الكود، أو بجانب الملف التنفيذي في النسخة المجمّدة."""
    for d in (resource_dir() / "help", app_root() / "help"):
        if (d / "index.html").exists():
            return d
    return resource_dir() / "help"


def models_dir() -> Path:
    return app_root() / "models"


def user_dir() -> Path:
    d = app_root() / "user_data"
    d.mkdir(parents=True, exist_ok=True)
    return d
