"""مؤشر الحالة والتغذية الراجعة: أحداث نشاط الصوت، هيكل اليد، مستوى الأصوات، ورسم المؤشر."""
import os
import struct
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from audio.vad import FRAME_BYTES, Segmenter  # noqa: E402
from audio.worker import AudioPipeline, frame_level  # noqa: E402
from core.events import HandPreviewEvent, SpeechEvent, VoiceActivityEvent  # noqa: E402
from core.sounds import ensure_sounds  # noqa: E402

SILENCE = b"\0" * FRAME_BYTES


def tone(amp: int) -> bytes:
    n = FRAME_BYTES // 2
    return struct.pack(f"<{n}h", *(int(amp * np.sin(i / 3)) for i in range(n)))


class FakeRec:
    def __init__(self):
        self.frames = 0

    def accept(self, data):
        self.frames += 1

    def partial(self):
        return ""

    def finish(self):
        return ("hello", "hello") if self.frames else ("", "")


def run_pipeline(frames):
    out = []
    pipe = AudioPipeline(FakeRec(), Segmenter(silence_ms=300), lambda f: f != SILENCE, out.append, "en")
    for f in frames:
        pipe.process(f)
    pipe.flush()
    return out


# ---------------- نشاط الصوت ----------------
def test_voice_activity_brackets_the_utterance():
    out = run_pipeline([SILENCE] * 5 + [tone(8000)] * 40 + [SILENCE] * 20)
    voice = [e for e in out if isinstance(e, VoiceActivityEvent)]
    assert voice[0].active and voice[0].level > 0.5
    assert voice[-1] == VoiceActivityEvent(False)
    assert sum(1 for e in voice if not e.active) == 1
    # النهاية تسبق نتيجة التعرف: المؤشر يتوقف عن النبض قبل ظهور الأمر
    end = out.index(voice[-1])
    assert isinstance(out[end + 1], SpeechEvent)


def test_voice_levels_are_throttled():
    # 1.2 ثانية من الكلام تُعالج في أجزاء من الثانية: يجب ألا تُرسل 40 رسالة مستوى
    out = run_pipeline([tone(8000)] * 40 + [SILENCE] * 20)
    levels = [e for e in out if isinstance(e, VoiceActivityEvent) and e.active]
    assert 1 <= len(levels) <= 3


def test_no_voice_events_for_silence():
    assert run_pipeline([SILENCE] * 50) == []


def test_flush_ends_voice_activity():
    out = run_pipeline([tone(8000)] * 10)   # بلا صمت بعده: flush يغلق العبارة (كتم الميكروفون)
    assert [e for e in out if isinstance(e, VoiceActivityEvent)][-1] == VoiceActivityEvent(False)


def test_frame_level_range():
    assert frame_level(SILENCE) == 0.0
    assert 0.2 < frame_level(tone(800)) < frame_level(tone(8000)) <= 1.0
    assert frame_level(tone(32000)) == 1.0
    assert frame_level(b"") == 0.0


# ---------------- التوجيه في الموزّع ----------------
def test_dispatcher_forwards_voice_and_hand(env):
    env.disp.handle(VoiceActivityEvent(True, 0.4))
    pts = [(0.1 * i, 0.05 * i) for i in range(21)]
    env.disp.handle(HandPreviewEvent(pts, "pinch"))
    assert ("voice", {"active": True, "level": 0.4}) in env.notes
    assert ("hand", {"points": pts, "pose": "pinch"}) in env.notes


def test_hand_preview_payload_has_no_image():
    from vision.gestures import Hand
    from vision.worker import hand_preview
    lms = np.random.default_rng(1).random((21, 3)).astype(np.float32)
    ev = hand_preview([Hand(lms, "Right", 0.4), Hand(lms * 0.5, "Left", 0.9)], "fist")
    assert ev.pose == "fist" and len(ev.points) == 21
    assert ev.points[0] == (round(float(lms[0][0] * 0.5), 3), round(float(lms[0][1] * 0.5), 3))
    assert all(isinstance(v, float) for p in ev.points for v in p)


