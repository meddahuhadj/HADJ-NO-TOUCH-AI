"""ما هو مثبّت فعلاً: نسخة "كاملة" (3 لغات + Whisper) أو "خفيفة" (فرنسي/إنجليزي، إملاء Vosk).

قاعدة كود واحدة للنسختين: لا شيء هنا يعتمد على اسم النسخة، بل على الملفات الموجودة.
حزمة العربية = نسخ models/vosk/ar داخل مجلد التطبيق، فتظهر اللغة تلقائياً دون أي إعداد.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from core import paths

LANGUAGES = ("ar", "en", "fr")
PREFERRED_FALLBACK = ("fr", "en", "ar")


def available_languages(models_dir: Path | None = None) -> list[str]:
    d = (models_dir or paths.models_dir()) / "vosk"
    return [lang for lang in LANGUAGES if (d / lang).is_dir()]


def whisper_models(models_dir: Path | None = None) -> list[str]:
    d = (models_dir or paths.models_dir()) / "whisper"
    return sorted(p.name for p in d.iterdir() if (p / "model.bin").exists()) if d.is_dir() else []


def whisper_available(models_dir: Path | None = None) -> bool:
    """النموذج وحده لا يكفي: النسخة الخفيفة لا تحمل مكتبة faster_whisper."""
    return bool(whisper_models(models_dir)) and importlib.util.find_spec("faster_whisper") is not None


def fallback_language(wanted: str, available: list[str]) -> str:
    """اللغة المطلوبة إن وُجد نموذجها، وإلا أول لغة متاحة (الفرنسية ثم الإنجليزية)."""
    if wanted in available or not available:
        return wanted
    return next(lang for lang in PREFERRED_FALLBACK if lang in available)


def name() -> str:
    """للسجلات وواجهة "حول": full | lite | custom."""
    langs = available_languages()
    if whisper_available() and len(langs) == len(LANGUAGES):
        return "full"
    if not whisper_models() and "ar" not in langs:
        return "lite"
    return "custom"
