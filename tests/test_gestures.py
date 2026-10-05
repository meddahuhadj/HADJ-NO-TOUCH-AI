"""اختبارات مصنّف الإيماءات وآلة الحالات والمؤشر (بنقاط يد اصطناعية، بلا كاميرا)."""
import threading

import pytest

from config.schema import GestureTuning, VisionConfig
from handsynth import make_hand
from vision.filters import OneEuroFilter
from vision.gestures import GestureEngine, classify
from vision.pointer import PointerController

T = GestureTuning()
DT = 1 / 30


def cls(hand, current=None):
    return classify(hand, T.pinch_enter, T.pinch_exit, aspect=1.0, current_pinch=current).name


# ---------------- التصنيف الساكن ----------------
@pytest.mark.parametrize("pose,expected", [
    ("point", "point"), ("open", "open"), ("fist", "fist"), ("two", "two"),
    ("pinch", "pinch"), ("pinch_closed", "pinch"), ("middle_pinch", "middle_pinch"),
])
def test_classify(pose, expected):
    assert cls(make_hand(pose)) == expected


@pytest.mark.parametrize("deg", [-60, -30, 30, 90, 180])
@pytest.mark.parametrize("pose", ["point", "open", "fist", "pinch", "two"])
def test_classify_rotation_invariant(pose, deg):
    assert cls(make_hand(pose, rotate_deg=deg)) == cls(make_hand(pose))


@pytest.mark.parametrize("pose", ["point", "open", "fist", "pinch"])
def test_classify_robust_to_small_noise(pose):
    for seed in range(5):
        assert cls(make_hand(pose, noise=0.003, seed=seed)) == pose


def test_fist_is_never_a_pinch():
    # في القبضة يقترب الإبهام من طرف السبابة المطوية: يجب ألا يُحتسب قرصاً (نقرة عرضية)
    p = classify(make_hand("fist"), T.pinch_enter, T.pinch_exit, aspect=1.0)
    assert p.pinch_index < T.pinch_enter and p.name == "fist"


# ---------------- آلة الحالات ----------------
class Seq:
    """يغذي المحرك بتسلسل وضعيات ويجمع الأحداث."""

    def __init__(self, tuning=T, **kw):
        self.eng = GestureEngine(tuning, aspect=1.0, **kw)
        self.t = 100.0
        self.events: list[str] = []
        self.outs = []

    def feed(self, pose, frames=1, **kw):
        for _ in range(frames):
            hands = [] if pose is None else [make_hand(pose, **kw)]
            out = self.eng.update(hands, self.t)
            self.events += out.events
            self.outs.append(out)
            self.t += DT
        return self.outs[-1]


def test_point_moves_pointer_in_zone():
    s = Seq(zone=(0.2, 0.15, 0.8, 0.75))
    out = s.feed("point")
    # طرف السبابة (0.44, 0.44) ← (0.4, 0.4833)
    assert out.pointer == pytest.approx((0.4, (0.44 - 0.15) / 0.6), abs=1e-4)
    out = s.feed("point", dx=0.9)          # خارج المنطقة ← يُقيَّد بالحافة
    assert out.pointer[0] == 1.0


def test_open_palm_and_two_do_not_move_pointer():
    s = Seq()
    assert s.feed("open").pointer is None
    assert s.feed("two").pointer is None
    assert s.feed("fist").pointer is None


def test_pinch_tap():
    s = Seq()
    s.feed("point", 5)
    out = s.feed("pinch", 4)            # ~130ms
    assert out.locked and out.pointer is None
    s.feed("point", 2)
    assert s.events == ["pinch_down", "pinch_tap"]


def test_double_pinch_gives_two_taps():
    s = Seq()
    s.feed("point", 3)
    s.feed("pinch", 3)
    s.feed("point", 3)
    s.feed("pinch", 3)
    s.feed("point", 2)
    assert s.events.count("pinch_tap") == 2


