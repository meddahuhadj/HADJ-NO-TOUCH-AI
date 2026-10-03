import math
import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from config.settings_manager import SettingsManager


class VirtualCursorOverlay(QWidget):
    """
    Lightweight 80x80 transparent overlay that follows the virtual cursor.
    Features:
    - Circular progress ring for Dwell mode.
    - State-based color indicator: REST (Blue) -> HOVER (Green) -> CLICK (Red).
    - Accessible non-color visual markers (Shape + Symbol: Dot, Ring, Crosshair).
    - Throttled to ~30 Hz via coalescing timer to prevent DWM overhead.
    """

    SIZE = 80
    HALF = SIZE // 2

    def __init__(self, parent=None):
        super(VirtualCursorOverlay, self).__init__(parent)
        self.settings = SettingsManager()

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

        self.setFixedSize(self.SIZE, self.SIZE)

        # Logical cursor position
        self._target_x = 960
        self._target_y = 540
        self._current_x = 960
        self._current_y = 540
        self._move_pending = False

        # Dwell & Gesture State
        self.dwell_progress: float = 0.0  # 0.0 to 1.0
        self.cursor_state: str = "REST"   # "REST", "HOVER", "CLICK"
        self.is_pinching: bool = False
        self.is_emergency: bool = False
        self.pulse_phase: float = 0.0

        # Coalescing timer (~30 FPS)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self._wire_events()

    def _wire_events(self):
        from core.qt_bridge import QtBridge
        self.qt_bridge = QtBridge()
        self.qt_bridge.cursor_moved.connect(self._on_cursor_signal)
        self.qt_bridge.gesture_detected.connect(self._on_gesture_signal)
        self.qt_bridge.emergency_stop.connect(self._on_emergency_signal)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            import sys
            if sys.platform == "win32":
                import ctypes
                hwnd = int(self.winId())
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_LAYERED = 0x00080000
                WS_EX_NOACTIVATE = 0x08000000
                WS_EX_TOOLWINDOW = 0x00000080
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                )
        except Exception:
            pass

    def _on_cursor_signal(self, screen_x: int, screen_y: int):
        self._target_x = screen_x
        self._target_y = screen_y
        self._move_pending = True

    def _on_gesture_signal(self, gesture_name: str, _conf: float):
        self.is_pinching = gesture_name in ("PINCH", "PINCH_HOLD", "DOUBLE_PINCH")
        if self.is_pinching:
            self.cursor_state = "CLICK"
            self.dwell_progress = 1.0
        elif gesture_name in ("POINT", "INDEX_STABLE"):
            self.cursor_state = "HOVER"
        else:
            self.cursor_state = "REST"
            self.dwell_progress = 0.0

        if gesture_name != "FIST":
            self.is_emergency = False

    def _on_emergency_signal(self, reason: str):
        self.is_emergency = (reason != "RESTORED")

    def update_position(self, screen_x: int, screen_y: int):
        self._on_cursor_signal(screen_x, screen_y)

    def set_dwell_progress(self, progress: float, state: str = "HOVER"):
        """Sets Dwell progress (0.0 to 1.0) and updates cursor state."""
        self.dwell_progress = max(0.0, min(1.0, progress))
        self.cursor_state = state

    def _on_tick(self):
        self.pulse_phase = (self.pulse_phase + 0.1) % 6.2832

        if self._move_pending:
            self._move_pending = False
            new_x = int(self._target_x - self.HALF)
            new_y = int(self._target_y - self.HALF)
            if new_x != self._current_x or new_y != self._current_y:
                self._current_x = new_x
                self._current_y = new_y
                self.move(self._current_x, self._current_y)

        self.update()

    def paintEvent(self, event):
        if not self.settings.get("gestures.virtual_cursor_preview", True):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPoint(self.HALF, self.HALF)
        radius = 24.0

        if self.is_emergency:
            # Emergency Stop State (Red Warning Cross)
            painter.setPen(QPen(QColor(239, 68, 68, 240), 3))
            painter.setBrush(QBrush(QColor(239, 68, 68, 60)))
            painter.drawEllipse(center, 22, 22)
            painter.setPen(QPen(QColor(255, 255, 255, 255), 3))
            painter.drawLine(self.HALF - 8, self.HALF - 8, self.HALF + 8, self.HALF + 8)
            painter.drawLine(self.HALF + 8, self.HALF - 8, self.HALF - 8, self.HALF + 8)

        elif self.cursor_state == "CLICK" or self.is_pinching:
            # State 3: CLICK / READY TO CLICK (Red + Crosshair Target)
            painter.setPen(QPen(QColor(239, 68, 68, 240), 3))
            painter.setBrush(QBrush(QColor(239, 68, 68, 90)))
            painter.drawEllipse(center, 18, 18)

            # Non-color crosshair symbol (⊕)
            painter.setPen(QPen(QColor(255, 255, 255, 240), 2))
            painter.drawLine(self.HALF - 12, self.HALF, self.HALF + 12, self.HALF)
            painter.drawLine(self.HALF, self.HALF - 12, self.HALF, self.HALF + 12)
            painter.drawPoint(center)

        elif self.cursor_state == "HOVER" or self.dwell_progress > 0.0:
            # State 2: HOVER (Green + Dwell Progress Ring + Open Ring Symbol)
            # Track ring background
            track_rect = QRectF(self.HALF - radius, self.HALF - radius, radius * 2, radius * 2)
            painter.setPen(QPen(QColor(34, 197, 94, 60), 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(track_rect)

            # Dwell progress arc (0 to 360 degrees)
            span_angle = int(-self.dwell_progress * 360 * 16)
            painter.setPen(QPen(QColor(34, 197, 94, 240), 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(track_rect, 90 * 16, span_angle)

            # Center Green Hover Circle with Open Ring Marker
            painter.setPen(QPen(QColor(34, 197, 94, 220), 2))
            painter.setBrush(QBrush(QColor(34, 197, 94, 140)))
            painter.drawEllipse(center, 8, 8)

        else:
            # State 1: REST (Blue + Solid Center Dot + Subtle Pulsing Halo)
            pulse = math.sin(self.pulse_phase) * 2.0
            radius_outer = 16 + pulse

            painter.setPen(QPen(QColor(59, 130, 246, 120), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, int(radius_outer), int(radius_outer))

            # Solid Center Blue Dot (●)
            painter.setPen(QPen(QColor(59, 130, 246, 240), 2))
            painter.setBrush(QBrush(QColor(59, 130, 246, 220)))
            painter.drawEllipse(center, 6, 6)

        painter.end()
