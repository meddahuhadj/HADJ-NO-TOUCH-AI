"""المعايرة الموجّهة: تلميحات الإضاءة والمسافة، مرحلة التحضير، والرسوم المتحركة."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from core.events import CalibrationSample  # noqa: E402
from vision.calibration import STEPS, dominant_hints, scene_hints  # noqa: E402


def S(hand=True, bright=120.0, size=0.4, over=0.0, hand_b=None, pinch=0.9):
    return CalibrationSample(hand, pinch, 0.5, 0.5, bright, hand_size=size if hand else 0.0,
                             overexposed=over, hand_brightness=bright if hand_b is None else hand_b)


# ---------------- التلميحات ----------------
@pytest.mark.parametrize("sample,expected", [
    (S(), []),
    (S(bright=30), ["dark"]),
    (S(over=0.3), ["backlight"]),
    (S(bright=150, hand_b=60), ["backlight"]),        # يد مظلمة أمام خلفية مضيئة
    (S(size=0.85), ["too_close"]),
    (S(size=0.08), ["too_far"]),
    (S(hand=False), []),                              # بلا يد: لا حكم على المسافة
    (S(hand=False, over=0.4), ["backlight"]),          # النافذة تُكشف حتى دون يد
    (S(bright=30, size=0.9), ["dark", "too_close"]),
])
def test_scene_hints(sample, expected):
    assert scene_hints(sample) == expected


def test_dominant_hints_ignore_flicker():
    samples = [S()] * 10 + [S(size=0.9)] * 3
    assert dominant_hints(samples) == []
    assert dominant_hints([S()] * 3 + [S(size=0.9)] * 10) == ["too_close"]
    assert dominant_hints([]) == []


def test_calibration_result_reports_scene_warnings():
    from vision.calibration import SETTLE_S, Calibrator
    cal = Calibrator()
    for step, _ in STEPS:
        for i in range(20):
            cal.add(step, S(over=0.25, size=0.1), SETTLE_S + i * 0.05)
    r = cal.result()
    assert "backlight" in r.warnings and "too_far" in r.warnings
    assert "too_dark" not in r.warnings


def test_old_samples_without_scene_stats_give_no_new_warnings():
    # عينات من نسخة سابقة (بلا حجم يد ولا احتراق) لا تُطلق تحذيرات خاطئة
    assert scene_hints(CalibrationSample(True, 0.2, 0.5, 0.5, 120)) == []


def test_scene_stats_on_synthetic_frame():
    from vision.worker import scene_stats
    frame = np.full((480, 640, 3), 110, np.uint8)
    frame[:120] = 255                                  # نافذة مضيئة في الربع العلوي
    frame[240:400, 280:400] = 40                       # منطقة اليد مظلمة
    lms = np.array([[280 / 640, 240 / 480, 0], [400 / 640, 400 / 480, 0]] * 11, np.float32)[:21]
    over, hand_b, size = scene_stats(frame, lms, 640 / 480)
    assert 0.2 < over < 0.3
    assert hand_b < 60
    assert size == pytest.approx(max(120 / 640 * 640 / 480, 160 / 480), abs=0.01)
    over2, hb2, size2 = scene_stats(frame, None, 640 / 480)
    assert over2 == over and hb2 == 0.0 and size2 == 0.0


# ---------------- المعالج ----------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def wizard(qapp, monkeypatch):
    from ui import calibration_wizard as cw
    from ui.i18n import Tr
    clock = Clock()
    monkeypatch.setattr(cw.time, "monotonic", clock)
    cues = []
    w = cw.CalibrationWizard(Tr("fr"), cue=cues.append)
    w.clock, w.cues = clock, cues
    w.start()
    w._timer.stop()        # نتحكم بالتقدم يدوياً
    yield w
    w._close(None)


def advance(w, seconds, sample=None, step=0.1):
    n = int(round(seconds / step))
    for _ in range(n):
        w.clock.t += step
        if sample is not None:
            for _ in range(3):
                w.add_sample(sample)
        w._tick()


def test_prepare_starts_steps_as_soon_as_conditions_are_good(wizard):
    assert wizard._phase == "prepare" and wizard.art.scene == "prepare"
    assert wizard.cues == ["step"]
    assert "lumière" in wizard.details.text()           # نصيحة الإضاءة الثابتة
    advance(wizard, 1.5, S())
    assert wizard._phase == "steps" and wizard._step == 0
    assert wizard.art.scene == STEPS[0][0]
    assert wizard.cues == ["step", "step"]


def test_prepare_shows_live_hint_and_never_blocks(wizard):
    advance(wizard, 2.0, S(over=0.3))
    assert wizard._phase == "prepare"
    assert "lumière derrière" in wizard.details.text()
    advance(wizard, 4.5, S(over=0.3))                   # الحد الأقصى 6 ث: لا يعلق أبداً
    assert wizard._phase == "steps"


def test_prepare_waits_for_hand(wizard):
    advance(wizard, 3.0, S(hand=False))
    assert wizard._phase == "prepare"
    assert wizard.hand.text() == wizard.t("calib_hand_missing")


def test_full_run_cues_each_step_and_ends_with_result(wizard):
    advance(wizard, 1.5, S())
    for name, dur in STEPS:
        assert wizard.art.scene == name
        sample = S(pinch=0.1 if name == "pinch" else 0.9)
        advance(wizard, dur + 0.1, sample)
    assert wizard._phase == "summary"
    assert wizard.cues.count("step") == 1 + len(STEPS)
    assert wizard.cues[-1] in ("ok", "error")
    assert wizard.art.scene == "none" and not wizard.art._timer.isActive()


def test_step_hint_clears_when_conditions_improve(wizard):
    advance(wizard, 1.5, S())
    advance(wizard, 1.0, S(size=0.9))
    assert "reculez" in wizard.details.text()
    advance(wizard, 1.0, S())
    assert wizard.details.text() == ""


# ---------------- الرسوم ----------------
@pytest.mark.parametrize("scene", ["prepare", "open", "pinch", "point", "zone"])
@pytest.mark.parametrize("rtl", [False, True])
def test_art_renders_every_scene(qapp, scene, rtl):
    from PySide6.QtGui import QImage

    from ui.calibration_art import CalibrationArt
    from ui.theme import theme
    art = CalibrationArt(theme(1.0, False), rtl=rtl)
    art.resize(600, art.height())
    art.set_scene(scene)
    assert art._timer.isActive()
    for dt in (0.0, 0.5, 1.3, 2.9):
        art._t0 -= dt
        img = QImage(art.size(), QImage.Format_ARGB32)
        img.fill(0)
        art.render(img)
        assert any(img.pixelColor(x, y).alpha() for x in range(0, 600, 7) for y in range(0, art.height(), 7))
    art.set_scene("none")
    assert not art._timer.isActive()


def test_animation_curves():
    from ui.calibration_art import OPEN, PINCH, POINT, lerp_pose, pinch_phase, zone_point
    assert len(OPEN) == len(PINCH) == len(POINT) == 21
    assert pinch_phase(0.0) == 0.0 and pinch_phase(1.2) == 1.0
    assert lerp_pose(OPEN, PINCH, 1.0) == PINCH and lerp_pose(OPEN, PINCH, -1) == OPEN
    # طرفا الإبهام والسبابة يتلامسان في وضعية القرص
    (tx, ty), (ix, iy) = PINCH[4], PINCH[8]
    assert abs(tx - ix) < 0.03 and abs(ty - iy) < 0.03
    corners = {tuple(round(v, 2) for v in zone_point(t)) for t in (1.4, 2.9, 4.4, 5.9)}
    assert corners == {(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)}