def test_pinch_hold_becomes_drag():
    s = Seq()
    s.feed("point", 3)
    s.feed("pinch", 15)                 # 500ms > drag_hold_ms
    assert "drag_start" in s.events and "pinch_tap" not in s.events
    out = s.feed("pinch", dx=0.05)
    assert out.pointer is not None      # المؤشر يتبع أثناء السحب
    s.feed("point", 2)
    assert s.events[-1] == "drag_end" and "pinch_tap" not in s.events


def test_pinch_with_movement_starts_drag_early():
    s = Seq()
    s.feed("point", 3)
    s.feed("pinch", 2)
    s.feed("pinch", 1, dx=0.06)
    assert "drag_start" in s.events
    assert s.t - 100 < 0.3


def test_pinch_released_into_fist_is_cancelled():
    s = Seq()
    s.feed("point", 3)
    s.feed("pinch", 3)
    s.feed("fist", 2)
    assert "pinch_tap" not in s.events and "pinch_cancel" in s.events


def test_middle_pinch_tap():
    s = Seq()
    s.feed("point", 3)
    s.feed("middle_pinch", 4)
    s.feed("point", 2)
    assert s.events == ["middle_down", "middle_pinch_tap"]


def test_fist_hold_fires_once():
    s = Seq()
    s.feed("fist", 10)                  # 330ms < 600ms
    assert "fist_hold" not in s.events
    s.feed("fist", 30)
    assert s.events.count("fist_hold") == 1


def test_palm_holds():
    s = Seq()
    s.feed("open", 32)                  # ~1.07s
    assert s.events == ["palm_hold_short"]
    s.feed("open", 32)                  # ~2.1s
    assert s.events == ["palm_hold_short", "palm_hold_long"]
    s.feed("open", 30)
    assert len(s.events) == 2


def test_brief_hand_loss_keeps_drag():
    s = Seq()
    s.feed("point", 2)
    s.feed("pinch", 15)
    s.feed(None, 3)                     # 100ms < lost_ms
    assert "drag_end" not in s.events
    s.feed("pinch", 2)
    assert "drag_end" not in s.events


def test_hand_lost_releases_drag():
    s = Seq()
    s.feed("point", 2)
    s.feed("pinch", 15)
    s.feed(None, 20)                    # 660ms
    assert s.events[-2:] == ["drag_end", "hand_lost"]
    s.feed(None, 10)
    assert s.events.count("hand_lost") == 1


def test_hand_preference():
    s = Seq(hand_pref="right")
    out = s.eng.update([make_hand("point", handedness="Left")], 1.0)
    assert out.pose == "none"
    out = s.eng.update([make_hand("open", handedness="Left"), make_hand("point", handedness="Right")], 1.1)
    assert out.pose == "point"


# ---------------- المرشح ----------------
def test_one_euro_reduces_jitter_but_follows_motion():
    import random
    rnd = random.Random(1)
    f = OneEuroFilter(min_cutoff=1.0, beta=0.01)
    raw = [500 + rnd.uniform(-4, 4) for _ in range(60)]
    out = [f(x, i / 30) for i, x in enumerate(raw)]
    spread = lambda v: max(v[20:]) - min(v[20:])  # noqa: E731
    assert spread(out) < spread(raw) / 2
    f.reset()
    moving = [f(i * 20.0, i / 30) for i in range(60)]  # 600 px/s
    assert abs(moving[-1] - 59 * 20) < 40              # تأخر صغير في الحركة السريعة


# ---------------- المؤشر ----------------
@pytest.fixture
def ptr():
    from conftest import FakeOS
    fake = FakeOS()
    forwarded = []
    cfg = VisionConfig()
    p = PointerController(fake, cfg, lambda g, a: forwarded.append((g, a)), threading.Event(),
                          screen_rect=(0, 0, 1920, 1080))
    return p, fake, forwarded


