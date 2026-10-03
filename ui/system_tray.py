from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

import config.i18n as i18n
from config.i18n import tr
from ui import theme


class HadjSystemTray(QSystemTrayIcon):
    """Windows notification-area integration with background quick controls."""

    def __init__(self, main_window, parent=None):
        super(HadjSystemTray, self).__init__(parent)
        self.main_window = main_window

        self.setIcon(self._build_icon())
        self._build_menu()
        self.retranslate()

        self.activated.connect(self._on_tray_activated)

    # ------------------------------------------------------------------ #

    def _build_icon(self) -> QIcon:
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.ACCENT_DEEP))
        painter.drawEllipse(1, 1, 30, 30)
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(8, 8, 16, 16)
        painter.setBrush(QColor(theme.CANVAS))
        painter.drawEllipse(13, 13, 6, 6)
        painter.end()
        return QIcon(pix)

    def _build_menu(self):
        self.menu = QMenu()
        self.menu.setStyleSheet(theme.stylesheet())

        self.action_show = self.menu.addAction("")
        self.action_show.triggered.connect(self._show_dashboard)

        self.menu.addSeparator()

        self.action_toggle_voice = self.menu.addAction("")
        self.action_toggle_voice.triggered.connect(self.main_window.toggle_voice)

        self.action_toggle_gesture = self.menu.addAction("")
        self.action_toggle_gesture.triggered.connect(self.main_window.toggle_gesture)

        self.action_offline = self.menu.addAction("")
        self.action_offline.setEnabled(False)

        self.menu.addSeparator()

        self.action_emergency = self.menu.addAction("")
        self.action_emergency.triggered.connect(self.main_window.trigger_emergency_stop)

        self.menu.addSeparator()

        self.action_quit = self.menu.addAction("")
        self.action_quit.triggered.connect(self.main_window.close_app_completely)

        self.setContextMenu(self.menu)

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def retranslate(self):
        self.setToolTip(tr("app.tray_tooltip"))

        voice_on = getattr(self.main_window, "voice_enabled", True)
        gesture_on = getattr(self.main_window, "gesture_enabled", True)

        self.action_show.setText(tr("tray.show"))
        self.action_toggle_voice.setText(
            tr("main.toggle", name=tr("tray.voice"),
               state=tr("common.on") if voice_on else tr("common.off"))
        )
        self.action_toggle_gesture.setText(
            tr("main.toggle", name=tr("tray.gesture"),
               state=tr("common.on") if gesture_on else tr("common.off"))
        )
        self.action_offline.setText(
            f"{tr('tray.offline')} — {tr('privacy.status_offline')}"
        )
        self.action_emergency.setText(tr("tray.emergency"))
        self.action_quit.setText(tr("tray.quit"))

    # ------------------------------------------------------------------ #

    def _show_dashboard(self):
        self.main_window.showNormal()
        self.main_window.activateWindow()
        self.main_window.raise_()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            if self.main_window.isVisible():
                self.main_window.hide()
            else:
                self._show_dashboard()
