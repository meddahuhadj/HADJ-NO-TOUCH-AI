"""Tests for config persistence (Settings.save / load)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hadj_no_touch.config import Settings, CameraSettings


class TestSettingsSaveLoad:
    """ROUND-TRIP SAVE/LOAD WITHOUT CRASHING ON THE INTERNAL RLock."""

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        s = Settings()
        s.cursor.speed = 0.42
        s.camera.index = 2
        s.active_profile = "medical"
        s.save(cfg)

        s2 = Settings()
        s2.load(cfg)
        assert s2.cursor.speed == 0.42
        assert s2.camera.index == 2
        assert s2.active_profile == "medical"

    def test_missing_file_loads_defaults(self, tmp_path: Path) -> None:
        s = Settings()
        s.load(tmp_path / "nope.json")
        assert s.active_profile == "personal"
        assert s.cursor.speed == 1.0

    def test_corrupt_file_loads_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "bad.json"
        cfg.write_text("{bad json!!!", encoding="utf-8")
        s = Settings()
        s.load(cfg)
        assert s.active_profile == "personal"

    def test_to_dict_excludes_lock(self) -> None:
        d = Settings().to_dict()
        assert "_lock" not in d
        assert "camera" in d
        assert isinstance(d["camera"], dict)

    def test_camera_sub_settings_round_trip(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg.json"
        s = Settings()
        s.camera = CameraSettings(index=5, width=320, height=240)
        s.save(cfg)
        s2 = Settings()
        s2.load(cfg)
        assert s2.camera.index == 5
        assert s2.camera.width == 320