# ---------------- الأصوات ----------------
def peak(path):
    with wave.open(str(path)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return int(np.abs(data.astype(np.int32)).max())


def test_sound_volume_scales_and_hand_tones_are_quiet(tmp_path):
    loud = ensure_sounds(tmp_path, 100)
    soft = ensure_sounds(tmp_path, 20)
    assert loud["ok"].parent.name == "v100" and soft["ok"].parent.name == "v20"
    assert peak(soft["ok"]) < peak(loud["ok"]) * 0.3
    assert peak(loud["hand"]) < peak(loud["ok"]) * 0.6
    assert {"hand", "hand_lost", "pause", "error"} <= set(loud)


def test_sound_volume_is_clamped(tmp_path):
    assert ensure_sounds(tmp_path, 500)["ok"].parent.name == "v100"
    assert ensure_sounds(tmp_path, 0)["ok"].parent.name == "v10"


def test_default_volume_matches_previous_loudness(tmp_path):
    # المستوى 70 = السعة 0.35 السابقة: المستخدمون الحاليون لا يلاحظون تغييراً
    assert abs(peak(ensure_sounds(tmp_path)["ok"]) - 0.35 * 32767) < 400


# ---------------- مؤشر الحالة ----------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def render(orb):
    from PySide6.QtGui import QImage
    img = QImage(orb.size(), QImage.Format_ARGB32)
    img.fill(0)
    orb.render(img)
    return img


def painted(img) -> bool:
    """القرص مرسوم فعلاً: مركز الصورة غير شفاف."""
    return img.pixelColor(img.width() // 2, img.height() // 2).alpha() > 0


@pytest.mark.parametrize("visual", ["ready", "armed", "paused", "error", "muted", "loading",
                                    "dictation", "grid"])
def test_orb_renders_every_state(qapp, visual):
    from ui.status_orb import StatusOrb
    for hc in (False, True):
        orb = StatusOrb(1.0, hc)
        orb.set_state(visual, "tracking")
        assert painted(render(orb))


def test_orb_glyphs_are_distinct_not_only_colour():
    from ui.status_orb import glyph_for
    glyphs = {glyph_for(v) for v in ("paused", "error", "muted", "loading", "ready")}
    assert len(glyphs) == 5


def test_orb_animates_only_while_needed(qapp):
    from ui.status_orb import StatusOrb
    orb = StatusOrb()
    orb.set_state("ready", "ready")
    assert not orb._timer.isActive()            # ساكن = لا استهلاك للمعالج
    orb.set_voice(True, 0.8)
    assert orb._timer.isActive()
    orb.set_voice(False)
    for _ in range(40):
        orb._tick()
    assert not orb._timer.isActive() and orb._level == 0.0


def test_orb_hand_skeleton_expires_and_pause_clears_it(qapp, monkeypatch):
    from ui import status_orb
    orb = status_orb.StatusOrb()
    orb.set_state("ready", "tracking")
    pts = [(0.4 + 0.01 * i, 0.5 - 0.01 * i) for i in range(21)]
    orb.set_hand(pts, "pinch")
    assert orb.hand is not None
    render(orb)                                 # رسم الهيكل لا يفشل
    t0 = orb._hand_t
    monkeypatch.setattr(status_orb.time, "monotonic", lambda: t0 + 1.0)
    orb._tick()
    assert orb.hand is None
    orb.set_hand(pts, "open")
    orb.set_state("paused", "tracking")         # الإيقاف الطارئ يمسح الهيكل والنبض
    assert orb.hand is None and not orb.voice_active
    orb.set_hand(pts, "open")                   # ولا يقبل هيكلاً جديداً وهو متوقف
    assert orb.hand is None


def test_fit_points_stays_inside_circle():
    from ui.status_orb import fit_points
    pts = [(0.2, 0.3), (0.6, 0.9), (0.4, 0.5)] + [(0.3, 0.4)] * 18
    out = fit_points(pts, 50, 50, 20)
    assert all(abs(p.x() - 50) <= 20 and abs(p.y() - 50) <= 20 for p in out)
    assert fit_points([(0.5, 0.5)] * 21, 0, 0, 10)[0].x() == 0   # يد بحجم صفر لا تقسم على صفر


@pytest.mark.parametrize("setting,rtl,expected", [
    ("auto", True, "bottom-left"), ("auto", False, "bottom-right"), ("top-left", True, "top-left")])
def test_orb_corner(setting, rtl, expected):
    from ui.status_orb import corner_for
    assert corner_for(setting, rtl) == expected


# ---------------- أصوات حالة الكاميرا في المتحكم ----------------
def make_controller_stub(hand_sounds):
    """المتحكم دون عمليات فرعية: فقط ما يحتاجه _vision_sound."""
    import threading

    from config.schema import AppConfig
    from core.controller import Controller
    c = Controller.__new__(Controller)
    c.config = AppConfig()
    c.config.feedback.hand_sounds = hand_sounds
    c.paused = threading.Event()
    c.calibrating = False
    c.played = []
    c._sound = c.played.append

    class W:
        state = ("ready", "")
    c.vision = W()
    return c


def test_camera_loss_always_beeps_hand_tones_optional():
    c = make_controller_stub(hand_sounds=False)
    c._vision_sound("tracking")
    c.vision.state = ("tracking", "")
    c._vision_sound("ready")
    assert c.played == []
    c._vision_sound("no_image")
    assert c.played == ["error"]

    c = make_controller_stub(hand_sounds=True)
    c._vision_sound("tracking")
    c.vision.state = ("tracking", "")
    c._vision_sound("ready")
    assert c.played == ["hand", "hand_lost"]
    c.paused.set()                                # متوقف: صمت
    c._vision_sound("tracking")
    assert c.played == ["hand", "hand_lost"]
