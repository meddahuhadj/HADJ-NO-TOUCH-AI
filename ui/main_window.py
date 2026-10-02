import os
import sys
import threading

import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QStackedWidget,
)
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
    _WEBENGINE_AVAILABLE = True
except Exception as e:
    print(f"[MainWindow] QtWebEngine notice: {e}")
    _WEBENGINE_AVAILABLE = False

from web_server import start_background_server, stop_background_server

from ui import theme
from ui import widgets as W
from ui.camera_widget import CameraWidget
from ui.privacy_dashboard import PrivacyDashboardDialog
from ui.calibration_wizard import CalibrationWizardDialog
from ui.accessibility_panel import AccessibilityDialog
from ui.macro_dialog import MacroManagerDialog
from ui.demo_mode import DemoModeDialog
from ui.system_tray import HadjSystemTray
from ui.floating_overlay_hud import FloatingOverlayHUD
from ui.virtual_keyboard_hud import VirtualKeyboardHUD
from ui.virtual_cursor_overlay import VirtualCursorOverlay
from ui.toast import ToastWidget
from core.audio_effects import AudioEffects

import config.i18n as i18n
from config.i18n import tr, tr_gesture, tr_intent, tr_profile, tr_result, tr_risk
from core.event_bus import EventBus, EventType
from core.profile_manager import ProfileManager, PerformanceProfile
from core.app_profile_manager import AppProfileManager, AppProfile
from core.security_engine import SecurityEngine
from core.command_orchestrator import CommandOrchestrator
from core.logger import EventLogger
from core.companion_server import CompanionServer
from core.qt_bridge import QtBridge
from vision.camera_stream import CameraStream
from voice.speech_engine import SpeechEngine
from config.settings_manager import SettingsManager


