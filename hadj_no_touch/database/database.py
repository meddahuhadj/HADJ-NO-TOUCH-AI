"""Local SQLite database: settings, calibration, custom gestures, activity log.

All data stays on this machine.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from ..config import data_dir
from ..logging_setup import get_logger

log = get_logger("database")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL, level TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    points TEXT, homography TEXT, created REAL, label TEXT
);
CREATE TABLE IF NOT EXISTS custom_gestures (
    name TEXT PRIMARY KEY,
    action TEXT, action_label TEXT, templates TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT, json TEXT, updated REAL
);
"""


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "hadj_no_touch.db")
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # ---- key/value -----------------------------------------------------------
    def set_kv(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO kv_store(key, value) VALUES (?,?)",
                (key, json.dumps(value)),
            )
            self._conn.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return row[0]

    # ---- calibration -----------------------------------------------------------
    def save_calibration(self, points: list, homography: list | None, label: str = "main") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO calibration(points, homography, created, label) VALUES (?,?,?,?)",
                (json.dumps(points), json.dumps(homography) if homography else None,
                 time.time(), label),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def latest_calibration(self) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT points, homography, created FROM calibration ORDER BY created DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return {
            "points": json.loads(row[0]),
            "homography": json.loads(row[1]) if row[1] else None,
            "created": row[2],
        }

    def clear_calibrations(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM calibration")
            self._conn.commit()

    # ---- custom gestures --------------------------------------------------------
    def save_custom_gesture(self, name: str, action: str, action_label: str,
                            templates: list[bytes]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO custom_gestures(name, action, action_label, templates)"
                " VALUES (?,?,?,?)",
                (name, action, action_label, json.dumps([t.hex() for t in templates])),
            )
            self._conn.commit()

    def load_custom_gestures(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, action, action_label, templates FROM custom_gestures"
            ).fetchall()
        out = []
        for name, action, label, templates_raw in rows:
            try:
                templates = [bytes.fromhex(t) for t in json.loads(templates_raw)]
            except Exception:
                templates = []
            out.append({"name": name, "action": action, "action_label": label,
                        "templates": templates})
        return out

    def delete_custom_gesture(self, name: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM custom_gestures WHERE name=?", (name,))
            self._conn.commit()

    # ---- profiles ---------------------------------------------------------------
    def save_profile(self, profile) -> None:
        data = {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "gesture_map": profile.gesture_map,
            "voice_map": profile.voice_map,
            "sensitivity": profile.sensitivity,
            "auto_apps": profile.auto_apps,
            "cursor_behavior": profile.cursor_behavior,
        }
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO profiles(id, name, json, updated) VALUES (?,?,?,?)",
                (profile.id, profile.name, json.dumps(data), time.time()),
            )
            self._conn.commit()

    # ---- activity log -----------------------------------------------------------
    def log_activity(self, level: str, message: str) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO activity_log(ts, level, message) VALUES (?,?,?)",
                    (time.time(), level, message[:500]),
                )
                self._conn.commit()
        except Exception:
            pass

    def recent_activity(self, limit: int = 50) -> list[tuple]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, level, message FROM activity_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(ts, level, message) for ts, level, message in rows]

    def clear_activity(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM activity_log")
            self._conn.commit()

    def clear_all_user_data(self) -> None:
        """Privacy: wipe all locally stored application data."""
        with self._lock:
            for table in ("activity_log", "calibration", "custom_gestures", "kv_store"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()
        log.info("All user data cleared")