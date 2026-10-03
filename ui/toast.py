"""
Elegant glassmorphic Toast notification for touchless desktop feedback.
Displays quick temporary confirmations (e.g. 'Screenshot saved ✓') without blocking user interaction.
"""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui import theme


class ToastWidget(QFrame):
    """
    Floating animated toast pill that appears at the bottom-center of the parent widget.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)

        self.icon_label = QLabel(self)
        self.icon_label.setStyleSheet("font-size: 15px; font-weight: 800; background: transparent;")
        layout.addWidget(self.icon_label)

        self.text_label = QLabel(self)
        self.text_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(self.text_label)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)

        self.hide()

    def show_message(self, message: str, icon: str = "✓", tone: str = "success", duration_ms: int = 2600) -> None:
        """Displays toast message with specified tone (success, warning, info)."""
        self.text_label.setText(message)
        self.icon_label.setText(icon)

        if tone == "success":
            color = theme.SUCCESS
        elif tone == "warning":
            color = theme.WARNING
        elif tone == "danger":
            color = theme.DANGER
        else:
            color = theme.ACCENT

        self.icon_label.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 800; background: transparent;")

        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        self.hide_timer.stop()
        self.hide_timer.start(duration_ms)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        pw = parent.width()
        ph = parent.height()
        tw = self.width()
        th = self.height()
        # Position at bottom center, 60px above bottom edge
        self.move((pw - tw) // 2, max(20, ph - th - 64))

    def _fade_out(self) -> None:
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(theme.qcolor(theme.CANVAS_DEEP, 240))
        painter.setPen(QPen(theme.qcolor(theme.BORDER_STRONG, 180), 1.2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), theme.RADIUS_MD, theme.RADIUS_MD)
        painter.end()
