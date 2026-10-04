"""سكون الكاميرا: آلة الحالات، الإيقاظ من المتحكم، والحلقة الحقيقية لعملية الرؤية بكاميرا وهمية."""
import threading
import time

import numpy as np
import pytest

from core.events import ControlMessage, StatusEvent
from vision.idle import ACTIVE, ASLEEP, DOZING, IdleManager


# ---------------- آلة الحالات ----------------
def test_idle_levels():
    m = IdleManager(120, 600, now=0)
    assert m.update(60, hand=False) is None and m.state == ACTIVE
    assert m.update(121, hand=False) == DOZING
    assert m.update(300, hand=False) is None
    assert m.update(601, hand=False) == ASLEEP
    assert m.wake(700) == ACTIVE and m.update(750, hand=False) is None


def test_hand_resets_and_wakes_from_doze():
    m = IdleManager(10, 100, now=0)
    m.update(11, hand=False)
    assert m.update(12, hand=True) == ACTIVE
    assert m.update(20, hand=False) is None          # العدّ يبدأ من آخر ظهور لليد
    assert m.update(23, hand=False) == DOZING


def test_no_deep_sleep_while_paused_or_calibrating():
    m = IdleManager(10, 20, now=0)
    assert m.update(30, hand=False, paused=True) == DOZING   # الكف ما زال يُرى ببطء
    assert m.update(500, hand=False, paused=True) is None
    m = IdleManager(10, 20, now=0)
    assert m.update(500, hand=False, calibrating=True) is None and m.state == ACTIVE


def test_zero_disables():
    m = IdleManager(0, 0, now=0)
    assert m.update(10_000, hand=False) is None and m.state == ACTIVE
    m = IdleManager(0, 30, now=0)
    assert m.update(31, hand=False) == ASLEEP                # بلا سكون خفيف: مباشرة للنوم


