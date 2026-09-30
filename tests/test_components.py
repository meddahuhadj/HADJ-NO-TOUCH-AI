"""اختبارات: بوابة التنبيه، مقطّع الصوت، فهرس التطبيقات، الإعدادات، حارس عدم الاتصال."""
import socket

import pytest
import yaml

from audio.vad import FRAME_BYTES, Segmenter
from commands.wake import WakeGate, strip_wake
from config import loader
from core import offline_guard
from os_layer.apps_index import AppIndex
from os_layer.base import AppEntry


# ---------------- كلمة التنبيه ----------------
@pytest.mark.parametrize("text,found,rest", [
    ("حاسوب افتح المفكرة", True, "افتح المفكرة"),
    ("الحاسوب انسخ", True, "انسخ"),
    ("يا حاسوب انسخ", True, "انسخ"),
    ("حاسوب", True, ""),
    ("انسخ", False, "انسخ"),
    ("حسوب انسخ", True, "انسخ"),       # خطأ تعرف بسيط
    ("حساب البنك", False, "حساب البنك"),
])
def test_strip_wake_ar(text, found, rest):
    assert strip_wake(text, ["حاسوب"]) == (found, rest)


def test_strip_wake_multiword():
    assert strip_wake("hey jarvis open chrome", ["jarvis"]) == (True, "open chrome")
    assert strip_wake("ok computer copy", ["ok computer"]) == (True, "copy")


def test_gate_timing():
    t = [0.0]
    g = WakeGate(["computer"], timeout_s=5, followup_s=0, clock=lambda: t[0])
    assert g.process("copy") == (None, False)
    assert g.process("computer") == (None, True)
    assert g.armed
    t[0] = 4
    assert g.process("copy") == ("copy", False)
    g.after_command()  # followup_s = 0 ← لا تمديد
    t[0] = 6
    assert not g.armed


# ---------------- مقطّع الصوت ----------------
def run_segmenter(pattern, **kw):
    seg = Segmenter(**kw)
    events = []
    for voiced in pattern:
        for kind, data in seg.push(b"\0" * FRAME_BYTES, voiced):
            events.append(kind)
    return events


def test_segmenter_detects_utterance_with_preroll():
    pattern = [False] * 20 + [True] * 30 + [False] * 30
    ev = run_segmenter(pattern, silence_ms=600, preroll_ms=300)
    assert ev.count("start") == 1 and ev.count("end") == 1
    # 10 إطارات سابقة (300ms) + الكلام + الصمت حتى النهاية
    assert ev.count("audio") == 10 + (30 - 3) + 20


def test_segmenter_ignores_clicks():
    pattern = ([False] * 5 + [True]) * 10
    assert "start" not in run_segmenter(pattern)


def test_segmenter_max_length():
    ev = run_segmenter([True] * 500, max_ms=3000)
    assert ev.count("end") >= 4


def test_segmenter_two_utterances():
    p = [True] * 20 + [False] * 25 + [True] * 20 + [False] * 25
    ev = run_segmenter(p, silence_ms=600)
    assert ev.count("start") == 2 and ev.count("end") == 2


# ---------------- فهرس التطبيقات ----------------
APPS = [AppEntry("Google Chrome", "chrome", "appid"), AppEntry("Microsoft Word", "word", "appid"),
        AppEntry("Microsoft Excel", "excel", "appid"), AppEntry("Notepad++", "npp", "appid"),
        AppEntry("الحاسبة", "calc-ar", "appid")]


@pytest.fixture
def index(tmp_path):
    idx = AppIndex(lambda: APPS, {"كروم": "Google Chrome", "المفكرة": "notepad.exe",
                                  "وورد": "Word", "الاعدادات": "ms-settings:"},
                   cache_path=tmp_path / "apps.json")
    idx.refresh()
    return idx


@pytest.mark.parametrize("spoken,target", [
    ("كروم", "chrome"), ("chrome", "chrome"), ("google chrome", "chrome"),
    ("وورد", "word"), ("word", "word"), ("excel", "excel"), ("exel", "excel"),
    ("المفكرة", "notepad.exe"), ("مفكرة", "notepad.exe"), ("الإعدادات", "ms-settings:"),
    ("notepad plus plus", None), ("الحاسبه", "calc-ar"),
])
def test_app_find(index, spoken, target):
    e = index.find(spoken)
    assert (e.target if e else None) == target or (target is None)


def test_app_unknown(index):
    assert index.find("برنامج لا وجود له") is None
    assert index.find("") is None


def test_app_cache_roundtrip(index, tmp_path):
    other = AppIndex(lambda: [], cache_path=tmp_path / "apps.json")
    assert other.load_cache()
    assert other.find("excel").target == "excel"


# ---------------- الإعدادات ----------------
def test_default_config_is_valid(tmp_path):
    cfg = loader.load_config(tmp_path)
    assert cfg.speech.language == "ar"
    assert cfg.speech.wake_words["ar"] == ["حاسوب"]
    assert cfg.app_aliases["المفكرة"] == "notepad.exe"


def test_user_config_overrides_and_merges(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "speech:\n  language: en\napp_aliases:\n  بريدي: outlook.exe\n", encoding="utf-8")
    cfg = loader.load_config(tmp_path)
    assert cfg.speech.language == "en"
    assert cfg.speech.wake_timeout_s == 5          # القيم الأخرى باقية
    assert cfg.app_aliases["بريدي"] == "outlook.exe"
    assert "المفكرة" in cfg.app_aliases            # الأسماء الافتراضية باقية


def test_broken_user_config_falls_back(tmp_path):
    (tmp_path / "config.yaml").write_text("speech: [unclosed", encoding="utf-8")
    assert loader.load_config(tmp_path).speech.language == "ar"


def test_update_user_config_writes_only_changes(tmp_path):
    loader.update_user_config({"speech": {"language": "en"}}, tmp_path)
    loader.update_user_config({"speech": {"continuous_listening": True}}, tmp_path)
    data = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert data == {"speech": {"language": "en", "continuous_listening": True}}


def test_custom_commands_override_defaults(tmp_path):
    (tmp_path / "custom_commands.yaml").write_text(
        "commands:\n  - id: copy\n    phrases: {ar: ['انسخ هذا']}\n    action: hotkey\n"
        "    args: {keys: [ctrl, insert]}\n", encoding="utf-8")
    specs = {s["id"]: s for s in loader.load_command_specs(tmp_path)}
    assert specs["copy"]["args"]["keys"] == ["ctrl", "insert"]
    assert "paste" in specs


# ---------------- حارس عدم الاتصال ----------------
def test_offline_guard_blocks_external_allows_loopback():
    offline_guard.install()
    with pytest.raises(offline_guard.OfflineViolation):
        socket.create_connection(("93.184.216.34", 80), timeout=1)
    with pytest.raises(offline_guard.OfflineViolation):
        socket.getaddrinfo("example.com", 80)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    c = socket.create_connection(srv.getsockname(), timeout=1)
    c.close()
    srv.close()
