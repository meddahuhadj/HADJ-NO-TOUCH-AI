from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QPushButton

import config.i18n as i18n
from config.i18n import tr, tr_gesture
from config.settings_manager import SettingsManager
from core.event_bus import EventBus, EventType
from core.qt_bridge import QtBridge
from core.app_profile_manager import AppProfileManager, AppProfile
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
    Transparent, non-intrusive interactive banner that stays above every Windows application.
    Reports the live touchless state — arming status, radial progress, recognized gesture, safety alert —
    with draggability and quick dominant-hand / compact-mode switching.
    """

    def __init__(self, parent=None):
        super(FloatingOverlayHUD, self).__init__(parent)
        self.settings = SettingsManager()
        self.event_bus = EventBus()

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(460, 78)

        self.app_profile_mgr = AppProfileManager()
        self._current_profile: str = self.app_profile_mgr.get_active_profile().value
        self._current_app_name: str = "Desktop"

        self._tone = "idle"
        self._dot_color = theme.SUCCESS
        self._status_key = "hud.ready"
        self._status_args: dict = {}
        self._raw_command = ""
        self._badge_key = "hud.badge_ready"
        self._badge_tone = "idle"
        self._active_gesture = ""
        self._security_alert_active = False
        self._is_armed: bool = False
        self._hold_progress: float = 0.0
        self._is_compact_hud: bool = False

        self._reposition()
        self._init_ui()
        self._wire_events()

        self.fade_timer = QTimer(self)
        self.fade_timer.setInterval(4000)
        self.fade_timer.timeout.connect(self._reset_to_idle)

        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #
    # Drag & Drop Movement
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.settings.set("hud.position", [self.x(), self.y()])
            event.accept()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _reposition(self):
        saved = self.settings.get("hud.position")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                self.move(int(saved[0]), int(saved[1]))
                return
            except (ValueError, TypeError):
                pass

        from PySide6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.move(480, 24)
            return
        geo = screen.geometry()
        self.move(max(20, geo.width() - self.width() - 25), max(20, geo.height() - self.height() - 65))

    def _init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 10, 16, 10)
        self.main_layout.setSpacing(12)

        # Arming Status Pill Button
        self.arm_btn = QPushButton(self)
        self.arm_btn.setCursor(Qt.PointingHandCursor)
        self.arm_btn.clicked.connect(self._toggle_arm_state)
        self.arm_btn.setFixedHeight(30)
        self.main_layout.addWidget(self.arm_btn)

        # Center text details
        self.text_column = QVBoxLayout()
        self.text_column.setSpacing(1)
        self.title_label = QLabel(self)
        self.title_label.setStyleSheet(
            f"color: {theme.TEXT_FAINT}; font-size: 9px; font-weight: 800;"
            "letter-spacing: 1.4px; background: transparent;"
        )
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        self.text_column.addWidget(self.title_label)
        self.text_column.addWidget(self.status_label)
        self.main_layout.addLayout(self.text_column, 1)

        # Contextual App Profile Badge Pill
        self.profile_btn = QPushButton(self)
        self.profile_btn.setCursor(Qt.PointingHandCursor)
        self.profile_btn.setFixedHeight(28)
        self.profile_btn.clicked.connect(self._cycle_profile_lock)
        self.main_layout.addWidget(self.profile_btn)

        # Gesture Badge
        self.gesture_badge = QLabel(self)
        self.gesture_badge.setAlignment(Qt.AlignCenter)
        self.gesture_badge.setMinimumWidth(80)
        self.main_layout.addWidget(self.gesture_badge)

        # Dominant Hand Toggle Pill
        self.hand_btn = QPushButton(self)
        self.hand_btn.setCursor(Qt.PointingHandCursor)
        self.hand_btn.setFixedSize(38, 28)
        self.hand_btn.setStyleSheet(
            f"background-color: {theme.CANVAS_DEEP}; color: {theme.TEXT_MUTED};"
            f"border: 1px solid {theme.BORDER}; border-radius: 6px; font-size: 11px; font-weight: 700;"
        )
        self.hand_btn.clicked.connect(self._toggle_dominant_hand)
        self.main_layout.addWidget(self.hand_btn)

        # Compact / Fullsize Toggle Button
        self.compact_btn = QPushButton("🗗", self)
        self.compact_btn.setCursor(Qt.PointingHandCursor)
        self.compact_btn.setFixedSize(28, 28)
        self.compact_btn.setStyleSheet(
            f"background-color: transparent; color: {theme.TEXT_FAINT};"
            f"border: none; font-size: 13px; font-weight: 800;"
        )
        self.compact_btn.clicked.connect(self._toggle_compact_hud)
        self.main_layout.addWidget(self.compact_btn)

    def _wire_events(self):
        self.qt_bridge = QtBridge()
        self.qt_bridge.speech_state.connect(self.set_listening_mode)
        self.qt_bridge.speech_command.connect(lambda cmd, _: self.show_command(cmd))
        self.qt_bridge.gesture_detected.connect(lambda gest, _: self.update_gesture(gest))
        self.qt_bridge.emergency_stop.connect(self._handle_emergency_signal)
        self.qt_bridge.security_prompt.connect(lambda payload: self.show_security_alert(payload.get("command", "")))
        self.qt_bridge.security_cleared.connect(lambda _reason: self.clear_security_alert())
        self.qt_bridge.arm_state_changed.connect(self.set_armed)
        self.qt_bridge.gesture_diagnostics.connect(self._on_gesture_diagnostics)
        self.qt_bridge.app_profile_changed.connect(self._on_app_profile_changed)

    def _handle_emergency_signal(self, reason: str):
        if reason == "RESTORED":
            self.set_listening_mode(False)
        else:
            self.show_emergency()

    def _on_gesture_diagnostics(self, gesture: str, diag_reason: str, conf: float, is_armed: bool, progress: float):
        self._is_armed = is_armed
        self._hold_progress = progress
        self._refresh_arm_button()
        if not self._raw_command and not self._security_alert_active:
            if diag_reason and diag_reason.startswith("diag."):
                self.status_label.setText(tr(diag_reason))
        self.update()

    # ------------------------------------------------------------------ #
    # Painting
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        """Draws the frosted glass pill, radial gauge, and glowing progress bar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Glass background
        bg_color = theme.qcolor(theme.CANVAS_DEEP, 240)
        border_color = theme.qcolor(theme.SUCCESS if self._is_armed else theme.BORDER_STRONG, 160)
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1.2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

        # Progress bar at bottom
        if self._hold_progress > 0.0:
            pw = int((self.width() - 8) * min(1.0, max(0.0, self._hold_progress)))
            painter.fillRect(4, self.height() - 4, pw, 3, theme.qcolor(theme.ACCENT, 240))

        painter.end()

    # ------------------------------------------------------------------ #
    # State & Handlers
    # ------------------------------------------------------------------ #

    def set_armed(self, armed: bool):
        self._is_armed = armed
        self._refresh_arm_button()
        self.update()

    def _toggle_arm_state(self):
        self._is_armed = not self._is_armed
        self.event_bus.publish(EventType.GESTURE_ARM_TOGGLED, {"armed": self._is_armed})
        self.qt_bridge.arm_state_changed.emit(self._is_armed)
        self._refresh_arm_button()
        self.update()

    def _refresh_arm_button(self):
        if self._is_armed:
            txt = "⚡ " + tr("arm.armed")
            style = (
                f"background-color: {theme.SUCCESS_SOFT}; color: {theme.SUCCESS};"
                f"border: 1.5px solid {theme.SUCCESS}; border-radius: 8px;"
                "padding: 4px 10px; font-size: 11px; font-weight: 800;"
            )
        else:
            txt = "🔒 " + tr("arm.disarmed")
            style = (
                f"background-color: {theme.CANVAS}; color: {theme.TEXT_MUTED};"
                f"border: 1px solid {theme.BORDER}; border-radius: 8px;"
                "padding: 4px 10px; font-size: 11px; font-weight: 700;"
            )
        self.arm_btn.setText(txt)
        self.arm_btn.setStyleSheet(style)

    def _toggle_dominant_hand(self):
        current = self.settings.get("gestures.dominant_hand", "right")
        new_hand = "left" if current == "right" else "right"
        self.settings.set("gestures.dominant_hand", new_hand)
        self.hand_btn.setText("✋ L" if new_hand == "left" else "✋ R")
        self.title_label.setText(
            f"{tr('hud.title').upper()} · {'✋ ' + tr('calib.hand_left') if new_hand == 'left' else '✋ ' + tr('calib.hand_right')}"
        )

    def _toggle_compact_hud(self):
        self._is_compact_hud = not self._is_compact_hud
        if self._is_compact_hud:
            self.setFixedSize(260, 52)
            self.text_column.setParent(None)
            self.profile_btn.setVisible(False)
            self.compact_btn.setText("🗖")
        else:
            self.setFixedSize(460, 78)
            self.main_layout.insertLayout(1, self.text_column, 1)
            self.profile_btn.setVisible(True)
            self.compact_btn.setText("🗗")
        self.adjustSize()

    def _on_app_profile_changed(self, profile: str, app_name: str):
        self._current_profile = profile
        self._current_app_name = app_name
        self._refresh_profile_button()

    def _cycle_profile_lock(self):
        modes = [None, AppProfile.BROWSER, AppProfile.MEDIA, AppProfile.DOCUMENT, AppProfile.DESKTOP]
        curr = self.app_profile_mgr.locked_profile
        try:
            curr_idx = modes.index(curr)
        except ValueError:
            curr_idx = 0
        next_mode = modes[(curr_idx + 1) % len(modes)]
        self.app_profile_mgr.lock_profile(next_mode)
        self._current_profile = self.app_profile_mgr.get_active_profile().value
        self._refresh_profile_button()

    def _refresh_profile_button(self):
        prof = self._current_profile.lower()
        icons = {
            "browser": "🌐",
            "media": "🎬",
            "document": "📄",
            "desktop": "🖥️",
        }
        icon = icons.get(prof, "🖥️")
        profile_key = f"profile.{prof}"
        translated_name = tr(profile_key) if profile_key in i18n.STRINGS.get("en", {}) else prof.upper()
        locked = self.app_profile_mgr.locked_profile is not None
        lock_marker = "🔒" if locked else ""
        self.profile_btn.setText(f"{icon} {translated_name} {lock_marker}".strip())
        self.profile_btn.setToolTip(f"{tr('profile.active_label', profile=translated_name)} ({self._current_app_name})")
        self.profile_btn.setStyleSheet(
            f"background-color: {theme.CANVAS_DEEP}; color: {theme.TEXT_MUTED};"
            f"border: 1px solid {theme.BORDER}; border-radius: 6px;"
            "padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )

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
        self.fade_timer.start()

    def update_gesture(self, gesture_name: str, confidence: float = 0.0):
        active = gesture_name if gesture_name and gesture_name != "NONE" else ""
        if active == self._active_gesture:
            return
        self._active_gesture = active
        if self._active_gesture:
            label = tr_gesture(self._active_gesture) or self._active_gesture
            self.gesture_badge.setText(label)
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
        self._security_alert_active = True
        self._set_status("hud.confirm", theme.WARNING, 700, command=cmd)
        self._set_badge("hud.badge_confirm", "alert")

    def clear_security_alert(self):
        if not getattr(self, "_security_alert_active", False):
            return
        self._security_alert_active = False
        self._reset_to_idle()

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

    def _paint_status(self, colour: str, weight: int):
        self.status_label.setStyleSheet(
            f"color: {colour}; font-size: 13px; font-weight: {weight}; background: transparent;"
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
        hand = self.settings.get("gestures.dominant_hand", "right")
        self.hand_btn.setText("✋ L" if hand == "left" else "✋ R")
        hand_name = tr("calib.hand_left") if hand == "left" else tr("calib.hand_right")
        self.title_label.setText(f"{tr('hud.title').upper()} · ✋ {hand_name}")

        self._refresh_arm_button()

        if self._raw_command:
            self.status_label.setText(f'"{self._raw_command}"')
        elif self._status_key:
            self.status_label.setText(tr(self._status_key, **self._status_args))
        if self._active_gesture:
            self.gesture_badge.setText(tr_gesture(self._active_gesture))
        else:
            self.gesture_badge.setText(tr(self._badge_key))
        self._set_badge_tone(self._badge_tone)
        self._refresh_profile_button()