def drive(ptr, seq_poses):
    p, fake, fwd = ptr
    s = Seq()
    for pose, n, kw in seq_poses:
        for _ in range(n):
            out = s.eng.update([] if pose is None else [make_hand(pose, **kw)], s.t)
            p.apply(out, s.t)
            s.t += DT
    return fake.calls


def test_pointer_click_at_rewound_position(ptr):
    calls = drive(ptr, [("point", 10, {}), ("point", 5, {"dx": 0.1}), ("pinch", 3, {}), ("point", 1, {})])
    clicks = [i for i, c in enumerate(calls) if c[0] == "mouse"]
    assert calls[clicks[0]] == ("mouse", "left", "click", 1)
    assert len(clicks) == 1
    # لا حركة بين التثبيت والنقرة
    lock_idx = max(i for i, c in enumerate(calls[:clicks[0]]) if c[0] == "move")
    assert all(c[0] != "move" for c in calls[lock_idx + 1:clicks[0]])


def test_pointer_right_click(ptr):
    calls = drive(ptr, [("point", 5, {}), ("middle_pinch", 3, {}), ("point", 1, {})])
    assert ("mouse", "right", "click", 1) in calls


def test_pointer_drag(ptr):
    calls = drive(ptr, [("point", 5, {}), ("pinch", 15, {}), ("pinch", 10, {"dx": 0.1}), ("point", 2, {"dx": 0.1})])
    downs = calls.index(("mouse", "left", "down", 1))
    ups = calls.index(("mouse", "left", "up", 1))
    moves_during = [c for c in calls[downs:ups] if c[0] == "move"]
    assert downs < ups and len(moves_during) > 3
    assert moves_during[-1][1] > moves_during[0][1]   # تحرك يميناً أثناء السحب


def test_fist_pauses_immediately_and_blocks(ptr):
    p, fake, fwd = ptr
    drive(ptr, [("point", 3, {}), ("fist", 25, {})])
    assert p.paused.is_set()
    assert ("fist_hold", "app.pause") in fwd
    n = len(fake.calls)
    drive(ptr, [("point", 10, {"dx": 0.1}), ("pinch", 3, {}), ("point", 2, {})])
    assert len(fake.calls) == n        # لا حركة ولا نقر أثناء الإيقاف


def test_open_palm_resumes(ptr):
    p, fake, fwd = ptr
    p.paused.set()
    drive(ptr, [("open", 35, {})])
    assert not p.paused.is_set()
    assert ("palm_hold_short", "app.resume") in fwd
    # الكف الطويل بعد الاستئناف لا يُطلق show_desktop في نفس الثبات؟ (يُطلق عند 2s)
    drive(ptr, [("point", 3, {})])
    assert fake.calls[-1][0] == "move"


def test_pause_during_drag_releases_button(ptr):
    p, fake, fwd = ptr
    drive(ptr, [("point", 3, {}), ("pinch", 15, {})])
    assert p.dragging
    p.paused.set()                      # إيقاف صوتي من العملية الرئيسية
    drive(ptr, [("pinch", 1, {})])
    assert fake.calls[-1] == ("mouse", "left", "up", 1) and not p.dragging


def test_palm_long_forwards_binding(ptr):
    p, fake, fwd = ptr
    drive(ptr, [("open", 65, {})])
    assert ("palm_hold_long", "show_desktop") in fwd


def test_binding_none_disables(ptr):
    p, fake, fwd = ptr
    p.cfg.bindings["pinch_tap"] = "none"
    calls = drive(ptr, [("point", 3, {}), ("pinch", 3, {}), ("point", 1, {})])
    assert not any(c[0] == "mouse" for c in calls)


# ============================ المرحلة (د): إيماءات متقدمة ============================
def feed_multi(s, hands_spec, frames=1):
    """hands_spec: قائمة (pose, kwargs) لعدة أيدٍ في الإطار نفسه."""
    for _ in range(frames):
        out = s.eng.update([make_hand(p, **kw) for p, kw in hands_spec], s.t)
        s.events += out.events
        s.outs.append(out)
        s.t += DT
    return s.outs[-1]


