"""توحيد النص قبل المطابقة: إزالة التشكيل، توحيد الهمزات، التاء المربوطة، ولكنات الفرنسية."""
from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_PUNCT = re.compile(r"[^\w\s{}]", re.UNICODE)
_SPACES = re.compile(r"\s+")

_CHAR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و",
    "ة": "ه",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "،": " ", "؟": " ", "؛": " ",
    "œ": "oe", "æ": "ae",
})


def _strip_accents(text: str) -> str:
    """fenêtre ← fenetre، déplace ← deplace (الحروف المركّبة تُفكَّك وتُحذف علاماتها)."""
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if unicodedata.category(c) != "Mn"))


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", text or "")
    text = text.translate(_CHAR_MAP).lower()
    text = _strip_accents(text)
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def tokens(text: str) -> list[str]:
    return normalize(text).split()


_GRAMMAR_DROP = re.compile(r"[^\w\s'\-]", re.UNICODE)


def grammar_form(text: str) -> str:
    """الشكل المرسل لقاموس Vosk المقيّد: أحرف صغيرة مع الإبقاء على اللكنات والفواصل العليا،
    لأن كلمات النموذج الفرنسي بلكناتها ("dictée"، "l'ordinateur") وتُحذف إن لم تطابق حرفياً."""
    text = (text or "").replace("’", "'").lower()
    text = re.sub(r"\{\w+\}", " ", text)
    text = _GRAMMAR_DROP.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
