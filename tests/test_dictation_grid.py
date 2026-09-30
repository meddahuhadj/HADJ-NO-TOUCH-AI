"""اختبارات الإملاء والشبكة الصوتية: المنطق البحت + التكامل مع الموزّع."""
import pytest

from commands.dictation import DictationSession, apply_spoken_punctuation, classify_command, is_hallucination
from commands.grid import GridState, center, parse_grid_command, parse_number, split_rect
from core.events import DictationEvent, SpeechEvent


# ============================ الترقيم ============================
@pytest.mark.parametrize("text,lang,expected", [
    ("مرحبا فاصلة كيف حالك علامة استفهام", "ar", "مرحبا، كيف حالك؟"),
    ("السلام عليكم نقطة", "ar", "السلام عليكم."),
    ("السطر الأول سطر جديد السطر الثاني", "ar", "السطر الأول\nالسطر الثاني"),
    ("قائمة نقطتان تفاح", "ar", "قائمة: تفاح"),
    ("hello comma world full stop", "en", "hello, world."),
    ("really question mark new line yes", "en", "really?\nyes"),
    ("مرحبا بالعالم", "ar", "مرحبا بالعالم"),
])
def test_spoken_punctuation(text, lang, expected):
    assert apply_spoken_punctuation(text, lang) == expected


def test_session_spacing_between_chunks():
    s = DictationSession("ar")
    t1 = s.render("مرحبا")
    s.commit(t1)
    t2 = s.render("كيف حالك")
    s.commit(t2)
    t3 = s.render("فاصلة أنا بخير")
    s.commit(t3)
    assert t1 + t2 + t3 == "مرحبا كيف حالك، أنا بخير"


def test_session_strips_whisper_auto_period_but_keeps_spoken_one():
    s = DictationSession("en")
    assert s.render("Hello there.") == "Hello there"
    s2 = DictationSession("en")
    assert s2.render("hello there period") == "Hello there."


def test_english_capitalization_after_sentence_end():
    s = DictationSession("en")
    t = s.render("hello full stop how are you")
    s.commit(t)
    assert t == "Hello. How are you"
    t2 = s.render("fine")
    assert t2 == " fine"
    s.commit(t2)
    t3 = s.render("question mark")
    assert t3 == "?"


def test_session_undo():
    s = DictationSession("ar")
    for chunk in ["مرحبا", "بالعالم"]:
        s.commit(s.render(chunk))
    assert s.undo() == len(" بالعالم")
    assert s.last_char == "ا"
    assert s.undo() == len("مرحبا")
    assert s.undo() == 0


@pytest.mark.parametrize("text,lang,cmd", [
    ("أوقف الإملاء", "ar", "stop"), ("إنهاء الإملاء", "ar", "stop"), ("stop dictation", "en", "stop"),
    ("امسح ذلك", "ar", "undo"), ("scratch that", "en", "undo"), ("مرحبا", "ar", None),
])
def test_dictation_commands(text, lang, cmd):
    assert classify_command(text, lang) == cmd


@pytest.mark.parametrize("text,expected", [
    ("شكراً للمشاهدة", True), ("Thank you.", True), ("", True), ("  ", True),
    ("مرحبا بكم في الاجتماع", False), ("thank you for the report", False),
])
def test_hallucination_filter(text, expected):
    assert is_hallucination(text) is expected


def test_hallucination_by_scores():
    assert is_hallucination("كلام", no_speech_prob=0.9, avg_logprob=-1.5)
    assert not is_hallucination("كلام", no_speech_prob=0.9, avg_logprob=-0.3)


# ============================ الشبكة ============================
SCREEN = (0, 0, 1920, 1080)


def test_split_rect_keypad_order():
    assert split_rect(SCREEN, 1) == (0, 0, 640, 360)
    assert split_rect(SCREEN, 3) == (1280, 0, 640, 360)
    assert split_rect(SCREEN, 5) == (640, 360, 640, 360)
    assert split_rect(SCREEN, 9) == (1280, 720, 640, 360)
    # الخانات تغطي الشاشة كلها دون فجوات
    assert sum(split_rect(SCREEN, n)[2] * split_rect(SCREEN, n)[3] for n in range(1, 10)) == 1920 * 1080


def test_split_rect_multi_monitor_offset():
    assert split_rect((-1920, 0, 1920, 1080), 1) == (-1920, 0, 640, 360)


def test_grid_zoom_and_back():
    g = GridState(SCREEN)
    assert g.target == (960, 540)
    g.select(1)
    g.select(9)
    assert g.rect == (426, 240, 214, 120) and g.level == 2
    assert center(g.rect) == g.target
    g.back()
    assert g.rect == (0, 0, 640, 360)
    assert not GridState(SCREEN).select(0)


def test_grid_stops_splitting_when_tiny():
    g = GridState(SCREEN)
    while g.can_split:
        g.select(5)
    assert g.rect[2] < 36 or g.rect[3] < 36


@pytest.mark.parametrize("text,lang,n", [
    ("خمسة", "ar", 5), ("خمسه", "ar", 5), ("5", "ar", 5), ("٥", "ar", 5), ("ثلاثة", "ar", 3),
    ("تلاتة", "ar", 3), ("اثنين", "ar", 2), ("رقم سبعة", "ar", 7), ("ثمانية", "ar", 8),
    ("five", "en", 5), ("to", "en", 2), ("for", "en", 4), ("number nine", "en", 9),
    ("مرحبا", "ar", None), ("خمسة وعشرون", "ar", None), ("0", "ar", None), ("ten", "en", None),
])
def test_parse_number(text, lang, n):
    assert parse_number(text, lang) == n