class MainWindow(QMainWindow):
    """Primary application window for HADJ NO-TOUCH OFFLINE AI."""

    def __init__(self):
        super(MainWindow, self).__init__()
        self.resize(1180, 760)
        self.setMinimumSize(1000, 680)

        # Application Icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Core engines
        self.settings = SettingsManager()
        self.event_bus = EventBus()
        self.profile_mgr = ProfileManager()
        self.security = SecurityEngine()
        self.orchestrator = CommandOrchestrator()
        self.logger = EventLogger()
        self.speech_engine = SpeechEngine()
        self.camera_stream = CameraStream()
        self.companion_server = CompanionServer(port=8766)
        self.audio_effects = AudioEffects()
        self.toast = ToastWidget(self)
        self.app_profile_mgr = AppProfileManager()
        self.app_profile_mgr.start()
        self._current_profile = self.app_profile_mgr.get_active_profile().value
        self._current_app_name = "Desktop"

        # Privacy Kill Switch & Confirmation countdown state
        self.privacy_mode_active: bool = False
        self.confirm_countdown_seconds: int = 5
        self.confirm_countdown_timer = QTimer(self)
        self.confirm_countdown_timer.setInterval(1000)
        self.confirm_countdown_timer.timeout.connect(self._on_confirm_timer_tick)

        # Compact mode state & global shortcuts
        self.is_compact_mode = False
        self._normal_geometry = None
        self.shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        self.shortcut_f11.activated.connect(self.toggle_compact_mode)
        self.shortcut_ctrl_m = QShortcut(QKeySequence("Ctrl+M"), self)
        self.shortcut_ctrl_m.activated.connect(self.toggle_compact_mode)

        # QtBridge for rock-solid thread-safe cross-thread signal delivery
        self.qt_bridge = QtBridge()

        # Transient UI state
        self.voice_enabled = True
        self.gesture_enabled = True
        self.vision_enabled = True
        self.skeleton_enabled = bool(self.settings.get("gestures.show_hand_skeleton", True))
        self._listening = False
        self._has_command = False
        # Whether a confirmation banner is currently on screen, so the clear
        # handler knows whether a security_cleared signal concerns it.
        self._security_prompt_active = False
        # Privacy Mode & Destructive Action Confirmation State
        self.privacy_mode_active = False
        self._confirm_seconds_remaining = 5
        self._confirm_timer = QTimer(self)
        self._confirm_timer.setInterval(1000)
        self._confirm_timer.timeout.connect(self._on_confirm_timer_tick)
        self._command_in_flight = False

        # HUD overlays
        self.floating_hud = FloatingOverlayHUD()
        self.floating_hud.show()
        self.cursor_overlay = VirtualCursorOverlay()
        # Overlay window is kept hidden so it never intercepts mouse clicks or saturates DWM
        self.virtual_keyboard = VirtualKeyboardHUD()

        # Connect thread-safe QtBridge signals directly to GUI slots
        self.qt_bridge.frame_ready.connect(self._on_frame_update)
        # cursor_overlay connects cursor_moved internally — no double connection
        self.qt_bridge.gesture_detected.connect(self.floating_hud.update_gesture)
        self.qt_bridge.gesture_diagnostics.connect(self._on_gesture_diagnostics)
        self.qt_bridge.arm_state_changed.connect(self._on_arm_state_changed)
        self.qt_bridge.speech_state.connect(self._update_listening_state)
        self.qt_bridge.speech_command.connect(self._on_speech_command)
        self.qt_bridge.emergency_stop.connect(self._handle_emergency_stop_event)
        self.qt_bridge.security_prompt.connect(self._show_security_prompt)
        self.qt_bridge.security_cleared.connect(self._clear_security_prompt)
        self.qt_bridge.command_finished.connect(self._on_command_finished)
        self.qt_bridge.app_profile_changed.connect(self._on_app_profile_changed)

        theme.apply_to(self)
        self._init_ui()

        # System tray (built after the UI so it can share the translated labels)
        self.tray = HadjSystemTray(self)
        self.tray.show()

        self._wire_events()
        i18n.on_language_changed(self._on_language_changed)

        # Start background workers
        start_background_server(port=8000)
        self.camera_stream.start()
        self.speech_engine.start()
        self.companion_server.start()

        # Global emergency stop hotkey (Ctrl + Alt + Escape)
        from automation.global_hotkey import GlobalHotkeyWorker
        self.global_hotkey = GlobalHotkeyWorker()
        self.global_hotkey.hotkey_triggered.connect(self.trigger_emergency_stop)
        self.global_hotkey.start()

        # In-app shortcut fallback
        self.esc_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Escape"), self)
        self.esc_shortcut.activated.connect(self.trigger_emergency_stop)

        # Telemetry timer (updates CPU, RAM, FPS every second)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_telemetry)
        self.telemetry_timer.start(1000)

        self.retranslate()
        self._update_telemetry()

        # Guided calibration on first launch
        if not self.settings.get("calibration.guided_done", False):
            QTimer.singleShot(800, self.show_calibration)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(theme.PAD, theme.PAD - 4, theme.PAD, theme.PAD - 4)
        root.setSpacing(theme.GAP)

        root.addWidget(self._build_header())

        # Main view stack (Page 0: Modern Web Dashboard, Page 1: Native Diagnostic Workspace)
        self.view_stack = QStackedWidget(central)

        if _WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView(self)
            ws = self.web_view.settings()
            ws.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            ws.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            ws.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            ws.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            ws.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
            # Auto-grant permissions for webcam/mic
            self.web_view.page().featurePermissionRequested.connect(
                lambda origin, feat: self.web_view.page().setFeaturePermission(
                    origin, feat, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                )
            )
            self.web_view.load(QUrl("http://127.0.0.1:8000"))
            self.view_stack.addWidget(self.web_view)
        else:
            self.web_view = None

        # Native Diagnostic & Sensor Workspace
        self.native_container = QWidget(central)
        native_lay = QVBoxLayout(self.native_container)
        native_lay.setContentsMargins(0, 0, 0, 0)
        native_lay.setSpacing(theme.GAP)
        native_lay.addLayout(self._build_sensor_bar())
        native_lay.addWidget(self._build_pc_control_dock())
        native_lay.addLayout(self._build_workspace(), 1)
        native_lay.addWidget(self._build_action_bar())

        self.view_stack.addWidget(self.native_container)
        root.addWidget(self.view_stack, 1)

        # Start on modern web dashboard by default
        self.view_stack.setCurrentIndex(0 if _WEBENGINE_AVAILABLE else 1)

    def _build_header(self) -> QWidget:
        card = W.frame(self, "card")
        lay = W.hbox(margins=(theme.PAD - 6, 12, theme.PAD - 6, 12))

        identity = QVBoxLayout()
        identity.setSpacing(3)
        self.brand_label = W.label(card, "", "brandTitle")
        self.subtitle_label = W.label(card, "", "brandSubtitle")
        self.brand_label.setMinimumWidth(210)
        identity.addWidget(self.brand_label)
        identity.addWidget(self.subtitle_label)
        lay.addLayout(identity)

        lay.addWidget(W.spacer())

        self.offline_badge = W.label(card, "", "badgeSuccess")
        lay.addWidget(self.offline_badge)

        self.app_profile_pill = QPushButton("", card)
        self.app_profile_pill.setCursor(Qt.PointingHandCursor)
        self.app_profile_pill.clicked.connect(self._cycle_profile_lock)
        self.app_profile_pill.setStyleSheet(
            f"background-color: {theme.CANVAS_DEEP}; color: {theme.TEXT_MUTED};"
            f"border: 1px solid {theme.BORDER}; border-radius: 6px;"
            "padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        lay.addWidget(self.app_profile_pill)

        self.view_switch_btn = QPushButton("", card)
        self.view_switch_btn.setCursor(Qt.PointingHandCursor)
        self.view_switch_btn.setObjectName("viewSwitchBtn")
        self.view_switch_btn.setStyleSheet(
            f"background-color: {theme.ACCENT_SOFT}; color: {theme.ACCENT};"
            f"border: 1px solid {theme.ACCENT}; border-radius: 6px;"
            "padding: 6px 12px; font-size: 11px; font-weight: 700;"
        )
        self.view_switch_btn.clicked.connect(self.toggle_view_mode)
        lay.addWidget(self.view_switch_btn)

        self.header_lang_btn = QPushButton("", card)
        self.header_lang_btn.setCursor(Qt.PointingHandCursor)
        self.header_lang_btn.setObjectName("headerLangBtn")
        self.header_lang_btn.clicked.connect(self._cycle_language)
        self.header_lang_btn.setStyleSheet(
            f"background-color: {theme.CANVAS_DEEP}; color: {theme.TEXT_PRIMARY};"
            f"border: 1px solid {theme.BORDER}; border-radius: 6px;"
            "padding: 6px 12px; font-size: 11px; font-weight: 700;"
        )
        lay.addWidget(self.header_lang_btn)

        self.theme_btn = W.button(self, "", "ghost", self._toggle_theme)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.theme_btn)

        self.compact_mode_btn = W.button(self, "", "ghost", self.toggle_compact_mode)
        self.compact_mode_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.compact_mode_btn)

        self.auto_calib_btn = QPushButton("", card)
        self.auto_calib_btn.setObjectName("calibAuto")
        self.auto_calib_btn.setCursor(Qt.PointingHandCursor)
        self.auto_calib_btn.clicked.connect(self._on_quick_auto_calibration)
        lay.addWidget(self.auto_calib_btn)

        self.web_btn = W.button(self, "", "ghost", self._open_web_companion)
        self.web_btn.setObjectName("companionBtn")
        self.web_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.web_btn)

        self.emergency_btn = W.button(self, "", "danger", self.trigger_emergency_stop)
        self.emergency_btn.setMinimumWidth(150)
        self.emergency_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.emergency_btn)

        card.setLayout(lay)
        return card

    def _build_pc_control_dock(self) -> QWidget:
        card = W.frame(self, "card")
        lay = W.hbox(spacing=6, margins=(14, 8, 14, 8))

        self.dock_title_label = W.label(card, "", "sectionTitle")
        lay.addWidget(self.dock_title_label)

        # (i18n key, slot) — labels are resolved in retranslate() so the dock
        # follows the interface language like every other surface.
        self.dock_actions = [
            ("dock.desktop", lambda: self.orchestrator.win_control.show_desktop()),
            ("dock.task_view", lambda: self.orchestrator.win_control.open_task_view()),
            ("dock.snap_left", lambda: self.orchestrator.win_control.snap_window_left()),
            ("dock.snap_right", lambda: self.orchestrator.win_control.snap_window_right()),
            ("dock.screenshot", self._take_screenshot_action),
            ("dock.volume_up", lambda: self.orchestrator.win_control.volume_up()),
            ("dock.volume_down", lambda: self.orchestrator.win_control.volume_down()),
            ("dock.volume_mute", lambda: self.orchestrator.win_control.volume_mute()),
            ("dock.keyboard", self.toggle_virtual_keyboard),
            ("dock.lock", lambda: self.orchestrator.win_control.lock_pc()),
            ("dock.task_manager", lambda: self.orchestrator.win_control.open_task_manager()),
        ]

        self.dock_buttons = []
        for key, fn in self.dock_actions:
            btn = QPushButton("", card)
            btn.setObjectName("quickAction")
            btn.setCursor(Qt.PointingHandCursor)

            def _make_handler(k=key, action_fn=fn, b=btn):
                def _handler():
                    self._highlight_button(b)
                    if k == "dock.screenshot":
                        self.audio_effects.play_screenshot_chime()
                    else:
                        self.audio_effects.play_button_feedback()
                    try:
                        action_fn()
                    except Exception as e:
                        print(f"[DockAction] Error: {e}")
                    if k != "dock.screenshot":
                        self.toast.show_message(tr(k), icon="⚡", tone="info")
                return _handler

            btn.clicked.connect(_make_handler())
            self.dock_buttons.append((key, btn))
            lay.addWidget(btn)

        lay.addWidget(W.spacer())
        card.setLayout(lay)
        return card

    def _build_sensor_bar(self) -> QHBoxLayout:
        lay = W.hbox(spacing=10)

        self.voice_pill = W.switch_button(self, "", self.toggle_voice)
        self.gesture_pill = W.switch_button(self, "", self.toggle_gesture)
        self.vision_pill = W.switch_button(self, "", self.toggle_vision)
        self.eco_pill = W.switch_button(self, "", self._toggle_eco_mode)
        self.hand_pill = W.switch_button(self, "", self._toggle_dominant_hand)
        for pill in (self.voice_pill, self.gesture_pill, self.vision_pill, self.eco_pill, self.hand_pill):
            lay.addWidget(pill)

        lay.addWidget(W.separator())
        self.listening_indicator = W.label(self, "", "metric")
        lay.addWidget(self.listening_indicator)

        lay.addWidget(W.separator())
        self.cam_privacy_badge = W.label(self, "📷 CAM ON", "badgeSuccess")
        self.mic_privacy_badge = W.label(self, "🎙️ MIC ON", "badgeSuccess")
        lay.addWidget(self.cam_privacy_badge)
        lay.addWidget(self.mic_privacy_badge)

        self.privacy_kill_switch_btn = QPushButton("", self)
        self.privacy_kill_switch_btn.setCursor(Qt.PointingHandCursor)
        self.privacy_kill_switch_btn.clicked.connect(self.toggle_privacy_mode)
        lay.addWidget(self.privacy_kill_switch_btn)

        lay.addWidget(W.spacer())

        self.language_label = W.label(self, "", "faint")
        lay.addWidget(self.language_label)

        self.language_combo = QComboBox(self)
        self.language_combo.setItemDelegate(QStyledItemDelegate(self.language_combo))
        self.language_combo.setCursor(Qt.PointingHandCursor)
        self.language_combo.setMinimumWidth(136)
        self.language_combo.addItems(
            [i18n.native_language_name(c) for c in i18n.available_languages()]
        )
        self.language_combo.currentIndexChanged.connect(self._on_language_selected)
        lay.addWidget(self.language_combo)



        lay.addWidget(W.separator())
        self.profile_label = W.label(self, "", "faint")
        lay.addWidget(self.profile_label)

        self.profile_combo = QComboBox(self)
        self.profile_combo.setItemDelegate(QStyledItemDelegate(self.profile_combo))
        self.profile_combo.setCursor(Qt.PointingHandCursor)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        lay.addWidget(self.profile_combo)

        self.telemetry_label = W.label(self, "", "mono")
        self.telemetry_label.setTextFormat(Qt.RichText)
        lay.addWidget(self.telemetry_label)

        return lay

    def _build_workspace(self) -> QHBoxLayout:
        split = W.hbox()
        split.setSpacing(theme.GAP)

        # Camera column
        camera_col = W.vbox()
        self.camera_widget = CameraWidget(self)
        camera_col.addWidget(self.camera_widget, 1)

        gesture_strip = W.hbox()
        self.gesture_info_label = W.label(self, "", "faint")
        gesture_strip.addWidget(self.gesture_info_label)
        gesture_strip.addWidget(W.spacer())
        self.skeleton_toggle = W.switch_button(self, "", self._toggle_skeleton)
        gesture_strip.addWidget(self.skeleton_toggle)
        camera_col.addLayout(gesture_strip)
        split.addLayout(camera_col, 3)

        # Command column
        command_col = W.vbox()
        intent_card, intent_layout, self.intent_title_label = W.panel_with_title(self, "")
        self.current_cmd_label = W.label(intent_card, "", "pageTitle", wrap=True)
        self.intent_details_label = W.label(intent_card, "", "faint", wrap=True)
        intent_layout.addWidget(self.current_cmd_label)
        intent_layout.addWidget(self.intent_details_label)

        # Destructive Confirmation Action Box (5s live countdown)
        self.confirm_actions_box = QWidget(intent_card)
        confirm_lay = W.hbox(spacing=10)
        confirm_lay.setContentsMargins(0, 8, 0, 0)
        self.confirm_btn = W.button(self.confirm_actions_box, "", "primary", self._on_confirm_click)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.reject_btn = W.button(self.confirm_actions_box, "", "danger", self._on_reject_click)
        self.reject_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_timeout_label = W.label(self.confirm_actions_box, "", "mono")
        confirm_lay.addWidget(self.confirm_btn)
        confirm_lay.addWidget(self.reject_btn)
        confirm_lay.addWidget(self.confirm_timeout_label)
        confirm_lay.addWidget(W.spacer())
        self.confirm_actions_box.setLayout(confirm_lay)
        self.confirm_actions_box.setVisible(False)
        intent_layout.addWidget(self.confirm_actions_box)

        command_col.addWidget(intent_card)

        input_strip = W.hbox()
        self.manual_cmd_input = QLineEdit(self)
        self.manual_cmd_input.setClearButtonEnabled(True)
        self.manual_cmd_input.returnPressed.connect(self._on_manual_command)
        input_strip.addWidget(self.manual_cmd_input, 1)
        self.execute_btn = W.button(self, "", "primary", self._on_manual_command)
        self.execute_btn.setCursor(Qt.PointingHandCursor)
        input_strip.addWidget(self.execute_btn)
        command_col.addLayout(input_strip)

        log_header_layout = W.hbox(spacing=8)
        self.log_title_label = W.label(self, "", "sectionTitle")
        log_header_layout.addWidget(self.log_title_label)
        log_header_layout.addWidget(W.spacer())

        self.log_export_btn = W.button(self, "", "ghost", self._on_export_csv)
        self.log_export_btn.setCursor(Qt.PointingHandCursor)
        log_header_layout.addWidget(self.log_export_btn)

        self.log_clear_btn = W.button(self, "", "danger", self._on_clear_log)
        self.log_clear_btn.setCursor(Qt.PointingHandCursor)
        log_header_layout.addWidget(self.log_clear_btn)
        command_col.addLayout(log_header_layout)

        self.log_search_input = QLineEdit(self)
        self.log_search_input.setClearButtonEnabled(True)
        self.log_search_input.textChanged.connect(self._on_log_search_changed)
        command_col.addWidget(self.log_search_input)

        self.log_table = QTableWidget(self)
        self.log_table.setColumnCount(6)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setShowGrid(False)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.verticalHeader().setDefaultSectionSize(32)
        command_col.addWidget(self.log_table, 1)

        self.command_col_widget = QWidget(self)
        self.command_col_widget.setLayout(command_col)
        split.addWidget(self.command_col_widget, 2)
        return split

    def _build_action_bar(self) -> QWidget:
        card = W.frame(self, "card")
        lay = W.hbox(spacing=8, margins=(12, 11, 12, 11))

        self.action_buttons = {}
        for key, slot in (
            ("main.calibration", self.show_calibration),
            ("main.privacy", self.show_privacy_dashboard),
            ("main.accessibility", self.show_accessibility),
            ("main.keyboard", self.toggle_virtual_keyboard),
            ("main.macros", self.show_macros),
            ("main.demo", self.show_demo_mode),
        ):
            btn = W.button(card, "", "ghost", slot)
            btn.setCursor(Qt.PointingHandCursor)
            self.action_buttons[key] = btn
            lay.addWidget(btn)

        lay.addWidget(W.spacer())
        self.footer_hint = W.label(card, "", "faint")
        lay.addWidget(self.footer_hint)

        card.setLayout(lay)
        return card

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_selected(self, index: int):
        codes = i18n.available_languages()
        if not (0 <= index < len(codes)):
            return
        i18n.set_language(codes[index])
        try:
            self.speech_engine.set_language(codes[index])
        except Exception:
            pass

    def _on_language_changed(self, code: str):
        """Rebuilds the whole interface in the newly selected language."""
        theme.apply_to(self)
        self.retranslate()
        for component in (self.floating_hud, self.virtual_keyboard, self.tray, self.camera_widget):
            retranslate = getattr(component, "retranslate", None)
            if callable(retranslate):
                retranslate()
        self._refresh_event_log()

    def _cycle_language(self):
        codes = i18n.available_languages()
        cur = i18n.current_language()
        idx = codes.index(cur) if cur in codes else 0
        next_code = codes[(idx + 1) % len(codes)]
        i18n.set_language(next_code)
        try:
            self.speech_engine.set_language(next_code)
        except Exception:
            pass

    def _toggle_theme(self):
        theme.cycle_theme_mode()
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self._on_language_changed(i18n.current_language())

    def retranslate(self):
        """Applies every visible string in the active language."""
        self.setWindowTitle(tr("app.name"))

        self.brand_label.setText(tr("app.name"))
        self.subtitle_label.setText(tr("app.tagline"))
        self.offline_badge.setText("● " + tr("app.offline_first"))

        self.emergency_btn.setText(
            tr("main.emergency_restore")
            if self.security.is_emergency_stopped
            else tr("main.emergency_stop")
        )

        self.web_btn.setText(tr("main.web_companion"))
        self.auto_calib_btn.setText(tr("calib.auto_btn"))
        self.dock_title_label.setText(tr("main.dock_title"))
        for key, btn in self.dock_buttons:
            btn.setText(tr(key))

        self._refresh_switch(self.voice_pill, "main.voice", self.voice_enabled)
        self._refresh_switch(self.gesture_pill, "main.gesture", self.gesture_enabled)
        self._refresh_switch(self.vision_pill, "main.vision", self.vision_enabled)
        is_eco = (self.profile_mgr.current_profile == PerformanceProfile.ECO)
        self._refresh_switch(self.eco_pill, "main.eco_mode", is_eco)
        is_left = (self.settings.get("gestures.dominant_hand", "right") == "left")
        self.hand_pill.setText(
            f"✋ {tr('calib.dominant_hand')}: {tr('calib.hand_left') if is_left else tr('calib.hand_right')}"
        )
        self._refresh_switch(self.skeleton_toggle, "main.skeleton", self.skeleton_enabled)
        self._refresh_listening(self._listening)

        # View Switcher Button
        if hasattr(self, "view_switch_btn"):
            if getattr(self, "view_stack", None) and self.view_stack.currentIndex() == 0:
                self.view_switch_btn.setText(tr("main.view_native"))
            else:
                self.view_switch_btn.setText(tr("main.view_dashboard"))

        # Header Language Switch Button
        if hasattr(self, "header_lang_btn"):
            lang_names = {"ar": "🌐 العربية", "fr": "🌐 Français", "en": "🌐 English"}
            self.header_lang_btn.setText(lang_names.get(i18n.current_language(), "🌐 Langue"))

        # Compact mode button
        if hasattr(self, "compact_mode_btn"):
            self.compact_mode_btn.setText(
                tr("main.full_mode") if getattr(self, "is_compact_mode", False) else tr("main.compact_mode")
            )

        # Language selector
        self.language_label.setText(tr("common.language"))
        self.language_combo.setToolTip(tr("common.language"))
        codes = i18n.available_languages()
        if i18n.current_language() in codes:
            blocked = self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(codes.index(i18n.current_language()))
            self.language_combo.blockSignals(blocked)

        # Theme button
        if hasattr(self, "theme_btn"):
            if theme.is_high_contrast():
                self.theme_btn.setText(tr("main.theme_high_contrast"))
            elif theme.is_light_mode():
                self.theme_btn.setText(tr("main.theme_light"))
            else:
                self.theme_btn.setText(tr("main.theme_dark"))

        # Performance profile selector
        self.profile_label.setText(tr("main.profile"))
        profiles = list(PerformanceProfile)
        blocked = self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in profiles:
            self.profile_combo.addItem(tr_profile(profile.name), profile.name)
        self.profile_combo.setCurrentIndex(profiles.index(self.profile_mgr.current_profile))
        self.profile_combo.blockSignals(blocked)

        # Command card
        self.intent_title_label.setText(tr("main.cmd_title"))
        self.intent_title_label.setVisible(True)
        self.manual_cmd_input.setPlaceholderText(tr("main.cmd_input_hint"))
        self.execute_btn.setText(tr("common.execute"))

        # Audit log
        self.log_title_label.setText(tr("main.log_title"))
        self.log_export_btn.setText("📊  " + tr("log.export_csv"))
        self.log_clear_btn.setText("🗑️  " + tr("log.clear"))
        self.log_search_input.setPlaceholderText(tr("log.search_placeholder"))
        self.log_table.setHorizontalHeaderLabels([
            tr("col.time"), tr("col.command"), tr("col.intent"),
            tr("col.confidence"), tr("col.risk"), tr("col.result"),
        ])

        # Destructive Confirmation Action Box
        self.confirm_btn.setText(tr("security.confirm_btn"))
        self.reject_btn.setText(tr("security.cancel_btn"))
        if hasattr(self, "_confirm_seconds_remaining"):
            self.confirm_timeout_label.setText(
                tr("security.countdown", seconds=self._confirm_seconds_remaining)
            )

        self._refresh_privacy_badges()

        # Action bar
        for key, btn in self.action_buttons.items():
            btn.setText(tr(key))
        self.footer_hint.setText(tr("main.footer"))

        if not self._has_command:
            self._show_idle_command()

        self._refresh_profile_pill()

        # Telemetry holds formatted numbers, so it must be recomputed.
        self._update_telemetry()

    def _on_app_profile_changed(self, profile: str, app_name: str):
        self._current_profile = profile
        self._current_app_name = app_name
        self._refresh_profile_pill()

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
        self._refresh_profile_pill()

    def _refresh_profile_pill(self):
        if not hasattr(self, "app_profile_pill"):
            return
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
        self.app_profile_pill.setText(f"{icon} {translated_name} {lock_marker}".strip())
        self.app_profile_pill.setToolTip(f"{tr('profile.active_label', profile=translated_name)} ({self._current_app_name})")

    def _refresh_switch(self, btn: QPushButton, name_key: str, enabled: bool):
        btn.setText(
            tr("main.toggle", name=tr(name_key),
               state=tr("common.on") if enabled else tr("common.off"))
        )
        W.set_switch_state(btn, enabled)

    def _refresh_listening(self, listening: bool):
        self.listening_indicator.setText(
            tr("main.listening") if listening else tr("main.ready")
        )
        tone = theme.ACCENT if listening else theme.SUCCESS
        self.listening_indicator.setStyleSheet(
            f"color: {tone}; font-size: 13px; font-weight: 700; background: transparent;"
        )

    # ------------------------------------------------------------------ #
    # Event wiring
    # ------------------------------------------------------------------ #

    def _wire_events(self):
        # All cross-thread GUI updates route via QtBridge queued signals connected in __init__
        pass

    def _update_listening_state(self, is_listening: bool):
        self._listening = is_listening
        self._refresh_listening(is_listening)

    def _on_arm_state_changed(self, is_armed: bool):
        if getattr(self, "_last_armed_state", None) != is_armed:
            self._last_armed_state = is_armed
            self._refresh_switch(self.gesture_pill, "main.gesture", is_armed)

    def _on_gesture_diagnostics(
        self, gesture_name: str, diag_reason: str, confidence: float, is_armed: bool, progress: float
    ):
        arm_text = tr("arm.armed") if is_armed else tr("arm.disarmed")
        arm_badge = f"[{arm_text}]"

        if diag_reason.startswith("diag."):
            status_text = tr(diag_reason, progress=int(progress * 100))
        elif diag_reason:
            status_text = f"{tr_gesture(diag_reason)} ({int(confidence * 100)} %)"
        else:
            status_text = tr("main.ready")

        full_info = f"{arm_badge}  ·  {status_text}"
        if getattr(self, "_last_gesture_info", None) != full_info:
            self._last_gesture_info = full_info
            self.gesture_info_label.setText(full_info)
            if not is_armed:
                self.gesture_info_label.setStyleSheet(
                    f"color: {theme.WARNING}; font-weight: 600; font-size: 13px;"
                )
            elif "low_light" in diag_reason or "out_of_frame" in diag_reason:
                self.gesture_info_label.setStyleSheet(
                    f"color: {theme.DANGER}; font-weight: 600; font-size: 13px;"
                )
            else:
                self.gesture_info_label.setStyleSheet(
                    f"color: {theme.SUCCESS}; font-weight: 600; font-size: 13px;"
                )

        if hasattr(self, "floating_hud") and self.floating_hud:
            hud_text = f"{arm_badge} {status_text}"
            self.floating_hud.update_gesture(hud_text, confidence)

    def _on_frame_update(self, frame_bgr: np.ndarray, gesture_name: str, confidence: float):
        self.camera_widget.update_frame(frame_bgr, gesture_name, confidence)

    def _on_speech_command(self, cmd_text: str, latency_ms: float):
        self._run_command(cmd_text, source="VOICE", latency_ms=latency_ms)

    def _on_manual_command(self):
        text = self.manual_cmd_input.text().strip()
        if not text:
            return
        self._highlight_button(self.execute_btn)
        self.audio_effects.play_button_feedback()
        self.manual_cmd_input.clear()
        self._run_command(text, source="MANUAL")

    def _run_command(self, text: str, source: str, latency_ms: float = 0.0):
        """
        Executes a command off the GUI thread and reports the result back.

        The orchestrator blocks on pyautogui calls, screenshots and the local
        LLM's HTTP timeout. Running it inline on the Qt thread froze the whole
        window for the duration of every command, which is what users see as
        "the app hangs sometimes". The result returns through a queued signal
        so widgets are only ever touched from the GUI thread.
        """
        self._set_current_command(f'"{text}"')
        self._command_in_flight = True
        self._refresh_command_busy_state()

        def _worker():
            try:
                result = self.orchestrator.execute_command_text(
                    text, source=source, latency_ms=latency_ms
                )
            except Exception as e:
                result = {"action": "COMMAND_ERROR", "success": False, "reason": str(e)}
            self.qt_bridge.command_finished.emit(result)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_emergency_stop_during_command(self):
        """Re-enables the input if a halted command never reports back."""
        if self._command_in_flight:
            self._command_in_flight = False
            self._refresh_command_busy_state()

    def _on_command_finished(self, result: dict):
        """Runs on the GUI thread via the queued command_finished signal."""
        self._command_in_flight = False
        if hasattr(self, "_refresh_command_busy_state"):
            self._refresh_command_busy_state()
        if hasattr(self, "_update_command_details"):
            self._update_command_details(result)
        if hasattr(self, "_refresh_event_log"):
            self._refresh_event_log()

        if isinstance(result, dict):
            action = result.get("action") or result.get("intent") or tr("main.ready")
            if result.get("success", True) and result.get("status") != "AWAITING_CONFIRMATION":
                if hasattr(self, "audio_effects") and self.audio_effects:
                    try:
                        self.audio_effects.play_command_success()
                    except Exception:
                        pass
                if hasattr(self, "toast") and self.toast:
                    self.toast.show_message(
                        tr("toast.action_executed", action=tr_intent(str(action)) or str(action)),
                        icon="✓",
                        tone="success",
                    )
            elif not result.get("success", True):
                if hasattr(self, "toast") and self.toast:
                    self.toast.show_message(
                        result.get("reason", "Command failed"),
                        icon="⚠️",
                        tone="danger",
                    )

    def _refresh_command_busy_state(self):
        """Disables the input while a command runs so two never overlap."""
        if not hasattr(self, "manual_cmd_input"):
            return
        self.manual_cmd_input.setEnabled(not self._command_in_flight)

    def _update_command_details(self, res: dict):
        if not isinstance(res, dict):
            return
        action = res.get("action") or res.get("intent") or tr("main.intent_standby")
        risk = res.get("risk", "LOW")
        if res.get("status") == "AWAITING_CONFIRMATION":
            outcome = tr("risk.HIGH")
        elif res.get("success", True):
            outcome = tr_result("SUCCESS")
        else:
            outcome = tr_result("FAILED")
        self.intent_details_label.setText(
            tr("main.intent_line",
               intent=tr_intent(str(action)) or str(action),
               risk=tr_risk(str(risk)),
               result=outcome)
        )

    def _set_current_command(self, text: str):
        self._has_command = True
        self.current_cmd_label.setText(text)
        self.intent_details_label.setText(
            tr("main.intent_line", intent=tr("main.intent_standby"),
               risk=tr("risk.LOW"), result=tr("main.ready"))
        )

    def _show_idle_command(self):
        self._has_command = False
        self.current_cmd_label.setText(tr("main.cmd_idle"))
        self.intent_details_label.setText(
            tr("main.intent_line", intent=tr("main.intent_standby"),
               risk=tr("risk.LOW"), result=tr("main.ready"))
        )

    # ------------------------------------------------------------------ #
    # Audit log
    # ------------------------------------------------------------------ #

    def _refresh_event_log(self):
        events = self.logger.get_recent_events(limit=50)
        query = self.log_search_input.text().strip().lower() if hasattr(self, "log_search_input") else ""

        if query:
            filtered = []
            for ev in events:
                haystack = f"{ev.get('command', '')} {ev.get('intent', '')} {ev.get('gesture', '')} {ev.get('result', '')}".lower()
                if query in haystack:
                    filtered.append(ev)
            events = filtered

        self.log_table.setRowCount(len(events))

        for row, event in enumerate(events):
            risk = event.get("risk_level", "LOW")
            outcome = event.get("result", "SUCCESS")
            conf = event.get("confidence", 1.0)
            conf_str = f"{int(conf * 100)}%" if isinstance(conf, (int, float)) else str(conf)
            timestamp = str(event.get("timestamp", "")).split()
            cells = [
                timestamp[-1] if timestamp else "",
                event.get("command", ""),
                tr_intent(event.get("intent", "")) or tr("intent.UNKNOWN"),
                conf_str,
                tr_risk(risk).upper(),
                tr_result(outcome),
            ]

            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(QColor(theme.ACCENT))
                elif column == 4:
                    item.setForeground(
                        QColor(theme.DANGER) if risk in ("HIGH", "CRITICAL") else QColor(theme.SUCCESS)
                    )
                elif column == 5:
                    item.setForeground(
                        QColor(theme.SUCCESS) if outcome == "SUCCESS" else QColor(theme.DANGER)
                    )
                self.log_table.setItem(row, column, item)

    def _on_log_search_changed(self, _text: str):
        self._refresh_event_log()

    def _on_export_csv(self):
        self._highlight_button(self.log_export_btn)
        self.audio_effects.play_command_success()
        try:
            path = self.logger.export_csv()
            self.toast.show_message(tr("toast.csv_exported"), icon="📊", tone="success")
        except Exception as e:
            self.toast.show_message(f"Export error: {e}", icon="⚠️", tone="danger")

    def _highlight_button(self, btn: QPushButton):
        """Provides an animated glow effect on activated button for 600ms."""
        if not btn:
            return
        orig_style = btn.styleSheet()
        btn.setStyleSheet(f"background-color: {theme.ACCENT_GLOW}; border: 1.5px solid {theme.ACCENT}; color: #FFFFFF;")
        QTimer.singleShot(600, lambda: btn.setStyleSheet(orig_style))

    def _toggle_dominant_hand(self):
        current = self.settings.get("gestures.dominant_hand", "right")
        new_hand = "left" if current == "right" else "right"
        self.settings.set("gestures.dominant_hand", new_hand)
        self.retranslate()
        self._highlight_button(self.hand_pill)
        self.audio_effects.play_button_feedback()
        hand_name = tr("calib.hand_left") if new_hand == "left" else tr("calib.hand_right")
        self.toast.show_message(
            tr("toast.dominant_hand_changed", hand=hand_name),
            icon="✋",
            tone="info"
        )

    def toggle_compact_mode(self):
        """Toggles between standard full dashboard and sleek floating compact mode."""
        self.is_compact_mode = not self.is_compact_mode
        if self.is_compact_mode:
            self._normal_geometry = self.geometry()
            if hasattr(self, "command_col_widget"):
                self.command_col_widget.hide()
            if hasattr(self, "action_card"):
                self.action_card.hide()
            self.setMinimumSize(480, 360)
            self.resize(560, 420)
            self.compact_mode_btn.setText(tr("main.full_mode"))
            self.toast.show_message(tr("main.compact_mode"), icon="🗗", tone="info")
        else:
            if hasattr(self, "command_col_widget"):
                self.command_col_widget.show()
            if hasattr(self, "action_card"):
                self.action_card.show()
            self.setMinimumSize(1000, 680)
            if hasattr(self, "_normal_geometry") and self._normal_geometry:
                self.setGeometry(self._normal_geometry)
            else:
                self.resize(1180, 760)
            self.compact_mode_btn.setText(tr("main.compact_mode"))
            self.toast.show_message(tr("main.full_mode"), icon="🗖", tone="info")

    def _toggle_eco_mode(self):
        is_eco = (self.profile_mgr.current_profile == PerformanceProfile.ECO)
        new_prof = PerformanceProfile.BALANCED if is_eco else PerformanceProfile.ECO
        self.profile_mgr.set_profile(new_prof)
        self.retranslate()
        tone = "info" if new_prof == PerformanceProfile.ECO else "success"
        self.toast.show_message(
            f"{tr('main.eco_mode')}: {tr('common.on') if new_prof == PerformanceProfile.ECO else tr('common.off')}",
            icon="🌱",
            tone=tone
        )

    # ------------------------------------------------------------------ #
    # Telemetry & settings
    # ------------------------------------------------------------------ #

    def _update_telemetry(self):
        # Auto-eco throttle check
        throttled = self.profile_mgr.check_cpu_throttle()
        if throttled:
            self.toast.show_message(tr("toast.eco_activated"), icon="⚡", tone="warning")
            self.retranslate()

        stats = self.profile_mgr.get_system_stats()
        fps = stats["fps"]
        lat = stats["camera_latency_ms"]
        cpu = stats["cpu_percent"]
        ram = stats["ram_percent"]

        # Color badges: FPS >= 28 green, >= 18 orange, else red
        fps_color = "#10B981" if fps >= 28 else ("#F59E0B" if fps >= 18 else "#EF4444")
        lat_color = "#10B981" if lat <= 60 else ("#F59E0B" if lat <= 110 else "#EF4444")
        cpu_color = "#EF4444" if cpu >= 80 else ("#F59E0B" if cpu >= 60 else theme.TEXT_FAINT)

        self.telemetry_label.setText(
            f'CPU <b style="color:{cpu_color};">{cpu}%</b> &nbsp;·&nbsp; '
            f'RAM <b>{ram}%</b> &nbsp;·&nbsp; '
            f'<b style="color:{fps_color};">{fps} FPS</b> &nbsp;·&nbsp; '
            f'<b style="color:{lat_color};">{lat} ms</b>'
        )

    def _on_profile_changed(self, index: int):
        code = self.profile_combo.itemData(index)
        if not code:
            return
        try:
            self.profile_mgr.set_profile(PerformanceProfile[code])
        except Exception:
            pass

    def _toggle_skeleton(self):
        self.skeleton_enabled = not self.skeleton_enabled
        self.settings.set("gestures.show_hand_skeleton", self.skeleton_enabled)
        self._refresh_switch(self.skeleton_toggle, "main.skeleton", self.skeleton_enabled)

    def toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        self.speech_engine.listener.set_mic_enabled(self.voice_enabled)
        self._refresh_switch(self.voice_pill, "main.voice", self.voice_enabled)
        self._refresh_privacy_badges()
        self._refresh_tray()

    def toggle_gesture(self):
        self.gesture_enabled = not self.gesture_enabled
        self.camera_stream.cursor_control_active = self.gesture_enabled
        self._refresh_switch(self.gesture_pill, "main.gesture", self.gesture_enabled)
        self._refresh_tray()

    def toggle_vision(self):
        self.vision_enabled = not self.vision_enabled
        self.camera_stream.set_camera_enabled(self.vision_enabled)
        self._refresh_switch(self.vision_pill, "main.vision", self.vision_enabled)
        if not self.vision_enabled:
            self.camera_widget.set_camera_off()
        self._refresh_privacy_badges()
        self._refresh_tray()

    def _refresh_tray(self):
        if getattr(self, "tray", None) is not None:
            self.tray.retranslate()

    def trigger_emergency_stop(self):
        if self.security.is_emergency_stopped:
            self.security.reset_emergency_stop()
        else:
            self.security.trigger_emergency_stop("USER_CLICKED_STOP")
        self._refresh_tray()

    def _handle_emergency_stop_event(self, reason: str = ""):
        """Single source of truth for the halt/restore UI state.

        Driven by the QtBridge signal, which SecurityEngine emits from both
        trigger_emergency_stop and reset_emergency_stop, so the labels, the
        button and the audit view can never disagree with the engine.
        """
        stopped = self.security.is_emergency_stopped
        self._has_command = True
        # Any pending confirmation is moot once the engine is halted, and the
        # cleared signal will never arrive for it, so drop it explicitly.
        self._security_prompt_active = False
        self._on_emergency_stop_during_command()
        if stopped:
            self.current_cmd_label.setText(tr("main.emergency_active"))
            self.intent_details_label.setText(tr("main.emergency_halted"))
            self.camera_stream._release_drag_if_needed()
            self.camera_stream.set_armed(False)
            self.camera_stream.set_camera_enabled(False)
            self.speech_engine.listener.set_mic_enabled(False)
            self._refresh_switch(self.vision_pill, "main.vision", False)
            self._refresh_switch(self.voice_pill, "main.voice", False)
            self._refresh_switch(self.gesture_pill, "main.gesture", False)
        else:
            self.current_cmd_label.setText(tr("main.status_ready"))
            self.intent_details_label.setText(tr("main.ready_desc"))
            self.camera_stream.set_camera_enabled(True)
            self.speech_engine.listener.set_mic_enabled(True)
            self.camera_stream.cursor_control_active = True
            self._refresh_switch(self.vision_pill, "main.vision", True)
            self._refresh_switch(self.voice_pill, "main.voice", True)
            self._refresh_switch(self.gesture_pill, "main.gesture", True)
        self.emergency_btn.setText(
            tr("main.emergency_restore") if stopped else tr("main.emergency_stop")
        )
        self._refresh_tray()
        self._refresh_event_log()

    def _show_security_prompt(self, data: dict):
        self._has_command = True
        self._security_prompt_active = True

        intent = data.get("intent", "")
        cmd = data.get("command", "")
        risk = data.get("risk", "HIGH")
        timeout = float(data.get("timeout", 5.0))

        # Warning chime
        try:
            self.audio_effects.play_command_failed()
        except Exception:
            pass

        # Targeted destructive prompt text
        if intent in ("DELETE_FILE", "DELETE_FOLDER"):
            prompt_title = tr("security.prompt_delete", target=cmd)
        elif intent == "EMPTY_RECYCLE_BIN":
            prompt_title = tr("security.prompt_empty_bin")
        elif intent == "SYSTEM_SHUTDOWN":
            prompt_title = tr("security.prompt_shutdown")
        elif intent == "SYSTEM_RESTART":
            prompt_title = tr("security.prompt_restart")
        elif intent == "CLOSE_WINDOW":
            prompt_title = tr("security.prompt_close")
        else:
            prompt_title = tr("main.security_confirm", command=cmd)

        self.current_cmd_label.setText("⚠️ " + prompt_title)
        self.intent_details_label.setText(
            tr("main.security_hint", risk=tr_risk(risk), yes=tr("common.yes"))
        )

        # Action buttons & live countdown
        self.confirm_btn.setText(tr("security.confirm_btn"))
        self.reject_btn.setText(tr("security.cancel_btn"))
        self._confirm_seconds_remaining = int(timeout)
        self.confirm_timeout_label.setText(
            tr("security.countdown", seconds=self._confirm_seconds_remaining)
        )
        self.confirm_actions_box.setVisible(True)
        self._confirm_timer.start(1000)

    def _on_confirm_timer_tick(self):
        self._confirm_seconds_remaining -= 1
        if self._confirm_seconds_remaining > 0:
            self.confirm_timeout_label.setText(
                tr("security.countdown", seconds=self._confirm_seconds_remaining)
            )
        else:
            self._confirm_timer.stop()
            self.confirm_actions_box.setVisible(False)
            self.security.cancel_pending("TIMEOUT")

    def _on_confirm_click(self):
        self._confirm_timer.stop()
        self.confirm_actions_box.setVisible(False)
        try:
            self.audio_effects.play_command_success()
        except Exception:
            pass
        self.security.confirm_pending("BUTTON")
        self.toast.show_message(
            tr("toast.action_executed", action=tr("security.confirm_btn")),
            icon="✔",
            tone="success",
        )

    def _on_reject_click(self):
        self._confirm_timer.stop()
        self.confirm_actions_box.setVisible(False)
        self.security.cancel_pending("USER_CLICK")
        self.toast.show_message(tr("security.cancel_btn"), icon="✖", tone="warning")

    def _clear_security_prompt(self, reason: str = "") -> None:
        """Removes the confirmation banner once the prompt is resolved."""
        self._confirm_timer.stop()
        if hasattr(self, "confirm_actions_box"):
            self.confirm_actions_box.setVisible(False)
        if not getattr(self, "_security_prompt_active", False):
            return
        self._security_prompt_active = False
        if reason == "CONFIRMED":
            self._show_idle_command()
        else:
            self.current_cmd_label.setText(tr("main.cmd_idle"))
            self.intent_details_label.setText(tr("main.ready_desc"))
            self._has_command = False

    def toggle_privacy_mode(self):
        """1-Click Privacy Kill Switch: instantly cuts or restores both camera and microphone."""
        self.privacy_mode_active = not getattr(self, "privacy_mode_active", False)
        if self.privacy_mode_active:
            # Cut camera completely
            self.camera_stream.set_camera_enabled(False)
            self.camera_widget.set_camera_off()
            # Cut microphone
            self.speech_engine.listener.set_mic_enabled(False)
            # Cut cursor control gestures
            self.camera_stream.cursor_control_active = False
            # Update switches
            self._refresh_switch(self.vision_pill, "main.vision", False)
            self._refresh_switch(self.voice_pill, "main.voice", False)
            self._refresh_switch(self.gesture_pill, "main.gesture", False)
            # Sound & Toast
            try:
                self.audio_effects.play_command_failed()
            except Exception:
                pass
            self.toast.show_message(tr("toast.privacy_mode_activated"), icon="🛡️", tone="warning")
        else:
            # Restore to previous user toggles
            self.camera_stream.set_camera_enabled(self.vision_enabled)
            self.speech_engine.listener.set_mic_enabled(self.voice_enabled)
            self.camera_stream.cursor_control_active = self.gesture_enabled
            self._refresh_switch(self.vision_pill, "main.vision", self.vision_enabled)
            self._refresh_switch(self.voice_pill, "main.voice", self.voice_enabled)
            self._refresh_switch(self.gesture_pill, "main.gesture", self.gesture_enabled)
            try:
                self.audio_effects.play_command_success()
            except Exception:
                pass
            self.toast.show_message(tr("toast.privacy_mode_deactivated"), icon="🛡️", tone="success")

        self._refresh_privacy_badges()
        self._refresh_tray()

    def _refresh_privacy_badges(self):
        if not hasattr(self, "cam_privacy_badge") or not hasattr(self, "mic_privacy_badge"):
            return

        is_privacy = getattr(self, "privacy_mode_active", False)

        # Cam status
        cam_on = (
            not is_privacy
            and getattr(self, "vision_enabled", True)
            and getattr(self.camera_stream, "_camera_enabled", True)
        )
        if cam_on:
            self.cam_privacy_badge.setText(tr("privacy.cam_on"))
            self.cam_privacy_badge.setStyleSheet(
                f"background-color: {theme.SUCCESS}22; color: {theme.SUCCESS}; font-weight: 700; border-radius: 4px; padding: 2px 7px; font-size: 11px;"
            )
        else:
            self.cam_privacy_badge.setText(tr("privacy.cam_off"))
            self.cam_privacy_badge.setStyleSheet(
                f"background-color: {theme.DANGER}22; color: {theme.DANGER}; font-weight: 700; border-radius: 4px; padding: 2px 7px; font-size: 11px;"
            )

        # Mic status
        mic_on = (
            not is_privacy
            and getattr(self, "voice_enabled", True)
            and getattr(self.speech_engine.listener, "_mic_enabled", True)
        )
        if mic_on:
            self.mic_privacy_badge.setText(tr("privacy.mic_on"))
            self.mic_privacy_badge.setStyleSheet(
                f"background-color: {theme.SUCCESS}22; color: {theme.SUCCESS}; font-weight: 700; border-radius: 4px; padding: 2px 7px; font-size: 11px;"
            )
        else:
            self.mic_privacy_badge.setText(tr("privacy.mic_off"))
            self.mic_privacy_badge.setStyleSheet(
                f"background-color: {theme.DANGER}22; color: {theme.DANGER}; font-weight: 700; border-radius: 4px; padding: 2px 7px; font-size: 11px;"
            )

        # Kill switch button
        if hasattr(self, "privacy_kill_switch_btn"):
            if is_privacy:
                self.privacy_kill_switch_btn.setText(tr("privacy.mode_active"))
                self.privacy_kill_switch_btn.setStyleSheet(
                    f"background-color: {theme.DANGER}; color: #FFFFFF; font-weight: 700; border-radius: 6px; padding: 4px 10px; border: 1px solid #FF0000; font-size: 11px;"
                )
            else:
                self.privacy_kill_switch_btn.setText("🛡️ " + tr("privacy.mode"))
                self.privacy_kill_switch_btn.setStyleSheet(
                    f"background-color: {theme.CANVAS_DEEP}; color: {theme.TEXT_MUTED}; font-weight: 700; border-radius: 6px; padding: 4px 10px; border: 1px solid {theme.BORDER}; font-size: 11px;"
                )

    def _on_clear_log(self):
        reply = QMessageBox.question(
            self,
            tr("log.clear_confirm_title"),
            tr("log.clear_confirm_msg"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logger.clear()
            self._refresh_event_log()
            self.toast.show_message(tr("toast.log_cleared"), icon="🗑️", tone="success")
            try:
                self.audio_effects.play_command_success()
            except Exception:
                pass

    def toggle_virtual_keyboard(self):
        if self.virtual_keyboard.isVisible():
            self.virtual_keyboard.hide()
            return
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            self.virtual_keyboard.move(
                (geo.width() - self.virtual_keyboard.width()) // 2,
                geo.height() - self.virtual_keyboard.height() - 60,
            )
        self.virtual_keyboard.show()

    # ------------------------------------------------------------------ #
    # Dialog openers
    # ------------------------------------------------------------------ #

    def show_calibration(self):
        CalibrationWizardDialog(self).exec()

    def show_privacy_dashboard(self):
        PrivacyDashboardDialog(self).exec()

    def show_accessibility(self):
        AccessibilityDialog(self).exec()

    def show_macros(self):
        MacroManagerDialog(self).exec()

    def show_demo_mode(self):
        DemoModeDialog(self).exec()

    # ------------------------------------------------------------------ #
    # Auto-Calibration & Total PC Control Actions
    # ------------------------------------------------------------------ #

    def _take_screenshot_action(self):
        """
        Captures the screen on a worker thread with audio chime and toast notification.
        """
        self.audio_effects.play_screenshot_chime()
        self.toast.show_message(tr("toast.screenshot_saved"), icon="📸", tone="success")

        def _worker():
            try:
                path = self.orchestrator.win_control.take_screenshot()
                QTimer.singleShot(
                    0,
                    lambda: self.intent_details_label.setText(
                        tr("shot.saved_at", path=path)
                    ),
                )
                QTimer.singleShot(0, lambda: self.current_cmd_label.setText(tr("shot.saved")))
            except Exception as e:
                QTimer.singleShot(
                    0,
                    lambda: self.intent_details_label.setText(tr("shot.failed", error=e)),
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_quick_auto_calibration(self):
        self.auto_calib_btn.setEnabled(False)
        self.auto_calib_btn.setText(tr("calib.auto_running"))
        self.current_cmd_label.setText(tr("calib.auto_start"))
        self.intent_details_label.setText(tr("calib.auto_detail"))
        
        # Ensure UI updates before running calibration
        QApplication.processEvents()

        try:
            from core.auto_calibration import perform_one_click_auto_calibration
            res = perform_one_click_auto_calibration()
            self._on_auto_calib_finished(res)
        except Exception as e:
            self._on_auto_calib_finished({"success": False, "error": str(e)})

    def _on_auto_calib_finished(self, res: dict):
        self.auto_calib_btn.setEnabled(True)
        self.auto_calib_btn.setText(tr("calib.auto_btn"))
        if res.get("success"):
            self.current_cmd_label.setText(
                tr("calib.auto_done", score=res.get("quality_score", 98))
            )
            self.intent_details_label.setText(tr(
                "calib.auto_values",
                fps=res.get("fps", 30),
                pinch=res.get("pinch_threshold", 0.045),
                smoothing=res.get("smoothing_factor", 0.45),
                speed=res.get("cursor_speed", 1.6),
            ))
            try:
                self.speech_engine.audio_effects.play_command_success()
            except Exception:
                pass
        else:
            self.current_cmd_label.setText(tr("calib.auto_failed"))
            self.intent_details_label.setText(str(res.get("error", "")))

    def toggle_view_mode(self):
        if not hasattr(self, "view_stack") or getattr(self, "web_view", None) is None:
            return
        if self.view_stack.currentIndex() == 0:
            self.view_stack.setCurrentIndex(1)
            self.view_switch_btn.setText(tr("main.view_dashboard"))
            self.toast.show_message(tr("main.view_native_toast"), icon="📷", tone="info")
        else:
            self.view_stack.setCurrentIndex(0)
            self.view_switch_btn.setText(tr("main.view_native"))
            self.toast.show_message(tr("main.view_dashboard_toast"), icon="🌐", tone="info")

    def _open_web_companion(self):
        if hasattr(self, "web_view") and self.web_view:
            self.view_stack.setCurrentIndex(0)
            self.web_view.reload()
            self.view_switch_btn.setText(tr("main.view_native"))
            self.toast.show_message(tr("main.view_dashboard_toast"), icon="🔄", tone="info")
        else:
            import webbrowser
            webbrowser.open("http://127.0.0.1:8000")

    # ------------------------------------------------------------------ #
    # Shutdown
    # ------------------------------------------------------------------ #

    def close_app_completely(self):
        if hasattr(self, "global_hotkey") and self.global_hotkey:
            self.global_hotkey.stop()
        self.camera_stream.stop()
        self.app_profile_mgr.stop()
        self.speech_engine.listener.stop()
        self.speech_engine.tts.stop()
        self.companion_server.stop()
        stop_background_server()
        # Writes are coalesced, so the pending settings change has to be forced
        # out here or the last adjustment before exit is lost.
        self.settings.flush()
        self.floating_hud.close()
        self.cursor_overlay.close()
        self.virtual_keyboard.close()
        self.tray.hide()
        sys.exit(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._reposition()

    def closeEvent(self, event):
        if self.settings.get("system.minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.showMessage(
                tr("main.minimized_title"),
                tr("main.minimized_body"),
                HadjSystemTray.Information,
                2200,
            )
        else:
            self.close_app_completely()
