"""النسختان الكاملة والخفيفة من قاعدة كود واحدة: اكتشاف ما هو مثبّت، والتراجع اللغوي، وطبقة edition.yaml."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from config import loader  # noqa: E402
from core import edition, paths  # noqa: E402
from core.events import SpeechEvent  # noqa: E402


def make_models(root, langs=("en", "fr"), whisper=False):
    for lang in langs:
        (root / "vosk" / lang).mkdir(parents=True)
    if whisper:
        (root / "whisper" / "small").mkdir(parents=True)
        (root / "whisper" / "small" / "model.bin").write_bytes(b"")
    return root


def test_detection(tmp_path):
    lite = make_models(tmp_path / "lite")
    full = make_models(tmp_path / "full", ("ar", "en", "fr"), whisper=True)
    assert edition.available_languages(lite) == ["en", "fr"]
    assert edition.available_languages(full) == ["ar", "en", "fr"]
    assert not edition.whisper_available(lite) and edition.whisper_models(full) == ["small"]
    assert edition.whisper_available(full)        # faster_whisper مثبّت في بيئة التطوير


def test_whisper_needs_the_library_too(tmp_path, monkeypatch):
    models = make_models(tmp_path, whisper=True)
    monkeypatch.setattr(edition.importlib.util, "find_spec", lambda name: None)
    assert not edition.whisper_available(models)


@pytest.mark.parametrize("wanted,available,expected", [
    ("ar", ["en", "fr"], "fr"), ("ar", ["en"], "en"), ("fr", ["en", "fr"], "fr"),
    ("en", ["ar", "en", "fr"], "en"), ("ar", [], "ar")])
def test_fallback_language(wanted, available, expected):
    assert edition.fallback_language(wanted, available) == expected


def test_edition_layer_between_defaults_and_user(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    (tmp_path / "edition.yaml").write_text(
        "edition: lite\nconfig:\n  speech: {language: fr}\n  ui: {ui_language: fr}\n  dictation: {engine: vosk}\n",
        encoding="utf-8")
    user = tmp_path / "user"
    user.mkdir()
    cfg = loader.load_config(user)
    assert (cfg.speech.language, cfg.ui.ui_language, cfg.dictation.engine) == ("fr", "fr", "vosk")
    loader.update_user_config({"ui": {"ui_language": "ar"}}, user)
    assert loader.load_config(user).ui.ui_language == "ar"   # اختيار المستخدم يغلب النسخة
    (tmp_path / "edition.yaml").write_text("config: [broken", encoding="utf-8")
    assert loader.load_config(user).speech.language == "ar"   # ملف تالف ← القيم العامة


# ---------------- المتحكم في النسخة الخفيفة ----------------
@pytest.fixture
def lite(tmp_path, monkeypatch):
    from conftest import FakeOS
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    monkeypatch.setattr(edition, "available_languages", lambda models_dir=None: ["en", "fr"])
    monkeypatch.setattr(edition, "whisper_available", lambda models_dir=None: False)
    loader.update_user_config({"speech": {"language": "ar"}}, tmp_path)   # مستخدم سابق للنسخة الكاملة
    notes = []
    c = Controller(FakeOS(), lambda k, **d: notes.append((k, d)), loader.load_config(tmp_path))
    c.notes, c.sent = notes, []
    monkeypatch.setattr(c.audio, "send", lambda kind, **p: c.sent.append((kind, p)))
    monkeypatch.setattr(c.audio, "start", lambda: None)
    monkeypatch.setattr(c.vision, "start", lambda: None)
    yield c
    c.shutdown()


def test_missing_arabic_falls_back_without_losing_the_choice(lite, tmp_path):
    c = lite
    assert c.config.speech.language == "fr" and c.lang_fallback == "ar"
    assert c.audio_config()["language"] == "fr"
    assert c.gate.wake_words == ["ordinateur"]
    c.start()
    assert ("lang_fallback", {"wanted": "ar", "used": "fr"}) in c.notes
    # الإعداد المحفوظ يبقى "ar": يعود تلقائياً عند تثبيت حزمة العربية
    assert loader.read_yaml(tmp_path / "config.yaml")["speech"]["language"] == "ar"


def test_switching_to_missing_language_explains(lite):
    c = lite
    assert c.set_language("ar") is False and c.config.speech.language == "fr"
    c.gate.continuous = True
    c.dispatcher.handle(SpeechEvent(text="arabe", lang="fr"))
    keys = [d.get("key") for k, d in c.notes if k == "result"]
    assert keys[-1] == "lang_pack_missing"
    c.toggle_language()
    c.toggle_language()
    assert [p["language"] for k, p in c.sent if k == "reload"] == ["en", "fr"]   # لا تمر بالعربية


def test_lite_dictation_uses_vosk(lite):
    c = lite
    c.config.dictation.engine = "whisper"
    c.start_dictation()
    assert [p["engine"] for k, p in c.sent if k == "dictation"] == ["vosk"]
    assert c.dictation_state == "ready"


def test_settings_show_only_installed_options(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ui.i18n import Tr
    from ui.settings_window import SettingsWindow
    QApplication.instance() or QApplication([])
    models = make_models(tmp_path / "models")
    w = SettingsWindow(Tr("fr"), loader.load_config(tmp_path / "u"), models, [], on_save=lambda c: None)
    assert [w.cmd_lang.itemData(i) for i in range(w.cmd_lang.count())] == ["en", "fr"]
    assert [w.engine.itemData(i) for i in range(w.engine.count())] == ["vosk"]
    assert w.collect()["dictation"]["engine"] == "vosk"


def test_build_script_editions():
    """النسخ الثلاث معرّفة، والخفيفة تستبعد Whisper ومكتباته والعربية لا غير."""
    from conftest import ROOT
    text = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8-sig")
    assert '[ValidateSet("full", "lite", "pack-ar")]' in text
    for lib in ("faster_whisper*", "ctranslate2*", "onnxruntime*", '"av"'):
        assert lib in text
    lite_models = text[text.index('foreach ($m in "vosk\\en"'):].split("\n")[0]
    assert "ar" not in lite_models.replace("for", "") and "whisper" not in lite_models
