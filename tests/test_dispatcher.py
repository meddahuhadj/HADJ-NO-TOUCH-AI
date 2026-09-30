"""اختبارات تكامل الموزّع: بوابة التنبيه + المحلل + التأكيد + الإيقاف، بطبقة نظام وهمية."""
from core.events import SpeechEvent


def say(env, text, free=None, lang="ar"):
    env.disp.handle(SpeechEvent(text=text, free_text=free if free is not None else text, lang=lang))


def kinds(env):
    return [k for k, _ in env.notes]


def test_command_without_wake_word_is_ignored(env):
    say(env, "انسخ")
    assert env.os.calls == []


def test_wake_word_plus_command(env):
    say(env, "حاسوب انسخ")
    assert env.os.calls == [("hotkey", "ctrl", "c")]


def test_wake_word_with_article_and_ya(env):
    say(env, "يا الحاسوب الصق")
    assert env.os.calls == [("hotkey", "ctrl", "v")]


def test_wake_word_alone_arms_then_command(env):
    say(env, "حاسوب")
    assert "wake" in kinds(env) and env.os.calls == []
    env.clock.advance(2)
    say(env, "تراجع")
    assert env.os.calls == [("hotkey", "ctrl", "z")]


def test_armed_window_expires(env):
    say(env, "حاسوب")
    env.clock.advance(6)
    say(env, "تراجع")
    assert env.os.calls == []


def test_followup_without_wake_word(env):
    say(env, "حاسوب مرر للأسفل")
    env.clock.advance(3)
    say(env, "مرر للأسفل")
    assert env.os.calls == [("scroll", -5, False), ("scroll", -5, False)]
    env.clock.advance(7)
    say(env, "مرر للأسفل")
    assert len(env.os.calls) == 2


def test_continuous_mode(env):
    env.gate.continuous = True
    say(env, "احفظ")
    assert env.os.calls == [("hotkey", "ctrl", "s")]


def test_emergency_stop_needs_no_wake_word(env):
    say(env, "توقف فورا")
    assert env.app.calls == ["pause"]
    assert env.app.paused.is_set()


def test_paused_blocks_commands_but_allows_resume(env):
    say(env, "توقف")
    say(env, "حاسوب انسخ")
    assert env.os.calls == []
    assert any(k == "result" and d["key"] == "paused" for k, d in env.notes)
    say(env, "حاسوب استأنف")
    assert not env.app.paused.is_set()
    say(env, "حاسوب انسخ")
    assert env.os.calls == [("hotkey", "ctrl", "c")]


def test_dangerous_command_requires_confirmation_yes(env):
    say(env, "حاسوب احذف")
    assert env.os.calls == []
    assert "confirm" in kinds(env)
    say(env, "نعم")  # بلا كلمة تنبيه
    assert env.os.calls == [("key", "delete", 1)]


def test_dangerous_command_cancelled(env):
    say(env, "حاسوب أطفئ الجهاز")
    say(env, "لا")
    assert env.os.calls == []
    assert ("confirm_cleared", {"executed": False}) in env.notes


def test_confirmation_times_out(env):
    say(env, "حاسوب احذف")
    env.clock.advance(9)
    say(env, "نعم")
    assert env.os.calls == []


def test_unrelated_speech_during_confirmation_keeps_waiting(env):
    say(env, "حاسوب احذف")
    say(env, "ما هذا")
    assert env.disp.pending is not None
    say(env, "أكد")
    assert env.os.calls == [("key", "delete", 1)]


def test_emergency_stop_cancels_confirmation(env):
    say(env, "حاسوب احذف")
    say(env, "توقف")
    assert env.disp.pending is None
    say(env, "نعم")
    assert env.os.calls == []


def test_confirmation_can_be_disabled(env):
    env.config.safety.confirm_dangerous = False
    say(env, "حاسوب احذف")
    assert env.os.calls == [("key", "delete", 1)]


