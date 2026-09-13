"""Tests for the local SQLite persistence layer."""

from __future__ import annotations

import pickle
from pathlib import Path

from hadj_no_touch.database.database import Database


class TestKVStore:
    def test_round_trip(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.set_kv("calibration_done", True)
        db.set_kv("window_geometry", {"x": 10})
        assert db.get_kv("calibration_done") is True
        assert db.get_kv("window_geometry") == {"x": 10}
        assert db.get_kv("missing", "dflt") == "dflt"
        db.close()


class TestCalibration:
    def test_save_and_latest(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        db.save_calibration([(0.1, 0.1)], [[1, 0], [0, 1]], label="main")
        latest = db.latest_calibration()
        assert latest is not None
        assert list(latest["points"][0]) == [0.1, 0.1]
        db.close()

    def test_clear(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        db.save_calibration([], [], label="x")
        db.clear_calibrations()
        assert db.latest_calibration() is None
        db.close()


class TestCustomGestures:
    def test_save_load_delete(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        blob = pickle.dumps((b"template-1",))
        db.save_custom_gesture("wave", "screenshot", "Take screenshot", [blob])
        rows = db.load_custom_gestures()
        assert len(rows) == 1
        assert rows[0]["name"] == "wave"
        assert rows[0]["action"] == "screenshot"
        assert pickle.loads(rows[0]["templates"][0]) == (b"template-1",)
        db.delete_custom_gesture("wave")
        assert db.load_custom_gestures() == []
        db.close()


class TestActivityLog:
    def test_log_and_recent(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        db.log_activity("INFO", "app started")
        db.log_activity("ERROR", "boom")
        rows = db.recent_activity(5)
        assert len(rows) == 2
        assert rows[0][2] == "boom"  # most recent first
        db.clear_activity()
        assert db.recent_activity() == []
        db.close()


class TestPrivacyWipe:
    def test_clear_all_user_data(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        db.set_kv("k", "v")
        db.save_calibration([], [], "x")
        db.save_custom_gesture("g", "a", "b", [b"\x01"])
        db.log_activity("INFO", "msg")
        db.clear_all_user_data()
        assert db.get_kv("k") is None
        assert db.latest_calibration() is None
        assert db.load_custom_gestures() == []
        assert db.recent_activity() == []
        db.close()


class TestProfilePersistence:
    def test_save_profile_requires_real_profile(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "t.db")
        # uses a stub profile object exposing the dataclass fields
        class StubProfile:
            id = "stub"
            name = "stub"
            description = ""
            gesture_map = {}
            voice_map = {}
            sensitivity = {}
            auto_apps = []
            cursor_behavior = {}
        db.save_profile(StubProfile())
        db.close()  # no exception raised
        assert Path(tmp_path / "t.db").exists()