@pytest.mark.parametrize("text,lang,cmd", [
    ("انقر", "ar", "click"), ("انقر مرتين", "ar", "double_click"), ("انقر يمين", "ar", "right_click"),
    ("رجوع", "ar", "back"), ("إلغاء", "ar", "close"), ("click", "en", "click"), ("cancel", "en", "close"),
    ("خمسة", "ar", None),
])
def test_parse_grid_command(text, lang, cmd):
    assert parse_grid_command(text, lang) == cmd


# ============================ التكامل مع الموزّع ============================
seg = iter(range(1, 10_000))


def say(env, text, lang="ar", free=None):
    sid = next(seg)
    env.disp.handle(SpeechEvent(text=text, free_text=free if free is not None else text, lang=lang, seg_id=sid))
    return sid


def dictated(env, sid, text, lang="ar"):
    env.disp.handle(DictationEvent(text, sid, lang))


def typed(env):
    return "".join(c[1] for c in env.os.calls if c[0] == "type_text")


def test_dictation_flow(env):
    say(env, "حاسوب ابدأ الإملاء")
    assert env.disp.mode is not None and env.disp.mode.name == "dictation"
    s1 = say(env, "مرحبا بكم")            # بلا كلمة تنبيه
    s2 = say(env, "فاصلة كيف الحال")
    dictated(env, s1, "مرحبا بكم.")         # Whisper يضيف نقطة
    dictated(env, s2, "فاصلة كيف الحال")
    assert typed(env) == "مرحبا بكم، كيف الحال"
    assert not any(c[0] == "hotkey" for c in env.os.calls)   # لم تُنفَّذ كأوامر


def test_dictation_does_not_execute_command_words(env):
    say(env, "حاسوب ابدأ الإملاء")
    sid = say(env, "انسخ")          # كلمة أمر، لكنها في الإملاء نص
    dictated(env, sid, "انسخ")
    assert typed(env) == "انسخ"
    assert not any(c[0] == "hotkey" for c in env.os.calls)


def test_dictation_command_with_wake_word_executes(env):
    say(env, "حاسوب ابدأ الإملاء")
    sid = say(env, "حاسوب احفظ")
    dictated(env, sid, "حاسوب احفظ")
    assert ("hotkey", "ctrl", "s") in env.os.calls
    assert typed(env) == ""
    assert env.disp.mode.name == "dictation"


def test_stop_dictation_drains_pending_text(env):
    say(env, "حاسوب ابدأ الإملاء")
    s1 = say(env, "جملة أخيرة")
    s2 = say(env, "أوقف الإملاء")
    assert env.disp.mode is None
    assert env.mode_exits == [("dictation", False)]
    dictated(env, s2, "أوقف الإملاء")     # نص الأمر نفسه لا يُكتب
    dictated(env, s1, "جملة أخيرة")       # يصل متأخراً بعد الخروج ويُكتب
    assert typed(env) == "جملة أخيرة"


def test_undo_in_dictation(env):
    say(env, "حاسوب ابدأ الإملاء")
    s1 = say(env, "مرحبا")
    dictated(env, s1, "مرحبا")
    s2 = say(env, "امسح ذلك")
    dictated(env, s2, "امسح ذلك")
    assert ("key", "backspace", len("مرحبا")) in env.os.calls
    assert typed(env) == "مرحبا"


def test_emergency_stop_during_dictation_drops_pending(env):
    say(env, "حاسوب ابدأ الإملاء")
    s1 = say(env, "نص سري")
    say(env, "توقف")
    env.disp.exit_mode(abort=True)    # ما يفعله المتحكم عند الإيقاف
    dictated(env, s1, "نص سري")
    assert typed(env) == ""
    assert env.app.paused.is_set()


def test_hallucination_text_not_typed(env):
    say(env, "حاسوب ابدأ الإملاء")
    s1 = say(env, "همم")
    dictated(env, s1, "")            # Whisper رشّح الهلوسة ← نص فارغ
    assert typed(env) == ""


def test_grid_flow_click(env):
    say(env, "حاسوب اعرض الشبكة")
    grid = [d for k, d in env.notes if k == "grid"]
    assert grid[-1]["rect"] == (0, 0, 1920, 1080)
    say(env, "خمسة")                     # بلا كلمة تنبيه
    assert env.os.pos == (960, 540)
    say(env, "ثلاثة")
    assert env.os.pos == (1173, 420)
    say(env, "انقر")
    assert env.os.calls[-1] == ("mouse", "left", "click", 1)
    assert env.disp.mode is None


def test_grid_back_and_cancel(env):
    say(env, "حاسوب اعرض الشبكة")
    say(env, "واحد")
    say(env, "رجوع")
    assert env.disp.mode.state.level == 0
    say(env, "إلغاء")
    assert env.disp.mode is None
    assert not any(c[0] == "mouse" for c in env.os.calls)


def test_grid_right_click_english(env):
    env.gate.wake_words = ["computer"]
    say(env, "computer show grid", lang="en")
    say(env, "nine", lang="en")
    say(env, "right click", lang="en")
    assert env.os.calls[-1] == ("mouse", "right", "click", 1)


def test_grid_ignores_chatter_and_times_out(env):
    say(env, "حاسوب اعرض الشبكة")
    say(env, "كلام لا علاقة له")
    assert env.disp.mode is not None and env.os.calls == []
    env.clock.advance(31)
    env.disp.tick()
    assert env.disp.mode is None


def test_grid_wake_command_closes_grid(env):
    say(env, "حاسوب اعرض الشبكة")
    say(env, "حاسوب انسخ")
    assert env.disp.mode is None
    assert ("hotkey", "ctrl", "c") in env.os.calls


def test_emergency_stop_in_grid(env):
    say(env, "حاسوب اعرض الشبكة")
    say(env, "توقف")
    assert env.app.paused.is_set()
