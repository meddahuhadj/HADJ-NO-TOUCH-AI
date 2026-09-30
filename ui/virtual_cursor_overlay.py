import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from core.event_bus import EventBus, EventType
from config.settings_manager import SettingsManager


class VirtualCursorOverlay(QWidget):
    """
    Transparent, click-through screen overlay that renders a futuristic glowing pointer ring
    at the active virtual cursor coordinates on Windows.
    """

    def __init__(self, parent=None):
        super(VirtualCursorOverlay, self).__init__(parent)
        self.event_bus = EventBus()
        self.settings = SettingsManager()

        # Transparent, topmost, click-through window
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.setFixedSize(60, 60)

        # State
        self.cursor_x = 960
        self.cursor_y = 540
        self.is_pinching = False
        self.is_emergency = False
        self.pulse_phase = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(20)  # 50 FPS smooth render
        self.anim_timer.timeout.connect(self._on_tick)
        self.anim_timer.start()

        self._wire_events()

    def _wire_events(self):
        self.event_bus.subscribe(EventType.CURSOR_MOVED, lambda d: self.update_position(d.get("x", 0), d.get("y", 0)))
        self.event_bus.subscribe(EventType.GESTURE_RECOGNIZED, lambda d: self._handle_gesture(d.get("gesture", "")))
        self.event_bus.subscribe(EventType.EMERGENCY_STOP, lambda _: self._handle_emergency(True))

    def update_position(self, screen_x: int, screen_y: int):
        self.cursor_x = screen_x
        self.cursor_y = screen_y
        # Center the 60x60 overlay window over the cursor point
        self.move(int(screen_x - 30), int(screen_y - 30))
        self.update()

    def _handle_gesture(self, gesture: str):
        self.is_pinching = (gesture in ["PINCH", "PINCH_HOLD", "DOUBLE_PINCH"])
        if gesture not in ["FIST"]:
            self.is_emergency = False
        self.update()

    def _handle_emergency(self, active: bool):
        self.is_emergency = active
        self.update()

    def _on_tick(self):
        self.pulse_phase = (self.pulse_phase + 0.1) % 6.28
        self.update()

    def paintEvent(self, event):
        if not self.settings.get("gestures.virtual_cursor_preview", True):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPoint(30, 30)

        if self.is_emergency:
            # Red emergency ring
            painter.setPen(QPen(QColor(239, 68, 68, 220), 2.5))
            painter.setBrush(QBrush(QColor(239, 68, 68, 50)))
            painter.drawEllipse(center, 18, 18)
            painter.setPen(QPen(QColor(254, 202, 202, 255), 2))
            painter.drawPoint(center)

        elif self.is_pinching:
            # Active pinch: pulsating cyan disk
            painter.setPen(QPen(QColor(14, 165, 233, 240), 2))
            painter.setBrush(QBrush(QColor(56, 189, 248, 120)))
            painter.drawEllipse(center, 12, 12)
            painter.setPen(QPen(QColor(255, 255, 255, 255), 3))
            painter.drawPoint(center)

        else:
            # Default: elegant futuristic glowing dual ring
            import math
            pulse = math.sin(self.pulse_phase) * 2.0
            radius_outer = 16 + pulse

            # Outer ring
            painter.setPen(QPen(QColor(56, 189, 248, 140), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, int(radius_outer), int(radius_outer))

            # Inner crosshair dot
            painter.setPen(QPen(QColor(52, 211, 153, 240), 2))
            painter.setBrush(QBrush(QColor(52, 211, 153, 180)))
            painter.drawEllipse(center, 4, 4)

        painter.end()
