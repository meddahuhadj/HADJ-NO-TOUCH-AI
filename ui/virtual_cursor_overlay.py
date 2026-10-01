import math
import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from config.settings_manager import SettingsManager


class VirtualCursorOverlay(QWidget):
    """
    Lightweight 80x80 transparent overlay that follows the virtual cursor.

    Key performance design:
    - Small window (80x80) so DWM only composites a tiny region, not the full screen.
    - Move is throttled to max ~30 Hz via a coalescing timer to avoid Win32
      SetWindowPos message flooding that causes 'reageert niet'.
    - The pulse animation timer only repaints, never moves the window.
    - Position updates are stored immediately but the actual window move
      is deferred to the next timer tick.
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

        # Logical cursor position (updated immediately from signal)
        self._target_x = 960
        self._target_y = 540
        # Actual window position (updated by timer)
        self._current_x = 960
        self._current_y = 540
        self._move_pending = False

        self.is_pinching = False
        self.is_emergency = False
        self.pulse_phase = 0.0

        # Single timer drives both animation and coalesced move at ~30 FPS
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

    # ------------------------------------------------------------------ #
    # Signal handlers — store state only, never call self.move()
    # ------------------------------------------------------------------ #

    def _on_cursor_signal(self, screen_x: int, screen_y: int):
        self._target_x = screen_x
        self._target_y = screen_y
        self._move_pending = True

    def _on_gesture_signal(self, gesture_name: str, _conf: float):
        self.is_pinching = gesture_name in ("PINCH", "PINCH_HOLD", "DOUBLE_PINCH")
        if gesture_name != "FIST":
            self.is_emergency = False

    def _on_emergency_signal(self, reason: str):
        self.is_emergency = (reason != "RESTORED")

    # For backward compat with MainWindow line 77 connecting cursor_moved
    def update_position(self, screen_x: int, screen_y: int):
        self._on_cursor_signal(screen_x, screen_y)

    # ------------------------------------------------------------------ #
    # Timer tick — the ONLY place self.move() is ever called
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Paint
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        if not self.settings.get("gestures.virtual_cursor_preview", True):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPoint(self.HALF, self.HALF)

        if self.is_emergency:
            painter.setPen(QPen(QColor(239, 68, 68, 220), 2.5))
            painter.setBrush(QBrush(QColor(239, 68, 68, 50)))
            painter.drawEllipse(center, 18, 18)
            painter.setPen(QPen(QColor(254, 202, 202, 255), 2))
            painter.drawPoint(center)

        elif self.is_pinching:
            painter.setPen(QPen(QColor(14, 165, 233, 240), 2))
            painter.setBrush(QBrush(QColor(56, 189, 248, 120)))
            painter.drawEllipse(center, 12, 12)
            painter.setPen(QPen(QColor(255, 255, 255, 255), 3))
            painter.drawPoint(center)

        else:
            pulse = math.sin(self.pulse_phase) * 2.0
            radius_outer = 16 + pulse

            painter.setPen(QPen(QColor(56, 189, 248, 140), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, int(radius_outer), int(radius_outer))

            painter.setPen(QPen(QColor(52, 211, 153, 240), 2))
            painter.setBrush(QBrush(QColor(52, 211, 153, 180)))
            painter.drawEllipse(center, 4, 4)

        painter.end()
