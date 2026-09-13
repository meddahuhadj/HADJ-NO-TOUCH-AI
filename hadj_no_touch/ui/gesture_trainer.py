"""Gesture trainer dialog ("TEACH MY GESTURE").

Lets the user record a custom movement pattern several times, then bind it to
a real action (launch an app, type text, switch profile, take a screenshot,
or any registered intent). Templates are stored in the local database.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton,
    QListWidget, QMessageBox, QGroupBox, QGridLayout, QListWidgetItem,
)

from ..core.app import AppCore
from ..logging_setup import get_logger

log = get_logger("ui.trainer")

ACTION_KINDS = [
    ("launch_app:", "Launch an application"),
    ("type_text:", "Type text"),
    ("open_profile:", "Switch to a profile"),
    ("open_document:", "Open documents folder"),
    ("screenshot", "Take a screenshot"),
    ("", "Custom intent (e.g. VOLUME_UP)"),
]


class GestureTrainer(QDialog):
    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("HADJ \u2014 Teach My Gesture")
        self.setMinimumSize(520, 480)
        self._samples: list = []

        lay = QVBoxLayout(self)

        title = QLabel("\u270b AI Gesture Trainer")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #7cc3ff;")
        lay.addWidget(title)

        note = QLabel(
            "Perform the same movement several times while your hand is visible. "
            "The pattern is learned from the hand trajectory and stored only on this "
            "computer."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9fc7e8; font-size: 11px;")
        lay.addWidget(note)

        form = QGridLayout()
        form.addWidget(QLabel("Gesture name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. 'Open calculator'")
        form.addWidget(self.name_edit, 0, 1)

        form.addWidget(QLabel("Action type:"), 1, 0)
        self.action_combo = QComboBox()
        for code, label in ACTION_KINDS:
            self.action_combo.addItem(label, code)
        form.addWidget(self.action_combo, 1, 1)

        form.addWidget(QLabel("Action value:"), 2, 0)
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("e.g. chrome, VOLUME_UP, next page\u2026")
        form.addWidget(self.value_edit, 2, 1)
        lay.addLayout(form)

        samples_box = QGroupBox("Samples")
        sb = QVBoxLayout(samples_box)
        self.samples_list = QListWidget()
        sb.addWidget(self.samples_list)
        row = QHBoxLayout()
        self.btn_record = QPushButton("Record sample (1.2 s)")
        self.btn_record.clicked.connect(self._record)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear)
        row.addWidget(self.btn_record)
        row.addWidget(self.btn_clear)
        sb.addLayout(row)
        lay.addWidget(samples_box)

        existing_box = QGroupBox("Saved gestures")
        eb = QVBoxLayout(existing_box)
        self.known_list = QListWidget()
        eb.addWidget(self.known_list)
        row2 = QHBoxLayout()
        self.btn_delete = QPushButton("Delete selected")
        self.btn_delete.clicked.connect(self._delete)
        row2.addWidget(self.btn_delete)
        eb.addLayout(row2)
        lay.addWidget(existing_box)

        btns = QHBoxLayout()
        self.btn_save = QPushButton("Save gesture")
        self.btn_save.clicked.connect(self._save)
        done_btn = QPushButton("Close")
        done_btn.clicked.connect(self.accept)
        btns.addWidget(self.btn_save)
        btns.addStretch(1)
        btns.addWidget(done_btn)
        lay.addLayout(btns)

        self._refresh_known()

    # ---- helpers ---------------------------------------------------------
    def _action_string(self) -> str:
        kind = self.action_combo.currentData() or ""
        value = self.value_edit.text().strip()
        if not kind:
            # free-form custom intent
            return value or ""
        return f"{kind}{value}" if value else kind.rstrip(":")

    def _refresh_known(self) -> None:
        self.known_list.clear()
        for g in self.core.list_custom_gestures():
            self.known_list.addItem(QListWidgetItem(
                f"{g['name']} \u2192 {g['action'] or '(unassigned)'}"))
        self._render_samples()

    def _render_samples(self) -> None:
        self.samples_list.clear()
        for i, _ in enumerate(self._samples):
            self.samples_list.addItem(f"Sample {i + 1} \u2713")
        self.samples_list.addItem(f"{len(self._samples)} sample(s) recorded")

    # ---- actions ---------------------------------------------------------
    def _record(self) -> None:
        name = self.name_edit.text().strip() or "custom"
        self.setEnabled(False)
        self.samples_list.addItem("Recording\u2026 keep your hand visible")
        try:
            path = self.core.record_custom_gesture_sample(name)
            if not path:
                QMessageBox.warning(
                    self, "Recording",
                    "No valid hand trajectory captured. Make sure your hand is "
                    "clearly visible to the webcam.")
                return
            self._samples.extend(path)
            self._render_samples()
        finally:
            self.setEnabled(True)

    def _clear(self) -> None:
        self._samples.clear()
        self._render_samples()

    def _delete(self) -> None:
        item = self.known_list.currentItem()
        if not item:
            return
        name = item.text().split(" \u2192 ")[0].strip()
        self.core.delete_custom_gesture(name)
        self._refresh_known()
        self.core.toasts.emit(f"Deleted custom gesture '{name}'")

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Save", "Give the gesture a name.")
            return
        if len(self._samples) < 2:
            QMessageBox.warning(
                self, "Save",
                "Record at least 2 samples of the movement so the AI can learn it.")
            return
        action = self._action_string()
        try:
            self.core.save_custom_gesture(name, action, list(self._samples))
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        QMessageBox.information(
            self, "Saved",
            f"Gesture '{name}' saved \u2192 {action or 'assigned to dashboard'}.\n"
            "Perform it any time while your hand is visible to trigger the action.")
        self._samples.clear()
        self._refresh_known()