"""مخطط الإعدادات مع التحقق من القيم (pydantic)."""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

Lang = Literal["ar", "en", "fr"]


class SpeechConfig(BaseModel):
    language: Lang = "ar"
    wake_words: dict[str, list[str]] = Field(
        default_factory=lambda: {"ar": ["حاسوب"], "en": ["computer"], "fr": ["ordinateur"]}
    )
    continuous_listening: bool = False
    wake_timeout_s: float = Field(5.0, ge=1, le=60)
    followup_s: float = Field(6.0, ge=0, le=60)
    match_threshold: int = Field(80, ge=50, le=100)
    use_grammar: Literal["auto", "on", "off"] = "auto"
    input_device: Optional[Union[int, str]] = None
    vad_aggressiveness: int = Field(2, ge=0, le=3)
    silence_ms: int = Field(600, ge=200, le=3000)
    max_utterance_s: float = Field(12.0, ge=2, le=60)


class SafetyConfig(BaseModel):
    emergency_hotkey: str = "ctrl+alt+shift+p"
    confirm_dangerous: bool = True
    confirm_timeout_s: float = Field(8.0, ge=2, le=60)


class FeedbackConfig(BaseModel):
    sounds: bool = True


class UIConfig(BaseModel):
    ui_language: Lang = "ar"
    font_scale: float = Field(1.0, ge=0.75, le=3.0)
    high_contrast: bool = False
    overlay: bool = True
    overlay_seconds: float = Field(4.0, ge=1, le=30)
    show_panel: bool = True   # لوحة التحكم عند التشغيل


class ActionsConfig(BaseModel):
    scroll_amount: int = Field(5, ge=1, le=50)
    volume_step: int = Field(5, ge=1, le=50)


class GestureTuning(BaseModel):
    pinch_enter: float = Field(0.25, ge=0.05, le=0.6)   # مسافة الإبهام-السبابة / حجم اليد لبدء القرص
    pinch_exit: float = Field(0.38, ge=0.1, le=0.9)     # لإنهائه (أكبر = تخلف hysteresis)
    drag_hold_ms: int = Field(400, ge=100, le=3000)     # قرص مستمر أطول من هذا ← سحب
    drag_move: float = Field(0.04, ge=0.005, le=0.3)    # أو حركة أكبر من هذا (نسبة من عرض الصورة) ← سحب
    rewind_ms: int = Field(180, ge=0, le=500)           # النقر في موضع المؤشر قبل بدء القرص بهذه المدة
    fist_ms: int = Field(600, ge=100, le=5000)
    palm_resume_ms: int = Field(1000, ge=200, le=5000)
    palm_long_ms: int = Field(2000, ge=500, le=10000)
    lost_ms: int = Field(400, ge=100, le=3000)          # فقدان اليد أطول من هذا ← تحرير أي زر مضغوط
    scroll_step: float = Field(0.035, ge=0.005, le=0.3)  # حركة الإصبعين (نسبة من الصورة) لكل نقرة عجلة
    scroll_settle_ms: int = Field(150, ge=0, le=2000)   # ثبات وضعية الإصبعين قبل بدء التمرير
    scroll_invert: bool = False                         # true = اليد للأعلى تمرّر للأسفل (مثل السحب باللمس)
    swipe_dist: float = Field(0.22, ge=0.05, le=0.8)    # مسافة سحب اليد المفتوحة أفقياً
    swipe_ms: int = Field(450, ge=100, le=2000)         # ...خلال هذه المدة
    swipe_max_dy: float = Field(0.12, ge=0.01, le=0.5)  # أقصى انحراف عمودي مسموح
    swipe_cooldown_ms: int = Field(1000, ge=100, le=5000)
    zoom_step: float = Field(0.15, ge=0.03, le=1.0)     # تغيّر نسبي في المسافة بين اليدين لكل خطوة تكبير


class VisionConfig(BaseModel):
    enabled: bool = True
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    preview: bool = False
    hand: Literal["any", "right", "left"] = "any"
    # منطقة التحكم داخل صورة الكاميرا (x0, y0, x1, y1) بنسب 0..1 ← تُطابق كامل الشاشة
    control_zone: tuple[float, float, float, float] = (0.2, 0.15, 0.8, 0.75)
    min_cutoff: float = Field(1.0, gt=0, le=20)
    beta: float = Field(0.01, ge=0, le=1)
    min_detection_confidence: float = Field(0.45, ge=0.1, le=1)
    min_tracking_confidence: float = Field(0.40, ge=0.1, le=1)
    tuning: GestureTuning = Field(default_factory=GestureTuning)
    # إيماءة ← إجراء (أي إجراء من قائمة الإجراءات، أو none للتعطيل)
    bindings: dict[str, str] = Field(default_factory=lambda: {
        "pinch_tap": "click",
        "middle_pinch_tap": "right_click",
        "fist_hold": "app.pause",
        "palm_hold_long": "show_desktop",
        "two_scroll": "scroll",
        "swipe_right": "switch_window",
        "swipe_left": "switch_window_prev",
        "zoom_in": "zoom_in",
        "zoom_out": "zoom_out",
    })


class DictationConfig(BaseModel):
    engine: Literal["whisper", "vosk"] = "whisper"
    whisper_model: str = "small"          # مجلد داخل models/whisper/
    threads: int = Field(0, ge=0, le=32)  # 0 = تلقائي
    beam_size: int = Field(1, ge=1, le=5)


class GridConfig(BaseModel):
    timeout_s: float = Field(30.0, ge=5, le=600)


class AppConfig(BaseModel):
    speech: SpeechConfig = Field(default_factory=SpeechConfig)
    dictation: DictationConfig = Field(default_factory=DictationConfig)
    grid: GridConfig = Field(default_factory=GridConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
    app_aliases: dict[str, str] = Field(default_factory=dict)