def test_two_finger_scroll_up_and_down():
    s = Seq()
    s.feed("two", 7)                       # ثبات 150ms قبل البدء
    out = s.feed("two", 1, dy=-0.12)        # اليد للأعلى 0.12 ← 3 نقرات للأعلى
    assert out.scroll == 3 and out.pointer is None
    out = s.feed("two", 1, dy=-0.12 + 0.2)  # للأسفل 0.2 ← -5 (مع الباقي السابق)
    assert out.scroll in (-5, -6)
    assert sum(o.scroll for o in s.outs) in (-2, -3)


def test_scroll_needs_settle_and_can_invert():
    t = GestureTuning(scroll_invert=True)
    s = Seq(tuning=t)
    s.feed("two", 1)
    out = s.feed("two", 1, dy=-0.2)         # قبل انتهاء فترة الثبات: لا تمرير
    assert out.scroll == 0
    s.feed("two", 7, dy=-0.2)
    out = s.feed("two", 1, dy=-0.32)
    assert out.scroll == -3                 # معكوس


def test_swipe_right_once_with_cooldown():
    s = Seq()
    for i in range(10):                     # 0.3 عرض خلال 330ms
        s.feed("open", 1, dx=i * 0.033)
    assert s.events.count("swipe_right") == 1
    for i in range(10):
        s.feed("open", 1, dx=0.3 + i * 0.033)   # سحب ثانٍ فوراً ← ممنوع بفترة التهدئة
    assert s.events.count("swipe_right") == 1


def test_swipe_left():
    s = Seq()
    for i in range(10):
        s.feed("open", 1, dx=-i * 0.033)
    assert s.events == ["swipe_left"]


def test_slow_drift_or_vertical_motion_is_not_swipe():
    s = Seq()
    for i in range(60):                     # 0.3 خلال ثانيتين: بطيء جداً
        s.feed("open", 1, dx=i * 0.005)
    for i in range(10):                     # عمودي
        s.feed("open", 1, dx=0.3, dy=-i * 0.04)
    assert "swipe_right" not in s.events and "swipe_left" not in s.events


def test_swipe_resets_palm_hold_timer():
    s = Seq()
    s.feed("open", 20)                      # 0.66s ثبات
    for i in range(10):
        s.feed("open", 1, dx=i * 0.033)
    s.feed("open", 40, dx=0.3)              # 1.3s بعد السحب < 2s
    assert "palm_hold_long" not in s.events


def test_two_hand_zoom_in_and_out():
    s = Seq()
    left, right = ("pinch", {"dx": -0.2}), ("pinch", {"dx": 0.2, "handedness": "Left"})
    out = feed_multi(s, [left, right])
    assert out.pose == "zoom" and "zoom_start" in out.events and out.locked
    out = feed_multi(s, [("pinch", {"dx": -0.26}), ("pinch", {"dx": 0.26, "handedness": "Left"})])
    assert out.zoom == 1 and "zoom_in" in out.events
    out = feed_multi(s, [("pinch", {"dx": -0.18}), ("pinch", {"dx": 0.18, "handedness": "Left"})])
    assert out.zoom == -1


def test_zoom_cancels_pending_click_and_suppresses_release_tap():
    s = Seq()
    s.feed("point", 3)
    s.feed("pinch", 2)                      # يد واحدة تبدأ القرص
    feed_multi(s, [("pinch", {}), ("pinch", {"dx": 0.4, "handedness": "Left"})], 3)
    assert "pinch_cancel" in s.events and "zoom_start" in s.events
    s.feed("pinch", 3)                      # اليد الثانية اختفت، الأولى ما زالت تقرص
    s.feed("point", 3)                      # الإفلات
    assert "pinch_tap" not in s.events and "drag_start" not in s.events
    assert "zoom_end" in s.events
    s.feed("pinch", 3)                      # قرص جديد بعد ذلك يعمل طبيعياً
    s.feed("point", 1)
    assert s.events.count("pinch_tap") == 1


