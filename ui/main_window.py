import sys

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

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

import config.i18n as i18n
from config.i18n import tr, tr_gesture, tr_intent, tr_profile, tr_result, tr_risk
from core.event_bus import EventBus, EventType
from core.profile_manager import ProfileManager, PerformanceProfile
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

        # QtBridge for rock-solid thread-safe cross-thread signal delivery
        self.qt_bridge = QtBridge()

        # Transient UI state
        self.voice_enabled = True
        self.gesture_enabled = True
        self.vision_enabled = True
        self.skeleton_enabled = bool(self.settings.get("gestures.show_hand_skeleton", True))
        self._listening = False
        self._has_command = False

        # HUD overlays
        self.floating_hud = FloatingOverlayHUD()
        self.floating_hud.show()
        self.cursor_overlay = VirtualCursorOverlay()
        self.cursor_overlay.show()
        self.virtual_keyboard = VirtualKeyboardHUD()

        # Connect thread-safe QtBridge signals directly to GUI slots
        self.qt_bridge.frame_ready.connect(self._on_frame_update)
        self.qt_bridge.cursor_moved.connect(self.cursor_overlay.update_position)
        self.qt_bridge.gesture_detected.connect(self.floating_hud.update_gesture)
        self.qt_bridge.speech_state.connect(self._update_listening_state)
        self.qt_bridge.speech_command.connect(self._on_speech_command)
        self.qt_bridge.emergency_stop.connect(self._handle_emergency_stop_event)
        self.qt_bridge.security_prompt.connect(self._show_security_prompt)

        theme.apply_to(self)
        self._init_ui()

        # System tray (built after the UI so it can share the translated labels)
        self.tray = HadjSystemTray(self)
        self.tray.show()

        self._wire_events()
        i18n.on_language_changed(self._on_language_changed)

        # Start background workers
        self.camera_stream.start()
        self.speech_engine.start()
        self.companion_server.start()

        # Telemetry timer (updates CPU, RAM, FPS every second)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_telemetry)
        self.telemetry_timer.start(1000)

        self.retranslate()
        self._update_telemetry()

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
        root.addLayout(self._build_sensor_bar())
        root.addWidget(self._build_pc_control_dock())
        root.addLayout(self._build_workspace(), 1)
        root.addWidget(self._build_action_bar())

    def _build_header(self) -> QWidget:
        card = W.frame(self, "card")
        lay = W.hbox(margins=(theme.PAD - 6, 12, theme.PAD - 6, 12))

        identity = QVBoxLayout()
        identity.setSpacing(3)
        self.brand_label = W.label(card, "", "brandTitle")
        self.subtitle_label = W.label(card, "", "brandSubtitle")
        identity.addWidget(self.brand_label)
        identity.addWidget(self.subtitle_label)
        lay.addLayout(identity)

        lay.addWidget(W.spacer())

        self.offline_badge = W.label(card, "", "badgeSuccess")
        lay.addWidget(self.offline_badge)

        self.auto_calib_btn = QPushButton("⚡ Calibrage Auto", card)
        self.auto_calib_btn.setObjectName("calibAuto")
        self.auto_calib_btn.setCursor(Qt.PointingHandCursor)
        self.auto_calib_btn.clicked.connect(self._on_quick_auto_calibration)
        lay.addWidget(self.auto_calib_btn)

        self.web_btn = QPushButton("🌐 Web Companion", card)
        self.web_btn.setObjectName("companionBtn")
        self.web_btn.setCursor(Qt.PointingHandCursor)
        self.web_btn.clicked.connect(self._open_web_companion)
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

        dock_title = W.label(card, "🎮 CONTRÔLE TOTAL DU PC :", "sectionTitle")
        lay.addWidget(dock_title)

        dock_actions = [
            ("🖥️ Bureau", lambda: self.orchestrator.win_control.show_desktop()),
            ("📑 Tâches", lambda: self.orchestrator.win_control.open_task_view()),
            ("🗔 Ancrer G", lambda: self.orchestrator.win_control.snap_window_left()),
            ("🗖 Ancrer D", lambda: self.orchestrator.win_control.snap_window_right()),
            ("📸 Capture", self._take_screenshot_action),
            ("🔊 Vol +", lambda: self.orchestrator.win_control.volume_up()),
            ("🔉 Vol -", lambda: self.orchestrator.win_control.volume_down()),
            ("🔇 Muet", lambda: self.orchestrator.win_control.volume_mute()),
            ("⌨️ Clavier", self.toggle_virtual_keyboard),
            ("🔒 Verrouiller", lambda: self.orchestrator.win_control.lock_pc()),
            ("⚡ TaskMgr", lambda: self.orchestrator.win_control.open_task_manager()),
        ]

        for label, fn in dock_actions:
            btn = QPushButton(label, card)
            btn.setObjectName("quickAction")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(fn)
            lay.addWidget(btn)

        lay.addWidget(W.spacer())
        card.setLayout(lay)
        return card

    def _build_sensor_bar(self) -> QHBoxLayout:
        lay = W.hbox(spacing=10)

        self.voice_pill = W.switch_button(self, "", self.toggle_voice)
        self.gesture_pill = W.switch_button(self, "", self.toggle_gesture)
        self.vision_pill = W.switch_button(self, "", self.toggle_vision)
        for pill in (self.voice_pill, self.gesture_pill, self.vision_pill):
            lay.addWidget(pill)

        lay.addWidget(W.separator())
        self.listening_indicator = W.label(self, "", "metric")
        lay.addWidget(self.listening_indicator)

        lay.addWidget(W.spacer())

        self.language_label = W.label(self, "", "faint")
        lay.addWidget(self.language_label)

        self.language_combo = QComboBox(self)
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
        self.profile_combo.setCursor(Qt.PointingHandCursor)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        lay.addWidget(self.profile_combo)

        self.telemetry_label = W.label(self, "", "mono")
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

        self.log_title_label = W.label(self, "", "sectionTitle")
        command_col.addWidget(self.log_title_label)

        self.log_table = QTableWidget(self)
        self.log_table.setColumnCount(5)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setShowGrid(False)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.verticalHeader().setDefaultSectionSize(32)
        command_col.addWidget(self.log_table, 1)

        split.addLayout(command_col, 2)
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

        self._refresh_switch(self.voice_pill, "main.voice", self.voice_enabled)
        self._refresh_switch(self.gesture_pill, "main.gesture", self.gesture_enabled)
        self._refresh_switch(self.vision_pill, "main.vision", self.vision_enabled)
        self._refresh_switch(self.skeleton_toggle, "main.skeleton", self.skeleton_enabled)
        self._refresh_listening(self._listening)

        # Language selector
        self.language_label.setText(tr("common.language"))
        self.language_combo.setToolTip(tr("common.language"))
        codes = i18n.available_languages()
        if i18n.current_language() in codes:
            blocked = self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(codes.index(i18n.current_language()))
            self.language_combo.blockSignals(blocked)

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
        self.log_table.setHorizontalHeaderLabels([
            tr("col.time"), tr("col.command"), tr("col.intent"),
            tr("col.risk"), tr("col.result"),
        ])

        # Action bar
        for key, btn in self.action_buttons.items():
            btn.setText(tr(key))
        self.footer_hint.setText(tr("main.footer"))

        if not self._has_command:
            self._show_idle_command()

        # Telemetry holds formatted numbers, so it must be recomputed.
        self._update_telemetry()

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
        self.event_bus.subscribe(EventType.SPEECH_LISTENING_START, lambda _: self._update_listening_state(True))
        self.event_bus.subscribe(EventType.SPEECH_LISTENING_END, lambda _: self._update_listening_state(False))
        self.event_bus.subscribe(EventType.EMERGENCY_STOP, self._handle_emergency_stop_event)
        self.event_bus.subscribe(EventType.SECURITY_CONFIRM_REQUEST, self._show_security_prompt)

    def _update_listening_state(self, is_listening: bool):
        self._listening = is_listening
        self._refresh_listening(is_listening)

    def _on_frame_update(self, frame_bgr: np.ndarray, gesture_name: str, confidence: float):
        self.camera_widget.update_frame(frame_bgr, gesture_name, confidence)
        self.gesture_info_label.setText(
            tr("main.gesture_info",
               gesture=tr_gesture(gesture_name),
               conf=int(confidence * 100))
        )

    def _on_speech_command(self, cmd_text: str, latency_ms: float):
        self._set_current_command(f'"{cmd_text}"')
        res = self.orchestrator.execute_command_text(cmd_text, source="VOICE", latency_ms=latency_ms)
        self._update_command_details(res)
        self._refresh_event_log()

    def _on_manual_command(self):
        text = self.manual_cmd_input.text().strip()
        if not text:
            return
        self.manual_cmd_input.clear()
        self._set_current_command(f'"{text}"')
        res = self.orchestrator.execute_command_text(text, source="MANUAL")
        self._update_command_details(res)
        self._refresh_event_log()

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
        events = self.logger.get_recent_events(limit=15)
        self.log_table.setRowCount(len(events))

        for row, event in enumerate(events):
            risk = event.get("risk_level", "LOW")
            outcome = event.get("result", "SUCCESS")
            timestamp = str(event.get("timestamp", "")).split()
            cells = [
                timestamp[-1] if timestamp else "",
                event.get("command", ""),
                tr_intent(event.get("intent", "")) or tr("intent.UNKNOWN"),
                tr_risk(risk).upper(),
                tr_result(outcome),
            ]

            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(
                        QColor(theme.DANGER) if risk in ("HIGH", "CRITICAL") else QColor(theme.SUCCESS)
                    )
                elif column == 4:
                    item.setForeground(
                        QColor(theme.SUCCESS) if outcome == "SUCCESS" else QColor(theme.DANGER)
                    )
                self.log_table.setItem(row, column, item)

    # ------------------------------------------------------------------ #
    # Telemetry & settings
    # ------------------------------------------------------------------ #

    def _update_telemetry(self):
        stats = self.profile_mgr.get_system_stats()
        self.telemetry_label.setText(
            tr("main.telemetry",
               cpu=stats["cpu_percent"],
               ram=stats["ram_percent"],
               fps=stats["fps"],
               latency=stats["camera_latency_ms"])
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

    def _refresh_tray(self):
        if getattr(self, "tray", None) is not None:
            self.tray.retranslate()

    def trigger_emergency_stop(self):
        if self.security.is_emergency_stopped:
            self.security.reset_emergency_stop()
        else:
            self.security.trigger_emergency_stop("USER_CLICKED_STOP")
        self.emergency_btn.setText(
            tr("main.emergency_restore")
            if self.security.is_emergency_stopped
            else tr("main.emergency_stop")
        )
        self._refresh_tray()

    def _handle_emergency_stop_event(self, data):
        self._has_command = True
        self.current_cmd_label.setText(tr("main.emergency_active"))
        self.intent_details_label.setText(tr("main.emergency_halted"))

    def _show_security_prompt(self, data):
        self._has_command = True
        self.current_cmd_label.setText(
            tr("main.security_confirm", command=data.get("command", ""))
        )
        self.intent_details_label.setText(
            tr("main.security_hint",
               risk=tr_risk(data.get("risk", "")),
               yes=tr("common.yes"))
        )

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
        try:
            path = self.orchestrator.win_control.take_screenshot()
            self.current_cmd_label.setText("📸 Capture d'écran enregistrée")
            self.intent_details_label.setText(f"Enregistré: {path}")
        except Exception as e:
            self.intent_details_label.setText(f"Erreur capture: {e}")

    def _on_quick_auto_calibration(self):
        self.auto_calib_btn.setEnabled(False)
        self.auto_calib_btn.setText("⚡ Analyse en cours...")
        self.current_cmd_label.setText("⚡ Calibrage automatique en cours...")
        self.intent_details_label.setText("Mesure caméra, FPS, bruit ambiant et calcul des seuils optimaux...")

        def _run():
            try:
                from core.auto_calibration import perform_one_click_auto_calibration
                res = perform_one_click_auto_calibration()
                QTimer.singleShot(0, lambda: self._on_auto_calib_finished(res))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_auto_calib_finished({"success": False, "error": str(e)}))

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _on_auto_calib_finished(self, res: dict):
        self.auto_calib_btn.setEnabled(True)
        self.auto_calib_btn.setText("⚡ Calibrage Auto")
        if res.get("success"):
            fps = res.get("fps", 30)
            pinch = res.get("pinch_threshold", 0.045)
            smooth = res.get("smoothing_factor", 0.45)
            speed = res.get("cursor_speed", 1.6)
            score = res.get("quality_score", 98)
            self.current_cmd_label.setText(f"✅ Calibrage Auto Réussi (Score {score}%)")
            self.intent_details_label.setText(f"Caméra: {fps} FPS | Seuil Pince: {pinch} | Lissage: {smooth} | Vitesse: {speed}")
            try:
                self.speech_engine.audio_effects.play_command_success()
            except Exception:
                pass
        else:
            self.current_cmd_label.setText("⚠️ Erreur Calibrage Auto")
            self.intent_details_label.setText(str(res.get("error", "Échec")))

    def _open_web_companion(self):
        import webbrowser
        import urllib.request
        import subprocess
        import os

        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=0.4)
        except Exception:
            web_srv = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web_server.py")
            if os.path.exists(web_srv):
                subprocess.Popen([sys.executable, web_srv], cwd=os.path.dirname(os.path.dirname(__file__)))

        webbrowser.open("http://127.0.0.1:8000")

    # ------------------------------------------------------------------ #
    # Shutdown
    # ------------------------------------------------------------------ #

    def close_app_completely(self):
        self.camera_stream.stop()
        self.speech_engine.listener.stop()
        self.speech_engine.tts.stop()
        self.companion_server.stop()
        self.floating_hud.close()
        self.cursor_overlay.close()
        self.virtual_keyboard.close()
        self.tray.hide()
        sys.exit(0)

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
