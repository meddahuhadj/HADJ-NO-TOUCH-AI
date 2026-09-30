import pytest

from commands.actions import REGISTRY
from commands.parser import CommandParser, is_no, is_yes
from commands.text import normalize


@pytest.mark.parametrize("raw,expected", [
    ("أغلِقْ النافذةَ", "اغلق النافذه"),
    ("إفتح  المفكرة!", "افتح المفكره"),
    ("مرّر للأسفل", "مرر للاسفل"),
    ("Close  Window.", "close window"),
    ("ـــتراجعـ", "تراجع"),
    ("٣ مرات", "3 مرات"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("text,cmd", [
    ("أغلق النافذة", "close_window"),
    ("اغلق النافذه", "close_window"),
    ("صغّر", "minimize"),
    ("كبّر النافذة", "maximize"),
    ("بدّل النافذة", "switch_window"),
    ("انسخ", "copy"),
    ("الصق", "paste"),
    ("تراجع", "undo"),
    ("احفظ", "save"),
    ("مرّر للأسفل", "scroll_down"),
    ("مرر للأعلى", "scroll_up"),
    ("انقر", "click"),
    ("انقر مرتين", "double_click"),
    ("انقر بالزر الأيمن", "right_click"),
    ("ارفع الصوت", "volume_up"),
    ("اخفض الصوت", "volume_down"),
    ("كتم الصوت", "mute"),
    ("اقفل الشاشة", "lock_screen"),
    ("لقطة شاشة", "screenshot"),
    ("توقف فورا", "emergency_stop"),
    ("بدل اللغة", "switch_language"),
])
def test_arabic_exact(parser, text, cmd):
    m = parser.parse(text, "ar")
    assert m is not None and m.id == cmd


@pytest.mark.parametrize("text,cmd", [
    ("close window", "close_window"),
    ("Minimize", "minimize"),
    ("copy", "copy"),
    ("scroll down", "scroll_down"),
    ("double click", "double_click"),
    ("right click", "right_click"),
    ("volume up", "volume_up"),
    ("stop now", "emergency_stop"),
    ("take a screenshot", "screenshot"),
])
def test_english_exact(parser, text, cmd):
    m = parser.parse(text, "en")
    assert m is not None and m.id == cmd


def test_exact_beats_prefix_of_longer_phrase(parser):
    # "بدل" وحدها = بدّل النافذة، و"بدل اللغة" أمر آخر
    assert parser.parse("بدل", "ar").id == "switch_window"
    assert parser.parse("بدل اللغة", "ar").id == "switch_language"
    assert parser.parse("اغلق", "ar").id == "close_window"
    assert parser.parse("اغلق بدون حفظ", "ar").id == "close_without_saving"


@pytest.mark.parametrize("text,cmd", [
    ("اغلق النافذ", "close_window"),        # خطأ تعرف: حرف ناقص
    ("مرر الى الاسفل", "scroll_down"),       # صياغة قريبة
    ("scroll dawn", "scroll_down"),
    ("clothes window", "close_window"),
])
def test_fuzzy(parser, text, cmd):
    m = parser.parse(text, "ar" if not text.isascii() else "en")
    assert m is not None and m.id == cmd
    assert m.score < 200


def test_short_phrases_need_exact_match(parser):
    # "قص" قصيرة جداً: "قصر" يجب ألا تُفهم كأمر قص
    assert parser.parse("قصر", "ar") is None
    assert parser.parse("قص", "ar").id == "cut"


def test_unrelated_speech_not_matched(parser):
    assert parser.parse("ما هو الطقس اليوم في المدينة", "ar") is None
    assert parser.parse("I think we should have lunch at noon", "en") is None


def test_slot_keeps_original_spelling(parser):
    m = parser.parse("ابحث عن أسعار الذهب", "ar")
    assert m.id == "search"
    assert m.slots == {"text": "أسعار الذهب"}  # الهمزة محفوظة
    m = parser.parse("إفتح المفكرة", "ar")
    assert m.id == "open_app" and m.slots == {"app": "المفكرة"}
    m = parser.parse("search for Weather Today", "en")
    assert m.slots == {"text": "Weather Today"}


def test_slot_prefers_longest_prefix(parser):
    m = parser.parse("search for cats", "en")
    assert m.slots["text"] == "cats"


def test_slot_requires_value(parser):
    assert parser.parse("افتح", "ar") is None


def test_fillers_are_ignored(parser):
    assert parser.parse("من فضلك انسخ", "ar").id == "copy"
    assert parser.parse("انسخ لو سمحت", "ar").id == "copy"
    assert parser.parse("please close window", "en").id == "close_window"


def test_only_always(parser):
    assert parser.parse("انسخ", "ar", only_always=True) is None
    assert parser.parse("توقف", "ar", only_always=True).id == "emergency_stop"


def test_language_isolation(parser):
    assert parser.parse("copy", "ar") is None


def test_custom_macro_and_override():
    specs = [
        {"id": "copy", "phrases": {"ar": ["انسخ"]}, "action": "hotkey", "args": {"keys": ["ctrl", "c"]}},
        {"id": "mail", "phrases": ["open my mail", "افتح بريدي"],
         "steps": [{"action": "hotkey", "keys": ["win", "r"]}, {"action": "type_text", "text": "outlook"}]},
        {"id": "bad", "phrases": {"ar": ["{x} في الوسط"]}, "action": "key", "args": {"key": "a"}},
        {"id": "broken"},  # بلا action ولا steps ← يُتجاهل
    ]
    p = CommandParser(specs)
    m = p.parse("افتح بريدي", "ar")
    assert m.id == "mail" and len(m.spec.steps) == 2
    assert p.parse("open my mail", "en").id == "mail"   # عبارات بلا لغة = كل اللغات
    assert p.parse("في الوسط", "ar") is None


def test_default_commands_use_known_actions(specs):
    for s in specs:
        steps = s.get("steps") or [{"action": s["action"]}]
        for st in steps:
            assert st["action"] in REGISTRY, (s["id"], st["action"])


def test_default_commands_have_both_languages(specs):
    for s in specs:
        assert set(s["phrases"]) == {"ar", "en", "fr"}, s["id"]


def test_no_duplicate_phrases_across_commands(parser):
    for lang in ("ar", "en"):
        seen = {}
        for t in parser.templates(lang):
            key = (t.joined, t.slot is not None)
            assert key not in seen or seen[key] == t.spec.id, (lang, t.joined, seen.get(key), t.spec.id)
            seen[key] = t.spec.id


@pytest.mark.parametrize("text,lang,yes,no", [
    ("نعم", "ar", True, False), ("أكّد", "ar", True, False), ("لا", "ar", False, True),
    ("إلغاء", "ar", False, True), ("yes", "en", True, False), ("cancel", "en", False, True),
    ("انسخ", "ar", False, False),
])
def test_yes_no(text, lang, yes, no):
    assert is_yes(text, lang) is yes
    assert is_no(text, lang) is no
