"""App-level integration tests for the roadmap axis-1/2 wiring.

Covers the parts that only exist end-to-end in AppCore: status emission of the
voice/click fields, the live-metrics reset, the sensitivity dial, and the
honest voice-engine switch (a local choice never silently becomes Google).
"""

from __future__ import annotations

import pytest


def _core():
    from PySide6.QtCore import QCoreApplication
    _ = QCoreApplication.instance() or QCoreApplication([])
    from hadj_no_touch.core.app import AppCore
    return AppCore()


def _no_save(monkeypatch, core) -> None:
    """Keep AppCore methods from writing the real per-user config.json."""
    monkeypatch.setattr(core.settings, "save",
                        lambda *a, **k: None)


class TestStatusFields:
    def test_click_metrics_reach_status(self) -> None:
        core = _core()
        core.perf.note_click(0.05)
        core._emit_status(snapshot_time=0.0)
        assert core._status.click_count == 1
        assert core._status.click_precision == pytest.approx(1.0)

    def test_reset_live_metrics_clears_status(self) -> None:
        core = _core()
        core.perf.note_click(0.30)
        core.perf.note_false_trigger()
        core._emit_status(snapshot_time=0.0)
        assert core._status.click_count == 1
        core.reset_live_metrics()
        core._emit_status(snapshot_time=0.0)
        assert core._status.click_count == 0
        assert core._status.click_precision is None

    def test_voice_fields_never_fabricate_an_engine(self) -> None:
        """With no engine running, status shows no engine — not 'google'."""
        core = _core()
        core.voice.engine = None
        core._emit_status(snapshot_time=0.0)
        assert core._status.voice_engine == ""
        assert core._status.voice_status == "idle"
        assert core._status.audio_online is False


class TestSensitivityAppLevel:
    def test_unknown_level_warns_and_is_ignored(self, monkeypatch) -> None:
        core = _core()
        _no_save(monkeypatch, core)
        warns: list = []
        core.event_logged.connect(lambda kind, msg: warns.append(msg)
                                  if kind == "WARN" else None)
        core.settings.sensitivity = "medium"
        core.set_sensitivity("bogus")
        assert any("sensitivity" in w.lower() for w in warns)
        assert core.settings.sensitivity == "medium"

    def test_high_level_applies_real_knobs(self, monkeypatch) -> None:
        core = _core()
        _no_save(monkeypatch, core)
        core.set_sensitivity("high")
        assert core.settings.cursor.speed > 1.0
        assert core.settings.cursor.smoothing < core.settings.SENSITIVITY_SETS["medium"]["smoothing"]
        assert core.settings.gestures.pinch_dwell_click_ms < 220


class TestVoiceEngineSwitch:
    def test_local_choice_disables_voice_honestly(self, monkeypatch) -> None:
        """voogle engine must never be built when the user picked a local one."""
        core = _core()
        _no_save(monkeypatch, core)
        import hadj_no_touch.voice.speech_recognition as sr
        built = {"google": False, "vosk": 0}

        class BoomGoogle:
            def __init__(self, *a, **k):
                built["google"] = True

            def available(self):
                return True

        original_make = sr.VoskSpeechEngine

        def fake_vosk(on_text=None, language="en-US", model_path=""):
            built["vosk"] += 1
            inst = original_make(on_text, language, model_path)
            return inst

        monkeypatch.setattr(sr, "GoogleSpeechEngine", BoomGoogle)
        monkeypatch.setattr(core.voice, "_make_engine", fake_vosk)

        ok = core.set_voice_engine("vosk")
        assert ok is False, "vosk unavailable without a model: voice must be off"
        assert core.voice.engine is None
        assert core.settings.voice.engine == "vosk"
        assert core.settings.voice.engine_choice_made is True
        assert built["google"] is False, "google must never be silently started"

    def test_unknown_engine_warns(self, monkeypatch) -> None:
        core = _core()
        _no_save(monkeypatch, core)
        warns: list = []
        core.event_logged.connect(lambda kind, msg: warns.append(msg)
                                  if kind == "WARN" else None)
        assert core.set_voice_engine("yahoo") is False
        assert any("voice engine" in w.lower() for w in warns)

    def test_google_choice_is_recorded(self, monkeypatch) -> None:
        core = _core()
        _no_save(monkeypatch, core)
        import hadj_no_touch.voice.speech_recognition as sr

        class FakeGoogle:
            def __init__(self, *a, **k):
                self.name = "google"
                self.offline = False
                self.status = "idle"

            def available(self):
                return True

            def start(self):
                self.status = "listening"
                return True

        monkeypatch.setattr(core.voice, "_make_engine",
                            lambda name: FakeGoogle())
        ok = core.set_voice_engine("google")
        assert ok is True
        assert core.settings.voice.engine == "google"
        assert core.settings.voice.engine_choice_made is True
