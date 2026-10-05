"""منطق المعايرة (بلا كاميرا ولا واجهة): من عينات اليد إلى عتبات القرص ومنطقة التحكم.

قبلها مرحلة تحضير قصيرة في الواجهة (scene_hints): الإضاءة، عكس الضوء، المسافة.

الخطوات (أقل من دقيقة):
  open  : اليد مفتوحة أمام الكاميرا ← نسبة ظهور اليد، الإضاءة
  pinch : الإبهام يلمس السبابة ← مسافة القرص "المغلق" لهذه اليد
  point : السبابة ممدودة والإبهام بعيد ← المسافة "المفتوحة"
  zone  : تحريك السبابة إلى زوايا المنطقة المريحة ← منطقة التحكم
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.events import CalibrationSample

STEPS: list[tuple[str, float]] = [("open", 3.0), ("pinch", 3.0), ("point", 3.0), ("zone", 7.0)]
SETTLE_S = 0.8           # بداية كل خطوة: وقت لتغيير الوضعية (لا تُحتسب العينات)
MIN_SAMPLES = 8

# حدود ظروف التصوير (انظر scene_hints)
DARK_LEVEL = 50.0        # متوسط سطوع الصورة 0..255
OVEREXPOSED_FRAC = 0.12  # أكثر من 12% من الصورة محترق = مصدر ضوء خلفك غالباً
BACKLIT_RATIO = 0.65     # اليد أغمق بكثير من بقية الصورة
TOO_CLOSE = 0.70         # اليد تملأ 70% من ارتفاع الصورة (أقل من ~30 سم)
TOO_FAR = 0.15           # اليد أصغر من 15% (أبعد من ~1.5 م)
HINT_ORDER = ("dark", "backlight", "too_close", "too_far")


def scene_hints(sample: CalibrationSample) -> list[str]:
    """مشكلات التصوير في عينة واحدة، بالأهمية: dark | backlight | too_close | too_far."""
    hints = []
    if sample.brightness < DARK_LEVEL:
        hints.append("dark")
    backlit = sample.overexposed > OVEREXPOSED_FRAC or (
        sample.has_hand and sample.brightness > 90
        and 0 < sample.hand_brightness < BACKLIT_RATIO * sample.brightness)
    if backlit:
        hints.append("backlight")
    if sample.has_hand and sample.hand_size > TOO_CLOSE:
        hints.append("too_close")
    elif sample.has_hand and 0 < sample.hand_size < TOO_FAR:
        hints.append("too_far")
    return hints


def dominant_hints(samples: list[CalibrationSample], share: float = 0.5) -> list[str]:
    """التلميحات الظاهرة في أكثر من share من العينات (يتجاهل الومضات العابرة)."""
    if not samples:
        return []
    counts = {h: 0 for h in HINT_ORDER}
    for s in samples:
        for h in scene_hints(s):
            counts[h] += 1
    return [h for h in HINT_ORDER if counts[h] > share * len(samples)]


@dataclass
class CalibrationResult:
    pinch_enter: float | None = None
    pinch_exit: float | None = None
    zone: tuple[float, float, float, float] | None = None
    detection: float = 0.0          # نسبة الإطارات التي ظهرت فيها اليد
    brightness: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.pinch_enter is not None or self.zone is not None

    def config_changes(self) -> dict:
        """التغييرات لملف user_data/config.yaml."""
        vision: dict = {}
        if self.pinch_enter is not None:
            vision["tuning"] = {"pinch_enter": round(self.pinch_enter, 3),
                                "pinch_exit": round(self.pinch_exit, 3)}
        if self.zone is not None:
            vision["control_zone"] = [round(v, 3) for v in self.zone]
        return {"vision": vision} if vision else {}


class Calibrator:
    def __init__(self):
        self.samples: dict[str, list[CalibrationSample]] = {name: [] for name, _ in STEPS}

    def add(self, step: str, sample: CalibrationSample, t_in_step: float) -> None:
        if t_in_step >= SETTLE_S and step in self.samples:
            self.samples[step].append(sample)

    def result(self) -> CalibrationResult:
        res = CalibrationResult()
        allv = [s for v in self.samples.values() for s in v]
        if not allv:
            res.warnings.append("hand_rarely_seen")
            return res
        res.detection = sum(s.has_hand for s in allv) / len(allv)
        res.brightness = float(np.median([s.brightness for s in allv]))
        if res.detection < 0.6:
            res.warnings.append("hand_rarely_seen")
        hints = dominant_hints(allv)
        if "dark" in hints:
            res.warnings.append("too_dark")
        res.warnings += [h for h in hints if h != "dark"]

        def vals(step, attr):
            return [getattr(s, attr) for s in self.samples[step] if s.has_hand]

        closed = vals("pinch", "pinch")
        opened = vals("point", "pinch") + vals("open", "pinch")
        if len(closed) >= MIN_SAMPLES and len(opened) >= MIN_SAMPLES:
            c = float(np.percentile(closed, 75))    # أسوأ القرص (الأوسع) يجب أن يُلتقط
            o = float(np.percentile(opened, 25))    # أقرب مسافة "مفتوحة" يجب ألا تُعد قرصاً
            gap = o - c
            if gap >= 0.2:
                enter = min(max(c + 0.35 * gap, 0.08), 0.5)
                exit_ = min(max(c + 0.6 * gap, enter + 0.05), 0.85)
                res.pinch_enter, res.pinch_exit = enter, exit_
            else:
                res.warnings.append("pinch_unclear")
        else:
            res.warnings.append("pinch_unclear")

        xs, ys = vals("zone", "tip_x"), vals("zone", "tip_y")
        if len(xs) >= MIN_SAMPLES:
            x0, x1 = np.percentile(xs, [3, 97])
            y0, y1 = np.percentile(ys, [3, 97])
            # تقليص 8% من كل جانب: الوصول لحافة الشاشة لا يتطلب مدّ اليد لأقصى حد
            mx, my = (x1 - x0) * 0.08, (y1 - y0) * 0.08
            zone = (float(x0 + mx), float(y0 + my), float(x1 - mx), float(y1 - my))
            if zone[2] - zone[0] >= 0.15 and zone[3] - zone[1] >= 0.12:
                res.zone = tuple(min(max(v, 0.0), 1.0) for v in zone)
            else:
                res.warnings.append("zone_small")
        else:
            res.warnings.append("zone_small")
        return res
