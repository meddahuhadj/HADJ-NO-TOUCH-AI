import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

import config.i18n as i18n
from config.i18n import tr
from ui import theme


from config.settings_manager import SettingsManager
from PySide6.QtWidgets import QPushButton, QHBoxLayout


class CameraWidget(QWidget):
    """Renders the live webcam feed with a skeletal overlay, aspect ratio preservation, and mirror toggle."""

    PLACEHOLDER_SIZE = (520, 380)

    def __init__(self, parent=None):
        super(CameraWidget, self).__init__(parent)
        self.settings = SettingsManager()
        self.mirror_enabled: bool = bool(self.settings.get("performance.mirror_camera", True))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container with overlay controls
        self.container = QWidget(self)
        container_lay = QVBoxLayout(self.container)
        container_lay.setContentsMargins(0, 0, 0, 0)

        # Image display label
        self.image_label = QLabel(self.container)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            f"QLabel {{ background-color: {theme.CANVAS_DEEP};"
            f"border: 1px solid {theme.BORDER}; border-radius: {theme.RADIUS_LG}px; }}"
        )
        self.image_label.setMinimumSize(*self.PLACEHOLDER_SIZE)
        container_lay.addWidget(self.image_label)

        # Floating controls row on top of camera widget
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(12, 12, 12, 0)
        controls_row.addStretch()

        self.mirror_btn = QPushButton("🪞 " + tr("camera.mirror"), self)
        self.mirror_btn.setObjectName("ghost")
        self.mirror_btn.setCursor(Qt.PointingHandCursor)
        self.mirror_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(20, 24, 32, 0.75); color: {theme.TEXT};"
            f"border: 1px solid {theme.BORDER}; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: rgba(0, 220, 180, 0.25); border-color: {theme.ACCENT}; }}"
        )
        self.mirror_btn.clicked.connect(self._toggle_mirror)
        controls_row.addWidget(self.mirror_btn)

        layout.addLayout(controls_row)
        layout.addWidget(self.container)

        i18n.on_language_changed(self._on_language_changed)
        self._create_placeholder()

    # ------------------------------------------------------------------ #

    def _toggle_mirror(self):
        self.mirror_enabled = not self.mirror_enabled
        self.settings.set("performance.mirror_camera", self.mirror_enabled)
        state_str = tr("common.on") if self.mirror_enabled else tr("common.off")
        self.mirror_btn.setText(f"🪞 {tr('camera.mirror')}: {state_str}")

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
        state_str = tr("common.on") if self.mirror_enabled else tr("common.off")
        self.mirror_btn.setText(f"🪞 {tr('camera.mirror')}: {state_str}")

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

        # Fast SIMD resize with OpenCV
        resized_bgr = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Letterbox/pillarbox into exact canvas size to avoid stretch
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        canvas[:] = (18, 22, 28) # CANVAS_DEEP
        x_off = (target_w - new_w) // 2
        y_off = (target_h - new_h) // 2
        canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized_bgr

        rgb_frame = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        q_image = QImage(rgb_frame.data, target_w, target_h, 3 * target_w, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap)

    def set_camera_off(self):
        self._create_placeholder()
