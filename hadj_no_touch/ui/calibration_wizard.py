"""Calibration wizard dialog.

Walks the user through pointing at the four on-screen corners (top-left,
top-right, bottom-right, bottom-left) plus a center verification, first to
enter fingertips or a greedy mapping. The mapping is computed with a
homography and stored locally.

Disclosing what is delivered here: a standard webcam yields an *estimated*
spatial mapping, not physical touch detection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
)

from ..core.app import AppCore
from ..interaction.calibration import SCREEN_ANCHORS, CalibrationManager
from ..logging_setup import get_logger

log = get_logger("ui.calibration")

STAGE_TEXTS = [
    "Aim your index fingertip at the TOP-LEFT corner, hold still and pinch "
    "(or press \u201cConfirm point\u201d).",
    "Now the TOP-RIGHT corner \u2014 point and pinch.",
    "Bottom-RIGHT corner \u2014 point and pinch.",
    "Bottom-LEFT corner \u2014 point and pinch.",
    "Center verification \u2014 point at the middle of the screen and pinch.",
]

ANCHOR_NAMES = ["Top-left", "Top-right", "Bottom-right", "Bottom-left", "Center"]


class CalibrationWizard(QDialog):
    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("HADJ \u2014 Calibration Wizard")
        self.setMinimumSize(560, 440)
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 Hz
        self._timer.timeout.connect(self._tick)

        lay = QVBoxLayout(self)

        title = QLabel("\U0001f3af Virtual Interaction Plane \u2014 Calibration")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #7cc3ff;")
        lay.addWidget(title)

        note = QLabel(
            "A standard webcam provides an estimated spatial mapping \u2014 this creates a "
            "virtual/contactless interaction plane, not a physical touchscreen."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9fc7e8; font-size: 11px;")
        lay.addWidget(note)

        self.preview = QLabel("Starting camera preview\u2026")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(480, 300)
        self.preview.setStyleSheet(
            "background: #080f19; border: 1px solid #223d5c; border-radius: 10px;"
            "color: #5f7ea0;")
        lay.addWidget(self.preview, 1)

        prog = QHBoxLayout()
        self.stage_labels: list[QLabel] = []
        for i, name in enumerate(ANCHOR_NAMES):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #5f7ea0; font-size: 11px; border: 1px solid #223d5c;"
                              "border-radius: 6px; padding: 4px 2px;")
            prog.addWidget(lbl, 1)
            self.stage_labels.append(lbl)
        lay.addLayout(prog)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #ffe08a; font-size: 13px; min-height: 34px;")
        lay.addWidget(self.hint)

        btns = QHBoxLayout()
        self.btn_confirm = QPushButton("✔ Confirm point")
        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_skip = QPushButton("Skip (estimate)")
        self.btn_skip.clicked.connect(self._skip)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._cancel)
        btns.addWidget(self.btn_confirm)
        btns.addWidget(self.btn_skip)
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)
        lay.addLayout(btns)

        self.core.start_calibration()

    # ---- lifecycle -------------------------------------------------------
    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._timer.start()

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def closeEvent(self, e) -> None:
        self._cancel_quiet()
        super().closeEvent(e)

    def _cancel_quiet(self) -> None:
        if self.core.calibration_active or not self.core.calibration.done:
            self.core.cancel_calibration()

    # ---- polling ---------------------------------------------------------
    def _tick(self) -> None:
        core = self.core
        stage = core.calibration_tick()
        self._draw_preview(stage)
        self._update_ui(stage)
        if core.calibration.done:
            self._timer.stop()
            QMessageBox.information(
                self, "Calibration",
                "Calibration complete and saved locally.\n"
                "Move your fingertip \u2014 the cursor should follow. "
                "Recalibrate any time from the dashboard.")
            self.accept()

    def _draw_preview(self, stage: int) -> None:
        f = self.core.camera.read()
        if f is None or f.bgr is None:
            self.preview.setText("No camera frame available")
            return
        try:
            import cv2
            view = f.bgr.copy()
            cal: CalibrationManager = self.core.calibration
            # fingertip marker (index tip) from the latest detection
            hand = getattr(self.core, "_last_hand", None)
            if hand is None:
                hands = self.core.hand_tracker.detect(view, view.shape[1], view.shape[0])
                if hands:
                    hand = self.core._choose_hand(hands)
                    self.core._last_hand = hand
            if hand is not None:
                x, y = (int(hand.landmarks_px[8][0]), int(hand.landmarks_px[8][1]))
                cv2.circle(view, (x, y), 9, (0, 230, 120), 2)
                cv2.circle(view, (x, y), 3, (0, 230, 120), -1)
            # target anchor drawn via inverse mapping when available
            if cal.homography is not None and stage < 5:
                try:
                    src = cal.homography.copy()
                    inv_h = cv2.invert(src)[1]
                    anchors_norm = SCREEN_ANCHORS if stage < 4 else [(0.5, 0.5)]
                    for a in anchors_norm[:1]:
                        pts = cv2.perspectiveTransform(
                            __import__("numpy").float32([a]).reshape(-1, 1, 2), inv_h)
                        cx = int(pts[0][0][0] * view.shape[1])
                        cy = int(pts[0][0][1] * view.shape[0])
                        cv2.drawMarker(view, (cx, cy), (255, 180, 60),
                                       markerType=cv2.MARKER_SQUARE, markerSize=30,
                                       thickness=2)
                except Exception:
                    pass
            cv2.putText(view, f"stage {stage}/5", (8, 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 230, 120), 2)
            qimg = QImage(view.data, view.shape[1], view.shape[0], 3 * view.shape[1],
                          QImage.Format.Format_BGR888)
            self.preview.setPixmap(QPixmap.fromImage(qimg.copy()).scaled(
                self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            log.debug("preview draw failed: %s", e)
            self.preview.setText("Preview unavailable")

    def _update_ui(self, stage: int) -> None:
        for i, lbl in enumerate(self.stage_labels):
            done = i < stage
            current = i == stage
            if done:
                lbl.setStyleSheet("color: #37d67a; border: 1px solid #2d9d5e;"
                                  "border-radius: 6px; padding: 4px 2px; font-size: 11px;")
            elif current:
                lbl.setStyleSheet("color: #ffe08a; border: 1px solid #e0b24f;"
                                  "border-radius: 6px; padding: 4px 2px; font-size: 11px;")
            else:
                lbl.setStyleSheet("color: #5f7ea0; border: 1px solid #223d5c;"
                                  "border-radius: 6px; padding: 4px 2px; font-size: 11px;")
        if stage < len(STAGE_TEXTS):
            self.hint.setText(STAGE_TEXTS[stage])
        else:
            self.hint.setText("Mapped \u2014 verifying cursor\u2026")

    # ---- buttons ---------------------------------------------------------
    def _confirm(self) -> None:
        self.core.confirm_calibration_point()
        if self.core.calibration.done:
            self._tick()

    def _skip(self) -> None:
        # accept the current fingertip regardless of pinch confidence
        self.core.confirm_calibration_point()
        if self.core.calibration.done:
            self._tick()

    def _cancel(self) -> None:
        self.core.cancel_calibration()
        self.reject()