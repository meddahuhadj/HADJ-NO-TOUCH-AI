"""
HADJ NO-TOUCH AI — Software Physical Privacy LED Indicator
Top-Most floating LED badge that flashes whenever camera or microphone are active.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QBrush, QPen


class PrivacyIndicatorLED(QWidget):
    """
    Floating 32x32 software LED badge indicating hardware camera/microphone capture.
    Flashes at 2 Hz in Green when active, transparent when idle.
    """

    def __init__(self, parent=None):
        super(PrivacyIndicatorLED, self).__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(32, 32)

        self.cam_active: bool = True
        self.mic_active: bool = True
        self._flash_state: bool = True

        self._timer = QTimer(self)
        self._timer.setInterval(500)  # 2 Hz
        self._timer.timeout.connect(self._on_flash_tick)
        self._timer.start()

    def set_sensor_state(self, cam: bool, mic: bool):
        self.cam_active = cam
        self.mic_active = mic
        self.update()

    def _on_flash_tick(self):
        if self.cam_active or self.mic_active:
            self._flash_state = not self._flash_state
        else:
            self._flash_state = False
        self.update()

    def paintEvent(self, event):
        if not (self.cam_active or self.mic_active):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPoint(16, 16)

        color = QColor(34, 197, 94, 255) if self._flash_state else QColor(34, 197, 94, 90)

        # Outer glow ring
        painter.setPen(QPen(QColor(34, 197, 94, 60), 2))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(center, 10, 10)

        # Inner bright core
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawEllipse(center, 3, 3)

        painter.end()
