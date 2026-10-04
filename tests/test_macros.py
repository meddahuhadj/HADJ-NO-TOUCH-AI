"""الماكرو: التحقق، قواعد الأمان (التأكيد الإجباري، اختصار الطوارئ، الإيماءات)، والتكامل والواجهة."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from config import macros as mac  # noqa: E402
from config.loader import load_command_specs  # noqa: E402
from core.events import GestureEvent, SpeechEvent  # noqa: E402


@pytest.fixture(scope="module")
def owners():
    return mac.phrase_owners(load_command_specs())


def keys(combo):
    return {"kind": "keys", "keys": combo}


# ---------------- الخطوات ----------------
def test_every_editor_key_exists_on_windows():
    from os_layer.windows.input import VK
    assert [k for k in mac.KEYS if k not in VK] == []


@pytest.mark.parametrize("step,expected", [
    (keys("ctrl+x"), {"action": "hotkey", "keys": "ctrl+x"}),
    (keys("Shift + Ctrl + S"), {"action": "hotkey", "keys": "ctrl+shift+s"}),   # ترتيب ثابت
    (keys("f5"), {"action": "key", "key": "f5"}),
    ({"kind": "text", "text": "Bonjour"}, {"action": "type_text", "text": "Bonjour"}),
    ({"kind": "wait", "ms": 400}, {"action": "wait", "ms": 400}),
    ({"kind": "right_click"}, {"action": "right_click"}),
    ({"kind": "scroll_up"}, {"action": "scroll", "direction": "up"}),
])
def test_step_conversion_roundtrip(step, expected):
    a = mac.step_to_action(step)
    assert a == expected
    assert mac.step_to_action(mac.action_to_step(a)) == a


@pytest.mark.parametrize("bad", [keys("ctrl+"), keys("hyper+x"), keys("ctrl+ctrl+x"), keys("ctrl+é"),
                                 {"kind": "text", "text": ""}, {"kind": "text", "text": "x" * 501},
                                 {"kind": "wait", "ms": 10}, {"kind": "wait", "ms": 60000},
                                 {"kind": "shell", "cmd": "del *"}])
def test_bad_steps_rejected(bad):
    with pytest.raises(mac.MacroError):
        mac.step_to_action(bad)


@pytest.mark.parametrize("combo,destructive", [
    ("delete", True), ("shift+delete", True), ("alt+f4", True), ("ctrl+w", True),
    ("ctrl+x", False), ("ctrl+c", False), ("ctrl+z", False), ("enter", False)])
def test_destructive_detection(combo, destructive):
    assert mac.is_destructive([mac.step_to_action(keys(combo))]) is destructive


# ---------------- بناء الماكرو ----------------
def test_simple_macro(owners):
    spec = mac.build_macro({"phrases": {"fr": "copie spéciale"}, "steps": [keys("ctrl+shift+v")]}, owners)
    assert spec == {"id": "macro.copie_sp_ciale", "phrases": {"fr": ["copie spéciale"]},
                    "steps": [{"action": "hotkey", "keys": "ctrl+shift+v"}]}


def test_destructive_macro_always_confirms_and_has_no_gesture(owners):
    spec = mac.build_macro({"phrases": {"fr": "efface tout"}, "steps": [keys("ctrl+a"), keys("delete")],
                            "dangerous": False}, owners)
    assert spec["dangerous"] is True                      # لا يمكن إلغاء التأكيد
    with pytest.raises(mac.MacroError) as e:
        mac.build_macro({"phrases": {"fr": "efface tout"}, "steps": [keys("delete")],
                         "gesture": "swipe_left"}, owners)
    assert e.value.key == "macro_gesture_dangerous"


def test_emergency_hotkey_cannot_be_used(owners):
    with pytest.raises(mac.MacroError) as e:
        mac.build_macro({"phrases": {"fr": "pause secrète"}, "steps": [keys("shift+ctrl+alt+p")]},
                        owners, emergency_hotkey="ctrl+alt+shift+p")
    assert e.value.key == "macro_emergency_key"


def test_fist_cannot_be_taken_by_a_macro(owners):
    with pytest.raises(mac.MacroError) as e:
        mac.build_macro({"gesture": "fist_hold", "steps": [keys("ctrl+c")]}, owners)
    assert e.value.key == "macro_bad_gesture"


def test_phrase_collision_names_the_owner(owners):
    with pytest.raises(mac.MacroError) as e:
        mac.build_macro({"phrases": {"fr": "Coupe"}, "steps": [keys("ctrl+x")]}, owners)
    assert e.value.key == "macro_phrase_taken" and e.value.values["owner"] == "cut"


@pytest.mark.parametrize("data,key", [
    ({"phrases": {}, "steps": [keys("a")]}, "macro_no_trigger"),
    ({"phrases": {"fr": "rien"}, "steps": []}, "macro_no_steps"),
    ({"phrases": {"fr": "trop"}, "steps": [keys("a")] * 21}, "macro_too_many"),
    ({"phrases": {"fr": "ouvre {app}"}, "steps": [keys("a")]}, "macro_bad_phrase"),
])
def test_invalid_macros(owners, data, key):
    with pytest.raises(mac.MacroError) as e:
        mac.build_macro(data, owners)
    assert e.value.key == key


def test_arabic_only_phrase_gets_unique_id(owners):
    a = mac.build_macro({"phrases": {"ar": "انسخ النص الخاص"}, "steps": [keys("ctrl+c")]}, owners)
    b = mac.build_macro({"phrases": {"ar": "الصق النص الخاص"}, "steps": [keys("ctrl+v")]}, owners,
                        taken_ids={a["id"]})
    assert a["id"].startswith("macro.") and a["id"] != b["id"]


def test_hand_edited_file_is_validated(tmp_path):
    (tmp_path / "macros.yaml").write_text(
        "macros:\n"
        "  - {id: macro.ok, phrases: {fr: [signature]}, steps: [{action: type_text, text: Cordialement}]}\n"
        "  - {id: macro.evil, phrases: {fr: [piège]}, steps: [{action: run, target: 'cmd /c del *'}]}\n"
        "  - {id: macro.quiet, phrases: {fr: [ferme vite]}, steps: [{action: hotkey, keys: alt+f4}]}\n",
        encoding="utf-8")
    loaded = mac.load_macros(load_command_specs(), user_dir=tmp_path)
    assert [m["id"] for m in loaded] == ["macro.ok", "macro.quiet"]   # "run" ليس خطوة ماكرو
    assert loaded[1]["dangerous"] is True                            # alt+f4 ← تأكيد رغم الملف
    assert mac.bindings_for(loaded) == {}


def test_no_file_no_trace(tmp_path):
    assert mac.load_macros(load_command_specs(), user_dir=tmp_path) == []
    assert not (tmp_path / "macros.yaml").exists()


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
    monkeypatch.setattr(c.audio, "send", lambda kind, **p: c.sent.append(("audio", kind, p)))
    monkeypatch.setattr(c.vision, "send", lambda kind, **p: c.sent.append(("vision", kind, p)))
    yield c
    c.shutdown()


def say(c, text, lang="fr"):
    c.config.speech.continuous_listening = True
    c.gate.continuous = True
    c.config.speech.language = lang
    c.dispatcher.handle(SpeechEvent(text=text, lang=lang))


def test_voice_macro_runs(controller, tmp_path):
    c = controller
    c.save_macro({"phrases": {"fr": "signature"}, "steps": [{"kind": "text", "text": "Cordialement,"},
                                                           keys("enter")]})
    assert (tmp_path / "macros.yaml").exists()
    assert ("audio", "set_grammar") in [(w, k) for w, k, _ in c.sent]
    say(c, "signature")
    assert ("type_text", "Cordialement,") in c.os.calls and ("key", "enter", 1) in c.os.calls


def test_destructive_voice_macro_asks_first(controller):
    c = controller
    c.save_macro({"phrases": {"fr": "vide la corbeille du dossier"}, "steps": [keys("ctrl+a"), keys("delete")]})
    say(c, "vide la corbeille du dossier")
    assert c.dispatcher.pending is not None and ("key", "delete", 1) not in c.os.calls
    say(c, "non")
    assert c.dispatcher.pending is None and ("key", "delete", 1) not in c.os.calls


def test_gesture_macro(controller):
    c = controller
    spec = c.save_macro({"phrases": {}, "gesture": "palm_hold_long", "steps": [keys("win+d")]})
    assert c.effective_bindings()["palm_hold_long"] == f"cmd:{spec['id']}"
    c.dispatcher.handle(GestureEvent("palm_hold_long", {"action": f"cmd:{spec['id']}"}))
    assert ("hotkey", "win", "d") in c.os.calls
    # ملف شخصي يعيد تعريف الإيماءة يغلب الماكرو، والقبضة مقفلة دائماً
    c.set_profile("presentation")
    assert c.effective_bindings()["palm_hold_long"] == "cmd:presentation.black_screen"
    assert c.effective_bindings()["fist_hold"] == "app.pause"


def test_gesture_moves_to_newest_macro_and_delete(controller):
    c = controller
    a = c.save_macro({"phrases": {"fr": "macro a"}, "gesture": "swipe_left", "steps": [keys("a")]})
    b = c.save_macro({"phrases": {"fr": "macro b"}, "gesture": "swipe_left", "steps": [keys("b")]})
    assert [m.get("gesture") for m in c.macros] == [None, "swipe_left"]
    assert c.effective_bindings()["swipe_left"] == f"cmd:{b['id']}"
    edited = c.save_macro({"id": a["id"], "phrases": {"fr": "macro a modifiée"}, "steps": [keys("c")]})
    assert edited["id"] == a["id"] and [m["id"] for m in c.macros] == [a["id"], b["id"]]
    c.delete_macro(b["id"])
    assert c.effective_bindings()["swipe_left"] != f"cmd:{b['id']}"
    assert c.parser.parse("macro b", "fr") is None


def test_macro_phrase_cannot_shadow_profile_commands(controller):
    with pytest.raises(mac.MacroError) as e:
        controller.save_macro({"phrases": {"fr": "diapositive suivante"}, "steps": [keys("right")]})
    assert e.value.values["owner"] == "presentation.next_slide"


# ---------------- الواجهة ----------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_macros_tab_builds_and_saves(qapp, controller):
    from ui.i18n import Tr
    from ui.macros_tab import MacrosTab
    from ui.settings_window import _combo
    from ui.theme import theme
    tab = MacrosTab(Tr("fr"), theme(1.0, False), controller, _combo)
    tab.phrase["fr"].setText("ferme l'onglet vite")
    tab._add(keys("ctrl+t"))
    # تعديل الخطوة عبر الخانات والقائمة (دون لوحة مفاتيح)
    tab.key.setCurrentIndex(tab.key.findData("w"))
    assert tab.current["steps"][0]["keys"] == "ctrl+w"
    assert tab.confirm.isChecked() and not tab.confirm.isEnabled()       # مدمّر ← تأكيد إجباري
    assert not tab.gesture.isEnabled() and tab.warn.text()
    tab._save()
    assert "✓" in tab.status.text()
    m = controller.macros[-1]
    assert m["dangerous"] and m["steps"] == [{"action": "hotkey", "keys": "ctrl+w"}]
    assert tab.list.count() == 1 and tab.list.item(0).text().startswith("⚠")
    # خطأ واضح بدل الحفظ الصامت
    tab.new_macro()
    tab.phrase["fr"].setText("coupe")
    tab._add(keys("ctrl+x"))
    tab._save()
    assert "cut" in tab.status.text() and len(controller.macros) == 1