# ---------------- المتحكم ----------------
@pytest.fixture
def controller(tmp_path, monkeypatch):
    from conftest import FakeOS
    from config import loader
    from core import paths
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    c = Controller(FakeOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    c.sent = []
    monkeypatch.setattr(c.vision, "send", lambda kind, **p: c.sent.append(kind))
    c.vision.wanted = True
    yield c
    c.vision.wanted = False
    c.shutdown()


def test_wake_camera_only_when_sleeping(controller):
    c = controller
    c.vision.state = ("ready", "")
    assert not c.wake_camera() and c.sent == []
    c.vision.state = ("asleep", "")
    assert c.wake_camera() and c.sent == ["wake"]
    c.wake_camera()
    assert c.sent == ["wake"]                     # رسالة واحدة تكفي
    c.vision.wanted = False                       # أطفأها المستخدم بنفسه: لا نوقظها
    c._wake_sent = 0
    assert not c.wake_camera()


def test_wake_word_and_voice_result_wake_camera(controller):
    c = controller
    c.vision.state = ("dozing", "")
    c.notify("wake")
    assert c.sent == ["wake"]
    c._wake_sent = 0
    c.notify("result", ok=True, command="copy", key="done", values={}, heard="ordinateur copie")
    assert c.sent == ["wake", "wake"]
    c._wake_sent = 0
    c.notify("result", ok=True, command="swipe_right", key="done", values={}, heard="")   # إيماءة
    assert c.sent == ["wake", "wake"]


def test_watchdog_wakes_on_user_input(controller, monkeypatch):
    c = controller
    c.vision.state = ("asleep", "")
    monkeypatch.setattr(c.os, "seconds_since_input", lambda: 30.0, raising=False)
    c.watchdog()
    assert c.sent == []
    monkeypatch.setattr(c.os, "seconds_since_input", lambda: 0.2, raising=False)
    c.watchdog()
    assert c.sent == ["wake"]
    c._wake_sent = 0
    c.config.vision.wake_on_input = False
    c.watchdog()
    assert c.sent == ["wake"]


@pytest.mark.parametrize("lang,phrase", [("fr", "réveille la caméra"), ("en", "camera on"),
                                         ("ar", "فعل الكاميرا")])
def test_voice_command(env, lang, phrase):
    m = env.disp.parser.parse(phrase, lang)
    assert m is not None and m.spec.id == "camera_wake"


def test_windows_last_input():
    from os_layer.windows.backend import WindowsBackend
    s = WindowsBackend.seconds_since_input(None)
    assert s is None or s >= 0


# ---------------- الحلقة الحقيقية بكاميرا وهمية ----------------
class FakeCap:
    opened = 0
    released = 0

    def __init__(self):
        FakeCap.opened += 1
        self.reads = 0

    def read(self):
        self.reads += 1
        return True, np.full((48, 64, 3), 120, np.uint8)

    def get(self, _prop):
        return 0

    def release(self):
        FakeCap.released += 1


class FakeTracker:
    def __init__(self, *_a):
        pass

    def detect(self, rgb, t):
        return []

    def close(self):
        pass


class FakeLink:
    def __init__(self, *_a):
        self.events = []
        self.inbox = []
        self.lock = threading.Lock()

    def send(self, ev):
        with self.lock:
            self.events.append(ev)

    def poll_control(self):
        with self.lock:
            msgs, self.inbox = self.inbox, []
        return msgs

    def close(self):
        pass

    def states(self):
        with self.lock:
            return [e.state for e in self.events if isinstance(e, StatusEvent)]


def wait_for(pred, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_worker_dozes_releases_camera_and_wakes(monkeypatch):
    from config.schema import VisionConfig
    from core import ipc, offline_guard
    from vision import worker
    FakeCap.opened = FakeCap.released = 0
    link = FakeLink()
    monkeypatch.setattr(ipc, "Link", lambda *a: link)
    monkeypatch.setattr(offline_guard, "install", lambda: None)
    monkeypatch.setattr(worker, "HandTracker", FakeTracker)
    caps = []
    monkeypatch.setattr(worker, "open_camera", lambda cfg: caps.append(FakeCap()) or caps[-1])
    cfg = VisionConfig(idle_light_s=1, idle_deep_s=2, light_fps=4).model_dump()
    cfg.update(log_level="WARNING", dry_run=True)
    t = threading.Thread(target=worker.run, args=(cfg, "models", None, b""), daemon=True)
    t.start()
    try:
        assert wait_for(lambda: "dozing" in link.states())
        reads_at_doze = caps[0].reads
        assert wait_for(lambda: "asleep" in link.states())
        st = link.states()
        assert st[:3] == ["ready", "dozing", "asleep"]
        assert FakeCap.released == 1
        # ثانية من السكون الخفيف بـ 4 إطار/ث: بضع قراءات فقط (الكاميرا الوهمية فورية، والنشطة تقرأ الآلاف)
        reads_awake = caps[0].reads
        assert reads_awake - reads_at_doze <= 8, reads_awake - reads_at_doze
        # نائمة: لا قراءة إطلاقاً
        time.sleep(0.5)
        assert caps[0].reads == reads_awake and len(caps) == 1
        with link.lock:
            link.inbox.append(ControlMessage("wake"))
        assert wait_for(lambda: link.states().count("ready") >= 2)
        assert len(caps) == 2 and FakeCap.opened == 2      # أُعيد فتح الكاميرا
        assert wait_for(lambda: caps[1].reads > 0)
        # الإيقاف الطارئ وهي نائمة يوقظها (لكي يستطيع الكف المفتوح الاستئناف)
        assert wait_for(lambda: link.states().count("asleep") >= 2)
        with link.lock:
            link.inbox.append(ControlMessage("paused", {"value": True}))
        assert wait_for(lambda: len(caps) == 3)
        time.sleep(2.6)
        assert link.states().count("asleep") == 2         # متوقف ← لا نوم عميق
    finally:
        with link.lock:
            link.inbox.append(ControlMessage("shutdown"))
        t.join(5)
    assert not t.is_alive() and link.states()[-1] == "stopped"
