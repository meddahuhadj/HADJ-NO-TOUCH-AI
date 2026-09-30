"""نافذة الإعدادات (Qt دون شاشة) وتطبيق الإعدادات في المتحكم."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from config import loader  # noqa: E402
from config.schema import AppConfig  # noqa: E402
from core import paths  # noqa: E402
from ui.i18n import Tr  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    from ui.settings_window import SettingsWindow
    (tmp_path / "whisper" / "small").mkdir(parents=True)
    (tmp_path / "whisper" / "small" / "model.bin").write_bytes(b"")
    (tmp_path / "whisper" / "base").mkdir()
    (tmp_path / "whisper" / "base" / "model.bin").write_bytes(b"")
    saved = []
    w = SettingsWindow(Tr("ar"), loader.load_config(tmp_path / "nouser"), tmp_path,
                       ["Mic A", "Mic B"], on_save=saved.append)
    w.saved = saved
    return w


def merged(changes):
    base = loader.read_yaml(loader.default_config_path())
    return AppConfig.model_validate(loader.deep_merge(base, changes))


def test_unchanged_window_produces_valid_config_equal_to_defaults(window):
    cfg = merged(window.collect())
    default = loader.load_config(paths.user_dir() / "__none__")
    assert cfg.speech == default.speech
    assert cfg.vision == default.vision
    assert cfg.safety == default.safety


def test_edits_are_collected_and_valid(window):
    w = window
    w.cmd_lang.setCurrentIndex(w.cmd_lang.findData("en"))
    w.wake_ar.setText("يا مساعد، حاسوب")
    w.continuous.setChecked(True)
    w.mic.setCurrentIndex(w.mic.findData(1))
    w.engine.setCurrentIndex(w.engine.findData("vosk"))
    w.whisper_model.setCurrentIndex(w.whisper_model.findData("base"))
    w.bindings["pinch_tap"].setCurrentIndex(w.bindings["pinch_tap"].findData("double_click"))
    w.bindings["fist_hold"].setCurrentIndex(w.bindings["fist_hold"].findData("none"))
    w.font_scale.setValue(1.5)
    w.hotkey.setText("ctrl+alt+s")
    cfg = merged(w.collect())
    assert cfg.speech.language == "en"
    assert cfg.speech.wake_words["ar"] == ["يا مساعد", "حاسوب"]
    assert cfg.speech.continuous_listening and cfg.speech.input_device == 1
    assert cfg.dictation.engine == "vosk" and cfg.dictation.whisper_model == "base"
    assert cfg.vision.bindings["pinch_tap"] == "double_click"
    assert cfg.vision.bindings["fist_hold"] == "none"
    assert cfg.ui.font_scale == 1.5 and cfg.safety.emergency_hotkey == "ctrl+alt+s"


def test_invalid_zone_and_pinch_are_repaired(window):
    w = window
    for s, v in zip(w.zone, (0.5, 0.5, 0.52, 0.9)):    # عرض 0.02 فقط
        s.setValue(v)
    w.pinch_enter.setValue(0.4)
    w.pinch_exit.setValue(0.3)                          # أقل من البدء
    ch = w.collect()["vision"]
    assert ch["control_zone"] == list(w.cfg.vision.control_zone)
    assert ch["tuning"]["pinch_exit"] > ch["tuning"]["pinch_enter"]
    merged(w.collect())


def test_empty_wake_word_keeps_previous(window):
    window.wake_en.setText("  ")
    assert window.collect()["speech"]["wake_words"]["en"] == ["computer"]


def test_save_button_calls_callback(window):
    window._save()
    assert len(window.saved) == 1 and "vision" in window.saved[0]


def test_whisper_models_listed_from_disk(window):
    items = [window.whisper_model.itemData(i) for i in range(window.whisper_model.count())]
    assert items == ["base", "small"]


def test_controller_apply_settings(tmp_path, monkeypatch):
    from conftest import FakeOS
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    c = Controller(FakeOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    restarted = []
    monkeypatch.setattr(c, "_restart_worker", lambda w: restarted.append(w.name))
    try:
        cfg_ref = c.ctx.config
        restart_ui = c.apply_settings({"speech": {"continuous_listening": True, "match_threshold": 90,
                                                  "wake_words": {"ar": ["مساعد"]}}})
        assert not restart_ui
        assert c.gate.continuous and c.parser.threshold == 90 and c.gate.wake_words == ["مساعد"]
        assert c.ctx.config is cfg_ref and cfg_ref.speech.match_threshold == 90   # نفس الكائن
        assert restarted == ["audio"]
        restarted.clear()
        assert c.apply_settings({"ui": {"font_scale": 2.0}}) is True
        assert restarted == []
        c.apply_settings({"vision": {"bindings": {"pinch_tap": "double_click"}}})
        assert restarted == ["vision"]
        saved = loader.read_yaml(tmp_path / "config.yaml")
        assert saved["speech"]["match_threshold"] == 90 and saved["ui"]["font_scale"] == 2.0
        assert saved["vision"]["bindings"] == {"pinch_tap": "double_click"}   # الباقي افتراضي
    finally:
        c.shutdown()