def test_open_app_via_alias(env):
    say(env, "حاسوب افتح المفكرة")
    assert env.os.calls == [("launch", "notepad.exe")]


def test_open_app_via_index_fuzzy(env):
    say(env, "حاسوب افتح كروم")
    say(env, "computer open visual studio code", lang="en")
    assert env.os.calls[0] == ("launch", "Chrome")


def test_open_unknown_app_reports_error(env):
    say(env, "حاسوب افتح برنامج غير موجود ابدا")
    assert env.os.calls == []
    res = [d for k, d in env.notes if k == "result"][-1]
    assert res["ok"] is False and res["key"] == "app_not_found"


def test_grammar_unk_slot_uses_free_text(env):
    env.gate.wake_words = ["computer"]
    say(env, "computer search for [unk]", free="computer search for weather today", lang="en")
    assert env.os.calls == [("open_search",), ("type_text", "weather today")]


def test_grammar_unk_rejects_non_slot_command(env):
    env.gate.continuous = True
    say(env, "[unk] launch new", free="i think we should have lunch at noon", lang="en")
    assert env.os.calls == []


def test_grammar_result_preferred_for_fixed_commands(env):
    env.gate.wake_words = ["computer"]
    say(env, "computer close window", free="computer clothes window", lang="en")
    assert env.os.calls == [("close_window",)]


def test_no_window_error(env):
    env.os.window = False
    say(env, "حاسوب أغلق النافذة")
    res = [d for k, d in env.notes if k == "result"][-1]
    assert res["ok"] is False and res["key"] == "no_window"


def test_not_understood_after_wake(env):
    say(env, "حاسوب كلام غير مفهوم تماما")
    res = [d for k, d in env.notes if k == "result"][-1]
    assert res["key"] == "not_understood"


def test_sleep_disarms_followup(env):
    say(env, "حاسوب نم")
    say(env, "انسخ")
    assert env.os.calls == []


def test_action_exception_does_not_crash(env):
    def boom(*a, **k):
        raise RuntimeError("x")
    env.os.hotkey = boom
    say(env, "حاسوب انسخ")
    res = [d for k, d in env.notes if k == "result"][-1]
    assert res["key"] == "action_failed"
    say(env, "حاسوب مرر للأسفل")
    assert env.os.calls[-1][0] == "scroll"


def test_execute_steps_blocked_while_paused(env):
    env.app.paused.set()
    assert env.disp.execute_steps([{"action": "click"}], "gesture") is False
    env.app.paused.clear()
    assert env.disp.execute_steps([{"action": "click"}], "gesture") is True
    assert env.os.calls == [("mouse", "left", "click", 1)]


def test_gesture_events_route_to_app_and_actions(env):
    from core.events import GestureEvent
    env.disp.handle(GestureEvent("fist_hold", {"action": "app.pause"}))
    assert env.app.calls == ["pause"]
    env.disp.handle(GestureEvent("palm_hold_long", {"action": "show_desktop"}))
    assert env.os.calls == []                       # متوقف ← لا تنفيذ
    env.disp.handle(GestureEvent("palm_hold_short", {"action": "app.resume"}))
    env.disp.handle(GestureEvent("palm_hold_long", {"action": "show_desktop"}))
    assert env.os.calls == [("show_desktop",)]
    env.disp.handle(GestureEvent("pinch_tap", {"action": ""}))   # إشعار فقط
    assert env.os.calls == [("show_desktop",)]
    assert [d["name"] for k, d in env.notes if k == "gesture"][-1] == "pinch_tap"


def test_gesture_swipe_left_switches_to_previous_window(env):
    from core.events import GestureEvent
    env.disp.handle(GestureEvent("swipe_left", {"action": "switch_window_prev"}))
    assert env.os.calls == [("hotkey", "alt", "shift", "tab")]


def test_voice_zoom_commands(env):
    say(env, "حاسوب كبر الخط")
    say(env, "صغر الخط")
    assert env.os.calls == [("zoom", 2), ("zoom", -2)]
