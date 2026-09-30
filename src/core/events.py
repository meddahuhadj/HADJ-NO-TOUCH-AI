"""الرسائل المتبادلة بين العمليات عبر الطوابير. كلها قابلة للتسلسل (pickle)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpeechEvent:
    """عبارة منطوقة اكتمل التعرف عليها."""
    text: str                 # نتيجة التعرف المقيّد بالقواعد (أو الحر إن لم تتوفر)
    free_text: str = ""       # نتيجة التعرف الحر (لأوامر فيها نص حر مثل: ابحث عن ...)
    lang: str = "ar"
    confidence: float = 1.0
    seg_id: int = 0           # يربط العبارة بنتيجة الإملاء التي تصل لاحقاً


@dataclass
class DictationEvent:
    """نص الإملاء لعبارة (من Whisper أو Vosk)، يصل بعد SpeechEvent لنفس seg_id."""
    text: str
    seg_id: int
    lang: str = "ar"
    engine: str = "whisper"
    seconds: float = 0.0      # زمن التحويل (للتشخيص)


@dataclass
class CalibrationSample:
    """عينة من عملية الرؤية أثناء المعايرة (بلا صور: أرقام فقط)."""
    has_hand: bool
    pinch: float = 0.0        # مسافة الإبهام-السبابة / حجم اليد
    tip_x: float = 0.0        # طرف السبابة في الصورة المعكوسة (0..1)
    tip_y: float = 0.0
    brightness: float = 0.0
    pose: str = "none"


@dataclass
class PartialSpeechEvent:
    text: str


@dataclass
class GestureEvent:
    name: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusEvent:
    """حالة عملية فرعية: source = audio|vision ، state = starting|ready|listening|error|stopped."""
    source: str
    state: str
    detail: str = ""


@dataclass
class ControlMessage:
    """من العملية الرئيسية إلى العمليات الفرعية."""
    kind: str                 # set_language | set_grammar | shutdown | ...
    payload: dict[str, Any] = field(default_factory=dict)
