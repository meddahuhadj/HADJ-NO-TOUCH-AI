"""Small reusable UI widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget,
)


class StatusDot(QWidget):
    """A colored status dot + caption."""

    def __init__(self, label: str, color: str = "#888888", parent=None):
        super().__init__(parent)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {color}; font-size: 16px; border: none;")
        self.label = QLabel(label)
        self.label.setStyleSheet("color: #dfe9f5; font-size: 12px; border: none;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.dot)
        lay.addWidget(self.label)
        lay.addStretch(1)

    def set_active(self, on: bool, tooltip: str = "",
                   color_on: str = "#37d67a", color_off: str = "#ff6b6b"):
        self.dot.setStyleSheet(f"color: {color_on if on else color_off}; font-size: 16px;")
        if tooltip:
            self.setToolTip(tooltip)


class StatCard(QFrame):
    """Title + big value + small caption."""

    def __init__(self, title: str, value: str = "—", caption: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #12263d; border: 1px solid #223d5c; border-radius: 10px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self.title = QLabel(title)
        self.title.setStyleSheet("color: #7fa3c8; font-size: 11px; border: none;")
        self.value = QLabel(value)
        self.value.setStyleSheet("color: #eaf3ff; font-size: 22px; font-weight: bold; border: none;")
        self.value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.caption = QLabel(caption)
        self.caption.setStyleSheet("color: #5f7e9f; font-size: 10px; border: none;")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set_value(self, v: str):
        self.value.setText(v)


class BigCursorLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("color: #ffffff; font-size: 26px; font-weight: bold;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)