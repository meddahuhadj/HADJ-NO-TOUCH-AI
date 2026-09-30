import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

import config.i18n as i18n
from config.i18n import tr
from ui import theme


class CameraWidget(QWidget):
    """Renders the live webcam feed with a skeletal overlay inside a glass frame."""

    PLACEHOLDER_SIZE = (520, 380)

    def __init__(self, parent=None):
        super(CameraWidget, self).__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            f"QLabel {{ background-color: {theme.CANVAS_DEEP};"
            f"border: 1px solid {theme.BORDER}; border-radius: {theme.RADIUS_LG}px; }}"
        )
        self.image_label.setMinimumSize(*self.PLACEHOLDER_SIZE)
        layout.addWidget(self.image_label)

        i18n.on_language_changed(self._on_language_changed)
        self._create_placeholder()

    # ------------------------------------------------------------------ #

    def _create_placeholder(self):
        width, height = self.PLACEHOLDER_SIZE
        pix = QPixmap(width, height)
        pix.fill(QColor(theme.CANVAS_DEEP))

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        inner = pix.rect().adjusted(14, 14, -14, -14)
        painter.setPen(QPen(QColor(theme.ACCENT), 1, Qt.DashLine))
        painter.drawRoundedRect(inner, theme.RADIUS_MD, theme.RADIUS_MD)

        # Camera glyph
        painter.setPen(QPen(QColor(theme.BORDER_STRONG), 2))
        body = inner.adjusted(inner.width() // 2 - 46, inner.height() // 2 - 40,
                              inner.width() // 2 + 22, inner.height() // 2 + 22)
        painter.drawRoundedRect(body, 10, 10)
        painter.drawLine(body.right() - 4, body.center().y(),
                         inner.center().x() + 52, inner.center().y() - 22)
        painter.drawLine(body.right() - 4, body.center().y(),
                         inner.center().x() + 52, inner.center().y() + 22)

        painter.setPen(QColor(theme.TEXT_FAINT))
        painter.drawText(pix.rect().adjusted(0, 96, 0, 0), Qt.AlignCenter,
                         tr("camera.standby"))
        painter.end()

        self.image_label.setPixmap(pix)

    def _on_language_changed(self, code: str):
        self.retranslate()

    def retranslate(self):
        self._create_placeholder()

    # ------------------------------------------------------------------ #

    def update_frame(self, frame_bgr: np.ndarray, gesture_name: str = "", confidence: float = 0.0):
        if frame_bgr is None:
            return
        height, width, channels = frame_bgr.shape
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        q_image = QImage(rgb_frame.data, width, height,
                         channels * width, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        lbl_size = self.image_label.size()
        if lbl_size.width() <= 1 or lbl_size.height() <= 1:
            lbl_size = self.image_label.minimumSize()
        self.image_label.setPixmap(
            pixmap.scaled(
                lbl_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def set_camera_off(self):
        self._create_placeholder()
