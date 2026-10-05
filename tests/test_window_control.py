"""اختبارات أوامر النوافذ والشاشات والعرض (تحكّم دقيق)."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from commands.actions import REGISTRY, ActionError
from config.loader import load_command_specs
from core.events import SpeechEvent
from ui.i18n import STRINGS
from ui.i18n_fr import FR

ROOT = Path(__file__).resolve().parents[1]


def say(env, text, free=None, lang="ar"):
    env.disp.handle(SpeechEvent(text=text, free_text=free if free is not None else text,
                                lang=lang))


def kinds(env):
    return [k for k, _ in env.notes]


def result(env):
    return [d for k, d in env.notes if k == "result"][-1]


def _ctx(env):
    from commands.actions import ActionContext
    return ActionContext(os=env.os, apps=None, app=None, config=env.config)


# ============================ النوافذ ============================
def test_focus_window_by_name(env):
    say(env, "حاسوب انتقل الى المتصفح")
    assert result(env)["ok"] is True
    assert ("focus_window", "المتصفح") in env.os.calls


def test_focus_window_not_found(env):
    env.os.window = False
    say(env, "حاسوب انتقل الى المتصفح")
    res = result(env)
    assert res["ok"] is False and res["key"] == "window_not_found"
    assert res["values"]["name"] == "المتصفح"


def test_center_window(env):
    say(env, "حاسوب ضع النافذة في الوسط")
    assert result(env)["ok"] is True
    assert ("center_window",) in env.os.calls


def test_center_window_without_window(env):
    env.os.window = False
    say(env, "حاسوب ضع النافذة في الوسط")
    assert result(env)["key"] == "no_window"


@pytest.mark.parametrize("phrase,position", [
    ("النافذة لليسار", "left"),
    ("النافذة لليمين", "right"),
    ("النافذة للاعلى", "top"),
])
def test_snap_positions(env, phrase, position):
    say(env, f"حاسوب {phrase}")
    assert result(env)["ok"] is True
    assert ("snap_window", position) in env.os.calls


def test_snap_rejects_unknown_position(env):
    """الإجراء يرفض أي موضع لا يدعمه winapi.snap_rect."""
    ctx = _ctx(env)
    with pytest.raises(ActionError) as exc:
        REGISTRY["snap"](ctx, {"position": "sideways"})
    assert exc.value.key == "bad_position"


def test_window_move_scales_by_step(env):
    say(env, "حاسوب حرك النافذة لليمين")
    assert result(env)["ok"] is True
    assert ("move_window", 80, 0) in env.os.calls


def test_window_resize_scales_by_step(env):
    say(env, "حاسوب وسع النافذة")
    assert result(env)["ok"] is True
    assert ("resize_window", 80, 80) in env.os.calls


def test_always_on_top(env):
    say(env, "حاسوب النافذة فوق كل شيء")
    assert result(env)["ok"] is True
    assert ("always_on_top", True) in env.os.calls


# ============================ الشاشات ============================
def test_move_to_primary_monitor(env):
    say(env, "حاسوب انقل النافذة للشاشة الرئيسية")
    assert result(env)["ok"] is True
    assert ("move_to_monitor", 0) in env.os.calls


def test_move_to_missing_monitor_reports_error(env):
    say(env, "حاسوب انقل النافذة للشاشة الثانية")
    res = result(env)
    assert res["ok"] is False and res["key"] == "no_monitor"
    assert res["values"]["index"] == 1


def test_display_extend(env):
    say(env, "حاسوب وسع الشاشتين")
    assert result(env)["ok"] is True
    assert ("display_mode", "extend") in env.os.calls


def test_display_rejects_unknown_mode(env):
    ctx = _ctx(env)
    with pytest.raises(ActionError) as exc:
        REGISTRY["display_mode"](ctx, {"mode": "sideways"})
    assert exc.value.key == "bad_display_mode"


def test_virtual_desktop_rejects_unknown_op(env):
    ctx = _ctx(env)
    with pytest.raises(ActionError) as exc:
        REGISTRY["virtual_desktop"](ctx, {"op": "sideways"})
    assert exc.value.key == "bad_virtual_desktop"


def test_brightness_percent_is_clamped(env):
    ctx = _ctx(env)
    REGISTRY["set_brightness"](ctx, {"percent": 250})
    assert ("set_brightness", 100) in env.os.calls
    env.os.calls.clear()
    REGISTRY["set_brightness"](ctx, {"percent": -20})
    assert ("set_brightness", 0) in env.os.calls


# ============================ أسطح المكتب ============================
@pytest.mark.parametrize("phrase,direction", [
    ("سطح المكتب التالي", "right"),
    ("سطح المكتب السابق", "left"),
    ("مكتب جديد", "new"),
])
def test_virtual_desktop_ops(env, phrase, direction):
    say(env, f"حاسوب {phrase}")
    assert result(env)["ok"] is True
    assert ("vdesktop", direction) in env.os.calls


def test_close_virtual_desktop_is_dangerous(env):
    """حذف سطح مكتب يجب أن يمرّ بتأكيد صريح قبل التنفيذ."""
    say(env, "حاسوب اغلق المكتب الافتراضي")
    assert "confirm" in kinds(env)
    assert not any(c[0] == "vdesktop" for c in env.os.calls)
    say(env, "نعم")                       # تأكيد بلا كلمة تنبيه
    assert ("vdesktop", "close") in env.os.calls


def test_close_virtual_desktop_cancelled(env):
    say(env, "حاسوب اغلق المكتب الافتراضي")
    say(env, "لا")
    assert not any(c[0] == "vdesktop" for c in env.os.calls)


# ============================ العرض ============================
def test_brightness_up_and_down(env):
    say(env, "حاسوب ارفع سطوع الشاشة")
    assert result(env)["ok"] is True
    assert ("brightness", "up", 10) in env.os.calls
    say(env, "حاسوب اخفض سطوع الشاشة")
    assert ("brightness", "down", 10) in env.os.calls


def test_set_brightness(env):
    say(env, "حاسوب السطوع نصف")
    assert result(env)["ok"] is True
    assert ("set_brightness", 40) in env.os.calls


def test_brightness_unsupported_reports_error(env):
    env.os.window = False
    say(env, "حاسوب ارفع سطوع الشاشة")
    assert result(env)["key"] == "no_brightness"


def test_dark_mode_toggle(env):
    say(env, "حاسوب شغل الوضع الداكن")
    assert ("dark_mode", True) in env.os.calls
    say(env, "حاسوب الوضع الفاتح")
    assert ("dark_mode", False) in env.os.calls


def test_monitor_off_then_on(env):
    say(env, "حاسوب اطفي الشاشة")
    assert result(env)["ok"] is True
    assert ("monitor_power", False) in env.os.calls
    say(env, "حاسوب شغل الشاشة")
    assert ("monitor_power", True) in env.os.calls


def test_toggle_microphone_mute(env):
    say(env, "حاسوب كتم الميكروفون")
    assert result(env)["ok"] is True
    assert ("mic_mute",) in env.os.calls


# ============================ اتساق عام ============================
def _all_actions():
    """كل الإجراءات المشار إليها في الأوامر (بسيطة أو ضمن خطوات)."""
    for spec in load_command_specs(ROOT / "src" / "config"):
        if spec.get("action"):
            yield spec["action"]
        for step in spec.get("steps") or ():
            if step.get("action"):
                yield step["action"]


def test_every_default_command_maps_to_registered_action():
    missing = sorted({a for a in _all_actions() if a not in REGISTRY})
    assert not missing, f"أوامر بلا إجراء مسجّل: {missing}"


# إجراءات يقصد بها الإيماءات/الماكرو/الواجهة لا النطق الصوتي:
# mouse_down/mouse_up = ضغط/رفع مستمر (السحب)، move_mouse = إحداثيات
# (وضع الشبكة)، run = تشغيل ماكرو. نطقها بلا معنى.
# app.set_profile: أوامره الصوتية تُولَّد من الملفات الشخصية (config/profiles.py: switch_specs).
GESTURE_ONLY_ACTIONS = {"mouse_down", "mouse_up", "move_mouse", "run", "app.set_profile"}


def test_every_registered_action_has_a_voice_command_or_is_gesture_only():
    mapped = set(_all_actions())
    orphans = sorted(a for a in REGISTRY
                     if a not in mapped and a not in GESTURE_ONLY_ACTIONS)
    assert not orphans, f"إجراءات بلا أمر صوتي: {orphans}"


def test_gesture_only_actions_are_really_gesture_only():
    """حارس ضد تسرّب إجراء جديد إلى هذه القائمة دون سبب."""
    mapped = set(_all_actions())
    stale = sorted(GESTURE_ONLY_ACTIONS & mapped)
    assert not stale, f"أصبح لها أمر صوتي، أخرجها من القائمة: {stale}"


def test_every_action_error_key_is_translated():
    """كل ActionError في actions.py يجب أن له نص عربي/إنجليزي/فرنسي."""
    source = (ROOT / "src" / "commands" / "actions.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'ActionError\(\s*"([a-z_]+)"', source))
    assert keys, "لم يُعثر على أي ActionError"
    for key in sorted(keys):
        assert key in STRINGS, f"مفتاح ترجمة مفقود: {key}"
        assert STRINGS[key].get("ar") and STRINGS[key].get("en"), f"ترجمة ناقصة: {key}"
        assert FR.get(key), f"نص فرنسي مفقود: {key}"


def test_new_actions_expose_only_documented_positions():
    """snap يقبل المواضع التي يولّدها snap_rect فقط."""
    from os_layer.windows import winapi
    work = (0, 0, 1920, 1040)
    valid = {"left", "right", "top", "bottom", "topleft", "topright",
             "bottomleft", "bottomright", "thirdleft", "thirdright",
             "maximize", "restore"}
    for position in valid:
        if position in ("maximize", "restore"):
            continue
        assert winapi.snap_rect(position, work) is not None, position
    assert winapi.snap_rect("sideways", work) is None


def test_snap_rect_geometry_is_inside_work_area():
    from os_layer.windows import winapi
    work = (0, 0, 1920, 1040)
    for position in ("left", "right", "top", "bottom",
                     "topleft", "topright", "bottomleft", "bottomright",
                     "thirdleft", "thirdright"):
        x, y, w, h = winapi.snap_rect(position, work)
        assert w > 0 and h > 0, position
        assert x >= work[0] and y >= work[1], position
        assert x + w <= work[0] + work[2], position
        assert y + h <= work[1] + work[3], position


def test_window_actions_are_foreground_based():
    """تأكيد أن الواجهة العامة تعتمد النافذة الأمامية لا نافذة عشوائية."""
    from os_layer.windows.backend import WindowsBackend
    src = inspect.getsource(WindowsBackend._target_window)
    assert "GetForegroundWindow" in src
