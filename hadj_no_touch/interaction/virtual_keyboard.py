"""Floating virtual keyboard (PySide6).

A real, always-on-top window. The user activates keys with the air pointer,
real mouse or voice. Keystrokes are sent to the focused Windows application
through the real keyboard driver.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QStyle, QLabel, QHBoxLayout, QToolButton,
    QVBoxLayout,
)
from PySide6.QtGui import QAction

from ..logging_setup import get_logger
from ..windows import keyboard_control

log = get_logger("interaction.keyboard")

# (label, vk_name_or_char, special)
TOP_ROW = ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "BACKSPACE"]
ROW1 = ["TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"]
ROW2 = ["CAPSLOCK", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "ENTER"]
ROW3 = ["LSHIFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "RSHIFT"]
ROW4 = ["LCTRL", "LWIN", "LALT", "SPACE", "RALT", "RCTRL", "PRINTSCREEN", "INSERT", "DELETE",
        "LEFT", "DOWN", "RIGHT", "UP"]

MODIFIERS = {"CAPSLOCK": False}
CHORD_KEYS = {"LCTRL": "CTRL", "LWIN": "WIN", "LALT": "ALT", "RALT": "ALT",
              "RCTRL": "CTRL", "LSHIFT": "SHIFT", "RSHIFT": "SHIFT"}


class FloatingKeyboard(QWidget):
    """Qt virtual keyboard that injects real keystrokes."""

    key_sent = Signal(str)
    dictation_toggled = Signal(bool)

    def __init__(self, voice_controller=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HADJ Virtual Keyboard")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._dragging = None
        self._hold = {}  # currently held modifier
        self._caps = False
        self._voice_controller = voice_controller
        self._build_ui()
        self.setMinimumWidth(760)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 6)

        header = QHBoxLayout()
        title = QLabel("⌨ Virtual Keyboard")
        title.setStyleSheet("font-weight: bold; color: #0f2b46;")
        header.addWidget(title)
        header.addStretch(1)
        self.dict_btn = QToolButton()
        self.dict_btn.setText("🎤 Voice")
        self.dict_btn.setCheckable(True)
        self.dict_btn.toggled.connect(self._on_dictation)
        header.addWidget(self.dict_btn)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(3)
        all_rows = [TOP_ROW, ROW1, ROW2, ROW3, ROW4]
        widths = {r: 0 for r in range(len(all_rows))}
        for ri, row in enumerate(all_rows):
            for ci, key in enumerate(row):
                widths[ri] += 1
                btn = self._make_key(key, ri, ci)
                span = 1
                if key in ("BACKSPACE",):
                    span = 2
                elif key == "TAB":
                    span = 2
                elif key == "ENTER":
                    span = 2
                elif key == "CAPSLOCK":
                    span = 2
                elif key in ("LSHIFT", "RSHIFT"):
                    span = 2
                elif key == "SPACE":
                    span = 9
                if span > 1:
                    grid.addWidget(btn, ri, ci, 1, span)
                    ci += span - 1
                else:
                    grid.addWidget(btn, ri, ci, 1, 1)
        root.addLayout(grid)

        self._style_buttons()

    def _make_key(self, key: str, ri: int, ci: int) -> QPushButton:
        btn = QPushButton(key)
        btn.setMinimumHeight(34)
        btn.setObjectName(f"key_{key}")
        if self._is_wide(key):
            btn.setMinimumWidth(70)
        else:
            btn.setMinimumWidth(44)
        btn.clicked.connect(lambda checked=False, k=key: self._press(k))
        return btn

    @staticmethod
    def _is_wide(key: str) -> bool:
        return key in ("BACKSPACE", "TAB", "CAPSLOCK", "ENTER", "LSHIFT", "RSHIFT",
                       "LCTRL", "LWIN", "LALT", "RALT", "RCTRL", "PRINTSCREEN")

    def _style_buttons(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #eef3f8; font-size: 13px; }
            QPushButton { background: #ffffff; color: #10243e;
                          border: 1px solid #c7d3e0; border-radius: 6px; }
            QPushButton:hover { background: #dbe9f7; }
            QPushButton:pressed { background: #bcd8ef; }
            QToolButton { background: #10243e; color: white; border-radius: 6px; padding: 4px 8px; }
            """
        )

    # ---- key handling --------------------------------------------------------
    def _press(self, key: str) -> None:
        if key in CHORD_KEYS:
            self._hold[key] = CHORD_KEYS[key]
            self.key_sent.emit(key)
            return
        if key == "CAPSLOCK":
            self._caps = not self._caps
            self.key_sent.emit(key)
            return
        if key == "SPACE":
            keyboard_control.type_text(" ")
            self._release_hold()
            self.key_sent.emit(key)
            return
        if key in ("BACKSPACE", "ENTER", "TAB", "PRINTSCREEN", "INSERT", "DELETE",
                   "LEFT", "RIGHT", "UP", "DOWN"):
            keyboard_control.tap(key if key != "BACKSPACE" else "BACK")
            self._release_hold()
            self.key_sent.emit(key)
            return
        if len(key) == 1:
            char = key
            if self._caps:
                char = char.upper() if char.isalpha() else self._shifted_char(char)
            mods = [v for v in self._hold.values()]
            if mods and (char.isalpha() or char.isdigit()):
                keyboard_control.tap(char, mods)
            else:
                keyboard_control.type_text(char)
        self._release_hold()
        self.key_sent.emit(key)

    @staticmethod
    def _shifted_char(key: str) -> str:
        pairs = {"`": "~", "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
                 "6": "^", "7": "&", "8": "*", "9": "(", "0": ")", "-": "_",
                 "=": "+", "[": "{", "]": "}", "\\": "|", ";": ":", "'": "\"",
                 ",": "<", ".": ">", "/": "?"}
        return pairs.get(key, key)

    def _release_hold(self) -> None:
        self._hold.clear()

    def _on_dictation(self, on: bool) -> None:
        self.dictation_toggled.emit(on)

    # ---- window chrome ----------------------------------------------------------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = (e.globalPosition().toPoint() - self.frameGeometry().topLeft())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._dragging is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._dragging)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._dragging = None
        super().mouseReleaseEvent(e)

    def closeEvent(self, e) -> None:
        if self._voice_controller and self.dict_btn.isChecked():
            self._voice_controller.stop_dictation()
            self.dict_btn.setChecked(False)
        super().closeEvent(e)

    def stop_dictation_ui(self) -> None:
        if self.dict_btn.isChecked():
            self.dict_btn.setChecked(False)