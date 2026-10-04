"""الملفات الشخصية: المدمجة صالحة، قواعد الأمان لا تُتجاوز، الاستيراد/التصدير، والتبديل الفوري."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
import yaml  # noqa: E402

from commands.parser import CommandParser, normalize  # noqa: E402
from config import profiles as prof  # noqa: E402
from config.loader import load_command_specs  # noqa: E402
from core.events import GestureEvent  # noqa: E402


@pytest.fixture(scope="module")
def base():
    return load_command_specs()


@pytest.fixture(scope="module")
def builtins(base):
    return prof.load_profiles(base, user_dir=None)


# ---------------- الملفات المدمجة ----------------
def test_builtin_profiles_load_cleanly(base):
    names = sorted(p.name for p in prof.builtin_dir().glob("*.yaml"))
    assert names == ["browsing.yaml", "kitchen.yaml", "presentation.yaml", "streaming.yaml"]
    for path in prof.builtin_dir().glob("*.yaml"):
        p, warnings = prof.parse_profile(yaml.safe_load(path.read_text(encoding="utf-8")), base, True)
        assert warnings == [], (path.name, warnings)
        assert set(p.name) == set(p.description) == {"ar", "fr", "en"}
        for c in p.commands:
            assert all(c["phrases"].get(lang) for lang in ("ar", "fr", "en")), c["id"]


def test_builtin_profile_phrases_do_not_shadow_base_commands(base, builtins):
    base_phrases = {(lang, normalize(ph)) for s in base for lang, v in s.get("phrases", {}).items() for ph in v}
    switch = [s for s in prof.switch_specs(builtins)]
    for p in builtins.values():
        for c in p.commands + switch:
            for lang, v in c["phrases"].items():
                for ph in v:
                    assert (lang, normalize(ph)) not in base_phrases, (p.id, c["id"], ph)


def test_presentation_gestures_point_to_its_commands(builtins):
    b = builtins["presentation"].bindings
    assert b["swipe_right"] == "cmd:presentation.next_slide"
    assert b["palm_hold_long"] == "cmd:presentation.black_screen"


def test_streaming_go_live_needs_confirmation(builtins):
    cmds = {c["id"]: c for c in builtins["streaming"].commands}
    assert cmds["streaming.start_stream"].get("dangerous")
    assert cmds["streaming.stop_stream"].get("dangerous")
    assert not cmds["streaming.scene_1"].get("dangerous")


# ---------------- قواعد الأمان ----------------
def evil_profile():
    return {
        "id": "evil", "name": {"fr": "Piège"},
        "bindings": {"fist_hold": "none", "pinch_tap": "cmd:shutdown", "swipe_left": "cmd:wipe",
                     "swipe_right": "rm_rf", "two_scroll": "cmd:ok", "unknown_gesture": "click"},
        "commands": [
            {"id": "emergency_stop", "always": True, "phrases": {"fr": ["bonjour"]}, "action": "key",
             "args": {"key": "a"}},
            {"id": "wipe", "dangerous": True, "phrases": {"fr": ["efface"]}, "action": "key", "args": {"key": "delete"}},
            {"id": "ok", "phrases": {"fr": ["d'accord"]}, "action": "key", "args": {"key": "enter"}},
            {"id": "bad", "phrases": {"fr": ["x"]}, "action": "os.system", "args": {"cmd": "format c:"}},
        ],
    }


def test_imported_profile_cannot_weaken_safety(base):
    p, warnings = prof.parse_profile(evil_profile(), base)
    assert "fist_hold" not in p.bindings                      # القبضة لا تُمس
    assert "pinch_tap" not in p.bindings                      # إيماءة ← أمر خطِر أساسي (shutdown)
    assert "swipe_left" not in p.bindings                     # إيماءة ← أمر خطِر خاص بالملف
    assert "swipe_right" not in p.bindings                    # إجراء غير معروف
    assert p.bindings == {"two_scroll": "cmd:evil.ok"}
    ids = [c["id"] for c in p.commands]
    assert ids == ["evil.emergency_stop", "evil.wipe", "evil.ok"]   # لا يستبدل أمراً أساسياً، والمجهول مرفوض
    assert not any(c.get("always") for c in p.commands)
    assert len(warnings) >= 6
    assert prof.effective_bindings({"fist_hold": "none"}, p)["fist_hold"] == "app.pause"


def test_profile_needs_a_name(base):
    with pytest.raises(prof.ProfileError):
        prof.parse_profile({"id": "x"}, base)
    with pytest.raises(prof.ProfileError):
        prof.parse_profile(["not", "a", "dict"], base)


def test_missing_languages_fall_back_to_given_name(base):
    p, _ = prof.parse_profile({"name": "Atelier"}, base)
    assert p.id == "atelier" and p.name == {"ar": "Atelier", "fr": "Atelier", "en": "Atelier"}


# ---------------- الاستيراد والتصدير ----------------
def test_export_import_roundtrip(tmp_path, base, builtins):
    out = prof.export_profile(builtins["presentation"], tmp_path / "p.hadjprofile")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["bindings"]["swipe_right"] == "cmd:next_slide"        # دون البادئة: قابل للنقل
    user = tmp_path / "user"
    p, warnings = prof.import_profile(out, base, builtins, user_dir=user)
    assert warnings == [] and p.id == "presentation-2"               # لا يطغى على المدمج
    assert p.bindings["swipe_right"] == "cmd:presentation-2.next_slide"
    loaded = prof.load_profiles(base, user_dir=user)
    assert loaded["presentation-2"].commands == p.commands and not loaded["presentation-2"].builtin


def test_import_rejects_bad_files(tmp_path, base, builtins):
    big = tmp_path / "big.hadjprofile"
    big.write_text("name: x\n#" + "a" * (prof.MAX_IMPORT_BYTES + 10), encoding="utf-8")
    with pytest.raises(prof.ProfileError) as e:
        prof.import_profile(big, base, builtins, user_dir=tmp_path)
    assert e.value.key == "profile_too_big"
    junk = tmp_path / "junk.hadjprofile"
    junk.write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(prof.ProfileError):
        prof.import_profile(junk, base, builtins, user_dir=tmp_path)
    assert not (tmp_path / "profiles").exists()                      # لا أثر عند الفشل


def test_builtin_profiles_are_read_only(builtins):
    with pytest.raises(prof.ProfileError):
        prof.save_profile(builtins["kitchen"])
    with pytest.raises(prof.ProfileError):
        prof.delete_profile(builtins["kitchen"])


def test_no_user_folder_until_first_save(tmp_path, base):
    prof.load_profiles(base, user_dir=tmp_path)
    assert not (tmp_path / "profiles").exists()


# ---------------- التبديل الصوتي ----------------
@pytest.mark.parametrize("lang,phrase,pid", [
    ("fr", "profil cuisine", "kitchen"), ("fr", "mode présentation", "presentation"),
    ("en", "profile streaming", "streaming"), ("ar", "وضع المطبخ", "kitchen"),
    ("fr", "profil standard", "standard"), ("en", "profile normal", "standard"),
    ("ar", "وضع عادي", "standard"),
])
def test_switch_phrases(base, builtins, lang, phrase, pid):
    parser = CommandParser([*base, *prof.switch_specs(builtins)])
    m = parser.parse(phrase, lang)
    assert m is not None and m.spec.id == f"profile.{pid}"


# ---------------- الإيماءة ← أمر ----------------
def test_gesture_runs_profile_command(env, builtins):
    parser = CommandParser([*env.disp.parser.specs, *builtins["presentation"].commands])
    env.disp.parser = parser
    env.disp.handle(GestureEvent("swipe_right", {"action": "cmd:presentation.next_slide"}))
    assert ("key", "right", 1) in env.os.calls or any("right" in str(c) for c in env.os.calls)


def test_gesture_never_runs_dangerous_command(env, builtins):
    env.disp.parser = CommandParser([*env.disp.parser.specs, *builtins["streaming"].commands])
    before = list(env.os.calls)
    env.disp.handle(GestureEvent("pinch_tap", {"action": "cmd:streaming.start_stream"}))
    env.disp.handle(GestureEvent("pinch_tap", {"action": "cmd:does.not.exist"}))
    assert env.os.calls == before
    keys = [d["key"] for k, d in env.notes if k == "result"]
    assert keys == ["gesture_needs_voice", "unknown_action"]


def test_gesture_command_ignored_while_paused(env, builtins):
    env.disp.parser = CommandParser([*env.disp.parser.specs, *builtins["presentation"].commands])
    env.app.paused.set()
    before = list(env.os.calls)
    env.disp.handle(GestureEvent("swipe_right", {"action": "cmd:presentation.next_slide"}))
    assert env.os.calls == before


# ---------------- المتحكم ----------------
@pytest.fixture
def controller(tmp_path, monkeypatch):
    from conftest import FakeOS
    from config import loader
    from core import paths
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    notes = []
    c = Controller(FakeOS(), lambda k, **d: notes.append((k, d)), loader.load_config(tmp_path))
    sent = []
    monkeypatch.setattr(c.audio, "send", lambda kind, **p: sent.append(("audio", kind, p)))
    monkeypatch.setattr(c.vision, "send", lambda kind, **p: sent.append(("vision", kind, p)))
    c.notes, c.sent = notes, sent
    yield c
    c.shutdown()


def test_switching_profile_is_instant_and_persistent(controller, tmp_path):
    from config import loader
    c = controller
    assert c.profile.id == "standard" and c.parser.parse("diapositive suivante", "fr") is None
    assert c.set_profile("presentation")
    assert c.parser.parse("diapositive suivante", "fr").spec.id == "presentation.next_slide"
    assert c.dispatcher.parser is c.parser
    kinds = [(w, k) for w, k, _ in c.sent]
    assert ("audio", "set_grammar") in kinds and ("vision", "bindings") in kinds   # لا إعادة تشغيل
    bindings = next(p for w, k, p in c.sent if k == "bindings")["bindings"]
    assert bindings["swipe_right"] == "cmd:presentation.next_slide" and bindings["fist_hold"] == "app.pause"
    assert ("profile", {"id": "presentation", "name": c.profile.label(c.config.ui.ui_language)}) in c.notes
    assert loader.read_yaml(tmp_path / "config.yaml")["profiles"]["active"] == "presentation"
    assert c.vision_config()["bindings"]["swipe_right"] == "cmd:presentation.next_slide"
    assert not c.set_profile("nope")


def test_active_profile_restored_and_bad_one_falls_back(tmp_path, monkeypatch):
    from conftest import FakeOS
    from config import loader
    from core import paths
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    loader.update_user_config({"profiles": {"active": "kitchen"}}, tmp_path)
    c = Controller(FakeOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    assert c.profile.id == "kitchen"
    c.shutdown()
    loader.update_user_config({"profiles": {"active": "deleted-profile"}}, tmp_path)
    c = Controller(FakeOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    assert c.profile.id == "standard"
    c.shutdown()


def test_duplicate_edit_delete_cycle(controller):
    c = controller
    p = c.duplicate_profile("kitchen", "Ma cuisine")
    assert p.id == "ma-cuisine" and not p.builtin and p.commands
    warnings = c.save_profile_bindings(p.id, {"swipe_right": "cmd:ma-cuisine.next", "fist_hold": "none",
                                              "pinch_tap": ""})
    assert warnings == ["fist_hold: protected"]
    assert c.profiles["ma-cuisine"].bindings == {"swipe_right": "cmd:ma-cuisine.next"}
    c.set_profile("ma-cuisine")
    c.delete_profile("ma-cuisine")
    assert "ma-cuisine" not in c.profiles and c.profile.id == "standard"
    assert ("profiles_changed", {}) in c.notes


# ---------------- واجهة التبويب ----------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_profiles_tab(qapp, controller):
    from ui.i18n import Tr
    from ui.profiles_tab import ProfilesTab
    from ui.settings_window import GESTURE_ACTIONS, _combo
    from ui.theme import theme
    tab = ProfilesTab(Tr("fr"), theme(1.0, False), controller, GESTURE_ACTIONS, _combo)
    assert tab.list.count() == len(controller.profiles)
    # ملف مدمج: لا محرّر ولا حذف
    tab.refresh("presentation")
    assert not tab.combos and not tab.btn_delete.isEnabled()
    tab._activate()
    assert controller.profile.id == "presentation" and "Présentation" in tab.status.text()
    # ملف مستخدم: محرّر بلا صف للقبضة
    p = controller.duplicate_profile("presentation", "Cours")
    tab.refresh(p.id)
    assert tab.combos and "fist_hold" not in tab.combos and tab.btn_delete.isEnabled()
    assert tab.collect_bindings()["swipe_right"] == "cmd:cours.next_slide"
