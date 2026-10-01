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
        if frame_bgr is None or frame_bgr.size == 0:
            return

        lbl_size = self.image_label.size()
        target_w = lbl_size.width() if lbl_size.width() > 1 else self.PLACEHOLDER_SIZE[0]
        target_h = lbl_size.height() if lbl_size.height() > 1 else self.PLACEHOLDER_SIZE[1]

        h, w, c = frame_bgr.shape
        scale = min(target_w / float(w), target_h / float(h))
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        # Fast SIMD resize with OpenCV to eliminate main-thread Qt software scaling lag
        resized_bgr = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        rgb_frame = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)

        # .copy() ensures QImage owns its memory buffer, preventing memory leaks & dangling pointers
        q_image = QImage(rgb_frame.data, new_w, new_h, c * new_w, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap)

    def set_camera_off(self):
        self._create_placeholder()
