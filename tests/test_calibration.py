"""اختبارات منطق المعايرة بعينات اصطناعية."""
import random

import pytest

from core.events import CalibrationSample
from vision.calibration import SETTLE_S, Calibrator


def feed(cal, step, n, make, t0=SETTLE_S):
    for i in range(n):
        cal.add(step, make(i), t0 + i * 0.066)


def good_session(rng=random.Random(0), bright=120.0, visible=1.0, closed=0.12, opened=0.9,
                 zone=(0.3, 0.25, 0.7, 0.65)):
    cal = Calibrator()

    def s(pinch, x=0.5, y=0.5):
        seen = rng.random() < visible
        return CalibrationSample(seen, pinch + rng.uniform(-0.03, 0.03), x, y, bright)

    feed(cal, "open", 30, lambda i: s(opened + 0.3))
    feed(cal, "pinch", 30, lambda i: s(closed))
    feed(cal, "point", 30, lambda i: s(opened))
    x0, y0, x1, y1 = zone
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def zone_sample(i):
        cx, cy = corners[(i // 25) % 4]
        nx, ny = corners[(i // 25 + 1) % 4]
        f = (i % 25) / 25
        return s(opened, cx + (nx - cx) * f, cy + (ny - cy) * f)
    feed(cal, "zone", 100, zone_sample)
    return cal


def test_good_session_produces_thresholds_and_zone():
    r = good_session().result()
    assert r.ok and not r.warnings
    assert 0.12 < r.pinch_enter < r.pinch_exit < 0.9
    # العتبة بين المغلق والمفتوح، وأقرب للمغلق
    assert r.pinch_enter < (0.12 + 0.9) / 2
    x0, y0, x1, y1 = r.zone
    assert 0.3 < x0 < 0.36 and 0.64 < x1 < 0.7      # مقلّصة قليلاً من الداخل
    assert 0.25 < y0 < 0.31 and 0.59 < y1 < 0.65
    ch = r.config_changes()["vision"]
    assert set(ch) == {"tuning", "control_zone"} and len(ch["control_zone"]) == 4


def test_settle_period_samples_are_ignored():
    cal = Calibrator()
    cal.add("pinch", CalibrationSample(True, 5.0, brightness=100), 0.2)
    assert cal.samples["pinch"] == []


def test_unclear_pinch_keeps_threshold_but_saves_zone():
    r = good_session(closed=0.5, opened=0.6).result()
    assert r.pinch_enter is None and "pinch_unclear" in r.warnings
    assert r.zone is not None and r.ok
    assert "tuning" not in r.config_changes()["vision"]


def test_tiny_zone_rejected():
    r = good_session(zone=(0.48, 0.48, 0.52, 0.52)).result()
    assert r.zone is None and "zone_small" in r.warnings


def test_dark_and_hand_rarely_seen_warnings():
    r = good_session(bright=30, visible=0.4).result()
    assert "too_dark" in r.warnings and "hand_rarely_seen" in r.warnings


def test_no_hand_at_all_fails():
    cal = Calibrator()
    for step in ("open", "pinch", "point", "zone"):
        feed(cal, step, 20, lambda i: CalibrationSample(False, brightness=90))
    r = cal.result()
    assert not r.ok and r.detection == 0
    assert r.config_changes() == {}


@pytest.mark.parametrize("closed,opened", [(0.02, 0.3), (0.3, 1.5)])
def test_thresholds_are_clamped(closed, opened):
    r = good_session(closed=closed, opened=opened).result()
    assert 0.08 <= r.pinch_enter <= 0.5
    assert r.pinch_enter + 0.05 <= r.pinch_exit <= 0.85


def test_calibrated_thresholds_work_with_engine():
    """العتبات الناتجة تُطبَّق فعلاً في المحرك: قرص يد "واسعة" يُكتشف بعد المعايرة."""
    from config.schema import GestureTuning
    from handsynth import make_hand
    from vision.gestures import classify
    hand = make_hand("pinch")
    base = classify(hand, 0.25, 0.38, aspect=1.0)
    # يد يقرص صاحبها بشكل أوسع (مسافة 0.3): العتبة الافتراضية لا تلتقطه
    wide = base.pinch_index + 0.25
    r = good_session(closed=wide, opened=1.0).result()
    t = GestureTuning(pinch_enter=r.pinch_enter, pinch_exit=r.pinch_exit)
    assert wide > 0.25 and wide < t.pinch_enter
