"""Main window: hosts the dashboard and wires the application core to the UI.

Also provides the system tray, dialogs (calibration, gesture trainer, debug
panel), the floating virtual keyboard and confirmation prompts for sensitive
actions. The dashboard receives this window as its ``app`` object.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QMenu, QSystemTrayIcon, QMessageBox,
)

from ..core.app import AppCore
from ..config import SETTINGS
from ..logging_setup import get_logger
from .dashboard import Dashboard
from .calibration_wizard import CalibrationWizard
from .gesture_trainer import GestureTrainer
from .debug_panel import DebugPanel
from ..interaction.virtual_keyboard import FloatingKeyboard

log = get_logger("ui.main")


def _make_tray_icon() -> QIcon:
    """Generate a simple HADJ glyph icon (no asset files needed)."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#123a63"))
    p.setPen(QColor("#2a6cb5"))
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setPen(QColor("#7cc3ff"))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(34)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "H")
    p.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.core = AppCore()
        self._quitting = False
        self._dialogs = {
            "calibration": None,
            "trainer": None,
            "keyboard": None,
            "debug": None,
        }
        self._tray = None

        self.dashboard = Dashboard(self)
        self.setCentralWidget(self.dashboard)
        self.setWindowTitle("HADJ NO-TOUCH AI")
        self.resize(1180, 720)

        self._wire_signals()
        self._build_menus()
        self._build_tray()
        self._apply_large_cursor()

    # ------------------------------------------------------------------
    # attribute/proxy surface used by the dashboard & panels
    # ------------------------------------------------------------------
    @property
    def profiles(self):
        return self.core.profiles

    @property
    def privacy(self):
        return self.core.privacy

    @property
    def engine(self):
        return self.core.engine

    def set_profile(self, pid: str) -> None:
        self.core.set_profile(pid)

    def emergency_stop(self) -> None:
        self.core.emergency_stop()

    def resume_from_emergency(self) -> None:
        self.core.resume_from_emergency()

    def pause_tracking(self, paused: bool) -> None:
        self.core.pause_tracking(paused)

    def toggle_camera(self) -> None:
        self.core.toggle_camera()

    def toggle_mic(self) -> None:
        self.core.toggle_mic()

    def toggle_privacy_mode(self) -> None:
        self.core.toggle_privacy_mode()

    # ------------------------------------------------------------------
    # signal wiring
    # ------------------------------------------------------------------
    def _wire_signals(self) -> None:
        c = self.core
        c.status_updated.connect(self.dashboard.update_status)
        c.frame_rendered.connect(self.dashboard.update_preview)
        c.toasts.connect(self.dashboard.on_toast)
        c.event_logged.connect(self.dashboard.on_log)
        c.voice_heard.connect(lambda t: None)  # surfaced via status snapshot
        c.profile_changed.connect(self._on_profile_changed)
        c.emergency_changed.connect(self._on_emergency_changed)
        c.request_confirmation.connect(self._on_confirm_request)

    # ------------------------------------------------------------------
    # menus & tray
    # ------------------------------------------------------------------
    def _build_menus(self) -> None:
        def act(parent, text, slot, shortcut=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            parent.addAction(a)
            return a

        m = self.menuBar()
        m_c = m.addMenu("&Control")
        act(m_c, "Camera On/Off", self.toggle_camera)
        act(m_c, "Microphone On/Off", self.toggle_mic)
        act(m_c, "Pause tracking", self._menu_pause)
        act(m_c, "Privacy mode", self.toggle_privacy_mode)
        m_c.addSeparator()
        act(m_c, "Emergency stop", self.emergency_stop, "Ctrl+Alt+H")
        act(m_c, "Resume control", self.resume_from_emergency)

        m_v = m.addMenu("&View")
        act(m_v, "Calibration wizard", self._ui_calibrate)
        act(m_v, "Virtual keyboard", self._ui_keyboard)
        act(m_v, "Teach my gesture", self._ui_trainer)
        act(m_v, "Debug panel", self._ui_debug)

        m_h = m.addMenu("&Help")
        act(m_h, "Quick guide", self._quick_guide)
        act(m_h, "About", self._about)

    def _menu_pause(self) -> None:
        self.core.pause_tracking(True)
        QTimer.singleShot(3000, lambda: self.core.pause_tracking(False))

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(_make_tray_icon(), self)
        self._tray.setToolTip("HADJ NO-TOUCH AI")
        menu = QMenu()
        menu.addAction("Show interface", self.show_normal)
        menu.addAction("Calibrate", self._ui_calibrate)
        menu.addAction("Emergency stop", self.emergency_stop)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_normal()

    def show_normal(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized
                            | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _apply_large_cursor(self) -> None:
        on = bool(self.core.profiles.active.cursor_behavior.get("large_cursor"))
        self.core.air_mouse.large_cursor(on)

    def _on_profile_changed(self, pid: str) -> None:
        self._apply_large_cursor()
        self.dashboard.update_status(self.core._status.filled())

    def _on_emergency_changed(self) -> None:
        if self.core.privacy.emergency_stopped:
            self.dashboard.on_emergency()
        else:
            self.dashboard.on_resume()

    def _on_confirm_request(self, intent) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Confirm action")
        box.setText("Confirm action?")
        box.setInformativeText(intent.describe())
        box.setStandardButtons(QMessageBox.StandardButton.Yes
                               | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self.core.confirm_pending()
        else:
            self.core.reject_pending()

    # ------------------------------------------------------------------
    # dialogs opened from the dashboard
    # ------------------------------------------------------------------
    def _ui_calibrate(self) -> None:
        win = self._dialogs["calibration"]
        if win is None or not win.isVisible():
            win = CalibrationWizard(self.core, self)
            win.destroyed.connect(lambda: self._dialogs.__setitem__("calibration", None))
            self._dialogs["calibration"] = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _ui_trainer(self) -> None:
        win = self._dialogs["trainer"]
        if win is None or not win.isVisible():
            win = GestureTrainer(self.core, self)
            win.destroyed.connect(lambda: self._dialogs.__setitem__("trainer", None))
            self._dialogs["trainer"] = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _ui_keyboard(self) -> None:
        win = self._dialogs["keyboard"]
        if win is None:
            win = FloatingKeyboard(voice_controller=self)
            win.dictation_toggled.connect(self._on_dictation_toggled)
            win.destroyed.connect(lambda: self._dialogs.__setitem__("keyboard", None))
            self._dialogs["keyboard"] = win
        if win.isVisible():
            win.hide()
        else:
            win.show()
        win.raise_()
        win.activateWindow()

    def _ui_debug(self) -> None:
        win = self._dialogs["debug"]
        if win is None or not win.isVisible():
            win = DebugPanel(self, self)
            win.destroyed.connect(lambda: self._dialogs.__setitem__("debug", None))
            self._dialogs["debug"] = win
            self.core.status_updated.connect(win.update_status)
        win.show()
        win.raise_()
        win.activateWindow()

    def _on_dictation_toggled(self, on: bool) -> None:
        self.core.set_dictation(on)
        if not on:
            kb = self._dialogs["keyboard"]
            if kb is not None:
                kb.stop_dictation_ui()

    def stop_dictation(self) -> None:
        self.core.set_dictation(False)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.core.start()
        if self.core.camera_error_hint:
            QMessageBox.warning(
                self, "Camera",
                f"Camera unavailable ({self.core.camera_error_hint}).\n\n"
                "Gestures are offline but voice can still be used.")
        self._first_run_calibration()

    def _first_run_calibration(self) -> None:
        try:
            already = self.core.db.latest_calibration() is not None
        except Exception:
            already = False
        if already:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("First run")
        box.setText("Set up your virtual interaction plane?")
        box.setInformativeText(
            "Calibrate now so the webcam fingertip maps correctly onto your "
            "screen. You can recalibrate any time from the dashboard.")
        y = box.addButton("Calibrate now", QMessageBox.ButtonRole.YesRole)
        box.addButton("Later", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() is y:
            self._ui_calibrate()

    def closeEvent(self, e) -> None:
        # hide to tray instead of quitting
        e.ignore()
        self.hide()
        if self._tray is not None:
            self._tray.showMessage(
                "HADJ NO-TOUCH AI",
                "Still running in the system tray (gestures remain active).",
                QSystemTrayIcon.MessageIcon.Information,
                2500)

    def _quit(self) -> None:
        self._quitting = True
        try:
            self.core.stop()
        except Exception as e:
            log.warning("stop error: %s", e)
        self.hide()
        if self._tray is not None:
            self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ------------------------------------------------------------------
    # help dialogs
    # ------------------------------------------------------------------
    def _quick_guide(self) -> None:
        QMessageBox.information(
            self, "Quick guide",
            "POINT \u2192 move cursor\n"
            "PINCH (thumb+index) \u2192 left click\n"
            "Double pinch \u2192 double click\n"
            "Thumb + middle \u2192 right click\n"
            "Pinch + move \u2192 drag\n"
            "Open palm + move vertically \u2192 scroll\n"
            "Swipe \u2192 next/previous (slides, pages, tracks, tabs)\n"
            "Open palm held 1-2 s \u2192 pause interaction\n"
            "Fist held \u2192 interaction lock\n\n"
            "Voice: 'open chrome', 'next page', 'volume 50 percent',\n"
            "'close this window', 'take screenshot' \u2014 English, French, Arabic.\n\n"
            "Emergency stop: CTRL + ALT + H")

    def _about(self) -> None:
        QMessageBox.about(
            self, "HADJ NO-TOUCH AI",
            "HADJ NO-TOUCH AI \u2014 a multimodal AI platform for controlling a "
            "computer without touching it (hands, voice, optional gaze).\n\n"
            "Privacy-first: camera and microphone processing stays local by "
            "default; no frames are uploaded or recorded.\n\n"
            "This is a virtual/contactless interaction layer, not a touchscreen.")