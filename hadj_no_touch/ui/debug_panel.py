"""Real-time debug / diagnostics panel.

Shows raw pipeline numbers. Diagnostics can be logged to a local text file;
**no camera frames are ever stored**.
"""

from __future__ import annotations

import csv
import os
import time

from PySide6.QtWidgets import (
    QGroupBox, QGridLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
    QHBoxLayout, QMessageBox,
)

from ..core.status import StatusSnapshot
from ..config import data_dir


class DebugPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("HADJ Debug Panel")
        self.setMinimumSize(560, 460)
        self._recording = False
        self._lines: list[str] = []
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        grid = QGroupBox("Pipeline")
        gl = QGridLayout(grid)
        rows = [
            "FPS", "Tracking FPS", "Latency (ms)", "Camera active", "Hand present",
            "Hand confidence", "Gesture", "Gesture confidence",
            "Fingertip idx (norm)", "Cursor (px)", "Gaze (x,y)", "Gaze match",
            "Voice status", "Last voice", "Profile", "Context", "Active app",
            "Pinch hold", "Locked", "Custom gestures", "Calibration",
            "Hand model", "Face model",
        ]
        self._cells: dict[str, QLabel] = {}
        for i, name in enumerate(rows):
            n = QLabel(name)
            n.setStyleSheet("color: #8fb4dd;")
            v = QLabel("—")
            v.setStyleSheet("color: #ffffff;")
            gl.addWidget(n, i, 0)
            gl.addWidget(v, i, 1)
            self._cells[name] = v
        lay.addWidget(grid)

        loggb = QGroupBox("Diagnostics")
        ll = QVBoxLayout(loggb)
        self.diagnostic_log = QTextEdit()
        self.diagnostic_log.setReadOnly(True)
        self.diagnostic_log.setMaximumHeight(160)
        ll.addWidget(self.diagnostic_log)
        row = QHBoxLayout()
        self.btn_record = QPushButton("Record diagnostics to file")
        self.btn_record.clicked.connect(self._toggle_record)
        self.btn_save = QPushButton("Save log now")
        self.btn_save.clicked.connect(self._save_now)
        row.addWidget(self.btn_record)
        row.addWidget(self.btn_save)
        ll.addLayout(row)
        lay.addWidget(loggb)

    def update_status(self, s: StatusSnapshot) -> None:
        d = s.diag
        values = {
            "FPS": f"{s.fps:.1f}", "Tracking FPS": f"{s.tracking_fps:.1f}",
            "Latency (ms)": f"{s.latency_ms:.0f}",
            "Camera active": str(s.camera_active),
            "Hand present": str(s.hand_present),
            "Hand confidence": f"{s.hand_confidence:.2f}",
            "Gesture": s.gesture,
            "Gesture confidence": f"{s.gesture_confidence:.2f}",
            "Fingertip idx (norm)": f"{d.get('fingerprint', '-')}",
            "Cursor (px)": f"{int(s.cursor_x)},{int(s.cursor_y)}",
            "Gaze (x,y)": f"{round(d.get('gaze_xy', [0, 0])[0], 2)},"  # placeholder updated below
        }
        gx, gy = d.get("gaze_xy", [0.0, 0.0])
        values["Gaze (x,y)"] = f"{gx:.2f},{gy:.2f}"
        values["Gaze match"] = f"{d.get('gaze_match', 0):.2f}"
        values["Voice status"] = d.get("voice_status", s.voice_status)
        values["Last voice"] = s.recognized_text
        values["Profile"] = d.get("profile", s.active_profile)
        values["Context"] = d.get("context", s.active_context)
        values["Active app"] = s.active_app
        values["Pinch hold"] = str(d.get("pinch_hold", False))
        values["Locked"] = str(self.app.engine.locked)
        values["Custom gestures"] = str(d.get("custom_gestures", 0))
        values["Calibration"] = s.calibration
        core = getattr(self.app, "core", None)
        values["Hand model"] = d.get("hand_model") or (
            "ready" if getattr(getattr(core, "hand_tracker", None), "_hands", None) is not None
            else "loading…")
        values["Face model"] = d.get("face_model") or (
            "ready" if getattr(getattr(core, "face_tracker", None), "_mesh", None) is not None
            else "loading…")
        for name, text in values.items():
            self._cells[name].setText(str(text))
        if self._recording:
            row = values.copy()
            row["_t"] = round(time.time(), 3)
            self._lines.append(row)
            if len(self._lines) % 30 == 0:
                self.diagnostic_log.append(f"{row['_t']}: {row['Gesture']}@{row['FPS']}fps")

    # ---- diagnostics logging ----------------------------------------------
    def _toggle_record(self) -> None:
        self._recording = not self._recording
        self.btn_record.setText("Stop diagnostics recording" if self._recording
                                else "Record diagnostics to file")
        self._lines.clear()

    def _save_now(self) -> None:
        folder = data_dir() / "diagnostics"
        folder.mkdir(exist_ok=True)
        path = folder / time.strftime("diag_%Y%m%d_%H%M%S.csv")
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                if self._lines:
                    writer = csv.DictWriter(f, fieldnames=list(self._lines[0].keys()))
                    writer.writeheader()
                    writer.writerows(self._lines)
            QMessageBox.information(self, "Diagnostics",
                                    f"Diagnostics saved (text only): {path}")
        except Exception as e:
            QMessageBox.warning(self, "Diagnostics", str(e))