def test_pointer_executes_scroll_zoom_and_forwards_swipe(ptr):
    p, fake, fwd = ptr
    drive(ptr, [("two", 7, {}), ("two", 1, {"dy": -0.12})])
    assert ("scroll", 3, False) in fake.calls
    s = Seq()
    for i in range(10):
        p.apply(s.eng.update([make_hand("open", dx=i * 0.033)], s.t), s.t)
        s.t += DT
    assert ("swipe_right", "switch_window") in fwd
    s = Seq()
    for dx in (0.2, 0.26):
        out = s.eng.update([make_hand("pinch", dx=-dx), make_hand("pinch", dx=dx, handedness="Left")], s.t)
        p.apply(out, s.t)
        s.t += DT
    assert ("zoom", 1) in fake.calls
    assert not any(c[0] == "mouse" for c in fake.calls)   # لا نقرات أثناء التكبير


def test_dwell_click_triggers_tap(ptr):
    p, fake, fwd = ptr
    p.cfg.dwell_click_enabled = True
    p.cfg.dwell_click_ms = 300
    p.cfg.dwell_click_radius = 50.0

    s = Seq()
    # Stay steady in point pose for 15 frames (~500ms > 300ms threshold)
    for _ in range(15):
        out = s.eng.update([make_hand("point")], s.t)
        p.apply(out, s.t)
        s.t += DT

    progress_events = [val for ev, val in fwd if ev == "dwell_progress"]
    assert len(progress_events) > 0
    assert "pinch_tap:click" in p.performed or ("mouse", "left", "click", 1) in fake.calls



def test_dwell_clicks_once_while_the_hand_stays_still(ptr):
    """يد ساكنة فوق زر (مثل «حذف»): نقرة واحدة فقط، لا نقرات متكررة كل ثانية."""
    p, fake, fwd = ptr
    p.cfg.dwell_click_enabled = True
    p.cfg.dwell_click_ms = 300
    p.cfg.dwell_click_radius = 50.0
    s = Seq()
    for _ in range(60):                       # ثانيتان ساكنتان = 6 أضعاف مهلة التحويم
        p.apply(s.eng.update([make_hand("point")], s.t), s.t)
        s.t += DT
    clicks = [c for c in fake.calls if c[:3] == ("mouse", "left", "click")]
    assert len(clicks) == 1
    progress = [v for g, v in fwd if g == "dwell_progress"]
    assert len(progress) <= 15 and all(float(v) in [x / 10 for x in range(11)] for v in progress)


def test_dwell_progress_is_a_notification_not_an_action(env):
    from core.events import GestureEvent
    env.disp.handle(GestureEvent("dwell_progress", {"action": "0.4"}))
    assert [k for k, _ in env.notes] == ["dwell"] and env.notes[0][1] == {"progress": 0.4}
    assert env.os.calls == []


def test_media_commands_use_global_media_keys(env):
    """«pause la musique» مع Word في المقدمة: مفتاح الوسائط، لا مسافة تُكتب في المستند."""
    from commands.actions import run_steps
    env.os.window_title = "Rapport.docx - Word"
    for action in ("media_play_pause", "media_next", "media_prev"):
        run_steps(env.disp.ctx, [{"action": action}])
    assert env.os.calls == [("key", "media_play_pause", 1), ("key", "media_next", 1), ("key", "media_prev", 1)]


def test_media_keys_exist_on_windows_and_linux():
    from os_layer.linux.keys import keysym_name
    from os_layer.windows.input import VK
    for k in ("media_play_pause", "media_next", "media_prev"):
        assert k in VK and keysym_name(k).startswith("XF86Audio")
