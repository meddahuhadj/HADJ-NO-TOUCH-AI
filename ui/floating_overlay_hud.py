from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import config.i18n as i18n
from config.i18n import tr, tr_gesture
from core.event_bus import EventBus, EventType
from ui import theme

# tone key -> (foreground, fill, border)
_BADGE_TONES = {
    "idle": (theme.ACCENT, theme.ACCENT_SOFT, theme.alpha(theme.ACCENT, 120)),
    "active": (theme.SUCCESS, theme.SUCCESS_SOFT, theme.alpha(theme.SUCCESS, 120)),
    "alert": (theme.WARNING, theme.WARNING_SOFT, theme.alpha(theme.WARNING, 140)),
    "danger": (theme.DANGER, theme.DANGER_SOFT, theme.alpha(theme.DANGER, 150)),
}


class FloatingOverlayHUD(QWidget):
    """
    Transparent, non-intrusive banner that stays above every Windows application.
    Reports the live touchless state — listening, recognised gesture, safety alert —
    even when the main window is minimised to the notification area.
    """

    def __init__(self, parent=None):
        super(FloatingOverlayHUD, self).__init__(parent)
        self.event_bus = EventBus()

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(400, 78)

        self._tone = "idle"
        self._dot_color = theme.SUCCESS
        self._status_key = "hud.ready"
        self._status_args: dict = {}
        self._raw_command = ""
        self._badge_key = "hud.badge_ready"
        self._badge_tone = "idle"
        self._active_gesture = ""

        self._reposition()
        self._init_ui()
        self._wire_events()

        self.fade_timer = QTimer(self)
        self.fade_timer.setInterval(4000)
        self.fade_timer.timeout.connect(self._reset_to_idle)

        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _reposition(self):
        from PySide6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.move(480, 24)
            return
        geo = screen.geometry()
        self.move((geo.width() - self.width()) // 2, 24)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        self.indicator_label = QLabel("●", self)
        self.indicator_label.setFixedWidth(14)
        self.indicator_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.indicator_label)

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        self.title_label = QLabel(self)
        self.title_label.setStyleSheet(
            f"color: {theme.TEXT_FAINT}; font-size: 9px; font-weight: 800;"
            "letter-spacing: 1.4px; background: transparent;"
        )
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        text_column.addWidget(self.title_label)
        text_column.addWidget(self.status_label)
        layout.addLayout(text_column)

        layout.addStretch()

        self.gesture_badge = QLabel(self)
        self.gesture_badge.setAlignment(Qt.AlignCenter)
        self.gesture_badge.setMinimumWidth(88)
        layout.addWidget(self.gesture_badge)

    def _wire_events(self):
        self.event_bus.subscribe(EventType.SPEECH_LISTENING_START, lambda _: self.set_listening_mode(True))
        self.event_bus.subscribe(EventType.SPEECH_LISTENING_END, lambda _: self.set_listening_mode(False))
        self.event_bus.subscribe(EventType.SPEECH_RECOGNIZED, lambda d: self.show_command(d.get("command", "")))
        self.event_bus.subscribe(EventType.GESTURE_RECOGNIZED, lambda d: self.update_gesture(d.get("gesture", "")))
        self.event_bus.subscribe(EventType.EMERGENCY_STOP, lambda _: self.show_emergency())
        self.event_bus.subscribe(EventType.SECURITY_CONFIRM_REQUEST, lambda d: self.show_security_alert(d.get("command", "")))

    # ------------------------------------------------------------------ #
    # Painting
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        """Draws the frosted, rounded dark-glass pill behind the HUD content."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(theme.qcolor(theme.CANVAS, 234))
        painter.setPen(QPen(theme.qcolor(theme.ACCENT, 105), 1.2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)
        painter.end()

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def set_listening_mode(self, active: bool):
        self.fade_timer.stop()
        self._raw_command = ""
        if active:
            self._set_status("hud.listening", theme.ACCENT, 700)
        else:
            self._set_status("hud.ready", theme.SUCCESS, 600)
        self._set_badge("hud.badge_ready", "idle")

    def show_command(self, cmd_text: str):
        self._raw_command = cmd_text
        self.status_label.setText(f'"{cmd_text}"')
        self._paint_status(theme.VIOLET, 700)
        self._paint_indicator(theme.VIOLET)
        self.fade_timer.start()

    def update_gesture(self, gesture_name: str):
        self._active_gesture = gesture_name if gesture_name and gesture_name != "NONE" else ""
        if self._active_gesture:
            self.gesture_badge.setText(tr_gesture(self._active_gesture))
            self._set_badge_tone("active")
        else:
            self._set_badge("hud.badge_tracking", "idle")

    def show_emergency(self):
        self.fade_timer.stop()
        self._raw_command = ""
        self._set_status("hud.emergency", theme.DANGER, 700)
        self._set_badge("hud.badge_halted", "danger")

    def show_security_alert(self, cmd: str):
        self.fade_timer.stop()
        self._raw_command = ""
        self._set_status("hud.confirm", theme.WARNING, 700, command=cmd)
        self._set_badge("hud.badge_confirm", "alert")

    def _reset_to_idle(self):
        self.fade_timer.stop()
        self._raw_command = ""
        self._set_status("hud.ready_active", theme.SUCCESS, 600)
        self._set_badge("hud.badge_tracking", "idle")

    # -- small helpers ------------------------------------------------------ #

    def _set_status(self, key: str, colour: str, weight: int, **args):
        self._status_key = key
        self._status_args = args
        self.status_label.setText(tr(key, **args))
        self._paint_status(colour, weight)
        self._paint_indicator(colour)

    def _paint_status(self, colour: str, weight: int):
        self.status_label.setStyleSheet(
            f"color: {colour}; font-size: 13px; font-weight: {weight}; background: transparent;"
        )

    def _paint_indicator(self, colour: str):
        self.indicator_label.setText("●")
        self.indicator_label.setStyleSheet(
            f"color: {colour}; font-size: 16px; font-weight: 700; background: transparent;"
        )

    def _set_badge(self, key: str, tone: str):
        self._active_gesture = ""
        self._badge_key = key
        self.gesture_badge.setText(tr(key))
        self._set_badge_tone(tone)

    def _set_badge_tone(self, tone: str):
        self._badge_tone = tone
        foreground, fill, border = _BADGE_TONES[tone]
        self.gesture_badge.setStyleSheet(
            f"background-color: {fill}; color: {foreground};"
            f"border: 1px solid {border}; border-radius: 8px;"
            "padding: 4px 10px; font-size: 10px; font-weight: 700;"
        )

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, code: str):
        self.retranslate()

    def retranslate(self):
        self.title_label.setText(tr("hud.title").upper())
        if self._raw_command:
            self.status_label.setText(f'"{self._raw_command}"')
        elif self._status_key:
            self.status_label.setText(tr(self._status_key, **self._status_args))
        if self._active_gesture:
            self.gesture_badge.setText(tr_gesture(self._active_gesture))
        else:
            self.gesture_badge.setText(tr(self._badge_key))
        self._set_badge_tone(self._badge_tone)
