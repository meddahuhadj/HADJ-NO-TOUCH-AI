"""Main dashboard UI (Windows-11 style, dark)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QComboBox, QFrame, QListWidget, QSplitter, QScrollArea,
)

from ..core.status import StatusSnapshot
from .widgets import StatusDot, StatCard

DARK = """
QWidget { background: #0b1622; color: #eaf3ff; }
QPushButton { background: #17335a; color: #eaf3ff; border: 1px solid #2a4a74;
              border-radius: 8px; padding: 8px 12px; font-weight: bold; }
QPushButton:hover { background: #1f416e; }
QPushButton:disabled { background: #22303f; color: #5f7ea0; }
QPushButton#danger { background: #8f1f1f; border-color: #b33636; }
QPushButton#danger:hover { background: #aa2a2a; }
QPushButton#ok { background: #1f6f43; border-color: #2d9d5e; }
QComboBox { background: #132940; color: #eaf3ff; border: 1px solid #2a4a74;
            border-radius: 6px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #132940; color: #eaf3ff; }
QListWidget { background: #0e1e30; border: 1px solid #223d5c; border-radius: 8px; }
QListWidget::item { padding: 2px; }
QScrollArea { border: none; }
"""


class Dashboard(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setStyleSheet(DARK)
        self._titles = {
            "personal": "👤 Personal", "presentation": "📊 Presentation",
            "media": "🎬 Media", "industrial": "⚙️ Industrial",
            "medical": "🏥 Medical", "accessibility": "♿ Accessibility",
            "kiosk": "📟 Kiosk", "browser": "🌐 Browser", "cad": "📐 CAD",
            "pdf": "📄 PDF", "hands_busy": "🧤 Hands Busy",
            "copilot": "🤖 AI Copilot", "custom": "✨ Custom",
        }
        self._last_history_count = -1
        self._build()

    # ---- construction -------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("HADJ NO-TOUCH AI")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #7cc3ff;")
        tagline = QLabel("Multimodal contactless control — hands, voice & eyes")
        tagline.setStyleSheet("color: #5f7ea0; font-size: 12px;")
        self.demo_badge = QLabel("🔴 REAL")
        self.demo_badge.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #ff6b6b; background: #2a1515;"
            "border: 1px solid #b33636; border-radius: 8px; padding: 3px 10px;")
        self.audio_badge = QLabel("🎙 —")
        self.audio_badge.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #8a8a9a; background: #191922;"
            "border: 1px solid #44445a; border-radius: 8px; padding: 3px 10px;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.audio_badge)
        header.addWidget(self.demo_badge)
        header.addWidget(tagline)
        root.addLayout(header)

        split = QSplitter(Qt.Orientation.Horizontal)

        # LEFT: camera + gesture
        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel("Camera preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(400, 300)
        self.preview.setStyleSheet(
            "background: #080f19; border: 1px solid #223d5c; border-radius: 10px; color:#5f7ea0;")
        llay.addWidget(self.preview, stretch=3)

        self.gesture_big = QLabel("—")
        self.gesture_big.setStyleSheet("font-size: 30px; font-weight: bold; color: #ffe08a;")
        self.gesture_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        llay.addWidget(self.gesture_big)

        self.action_label = QLabel("Waiting for a gesture…")
        self.action_label.setStyleSheet("color: #9fc7e8; font-size: 14px;")
        self.action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        llay.addWidget(self.action_label)

        self.voice_label = QLabel("🎤 —")
        self.voice_label.setStyleSheet("color: #b7a5e0; font-size: 13px;")
        self.voice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        llay.addWidget(self.voice_label)
        left.setLayout(llay)
        split.addWidget(left)

        # RIGHT: status + controls
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(8)

        # status dots
        dotbox = QFrame()
        dotbox.setStyleSheet("background:#12263d; border:1px solid #223d5c; border-radius:10px;")
        dlay = QGridLayout(dotbox)
        self.dot_cam = StatusDot("Camera")
        self.dot_hand = StatusDot("Hand Tracking")
        self.dot_voice = StatusDot("Voice")
        self.dot_gaze = StatusDot("Gaze (optional)")
        self.dot_ctl = StatusDot("Control")
        self.dot_env = StatusDot("Lighting")
        dlay.addWidget(self.dot_cam, 0, 0)
        dlay.addWidget(self.dot_hand, 0, 1)
        dlay.addWidget(self.dot_voice, 1, 0)
        dlay.addWidget(self.dot_gaze, 1, 1)
        dlay.addWidget(self.dot_ctl, 2, 0)
        dlay.addWidget(self.dot_env, 2, 1)
        rlay.addWidget(dotbox)

        # stat cards
        cards = QHBoxLayout()
        self.card_fps = StatCard("Camera FPS", "—", "frames / sec")
        self.card_tfps = StatCard("Tracking", "—", "FPS")
        self.card_lat = StatCard("Latency", "—", "ms")
        self.card_cpu = StatCard("CPU", "—", "%")
        self.card_mem = StatCard("RAM", "—", "MB")
        self.card_cmd = StatCard("Commands", "—", "per minute")
        for c in (self.card_fps, self.card_tfps, self.card_lat, self.card_cpu,
                  self.card_mem, self.card_cmd):
            cards.addWidget(c)
        rlay.addLayout(cards)

        # profile row
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Mode:"))
        self.profile_combo = QComboBox()
        for p in self.app.profiles.all():
            self.profile_combo.addItem(self._titles.get(p.id, p.name), p.id)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_change)
        prow.addWidget(self.profile_combo, 1)
        rlay.addLayout(prow)

        # big controls
        btnrow = QGridLayout()
        self.btn_stop = QPushButton("⛔ STOP NO-TOUCH CONTROL")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(lambda: self.app.emergency_stop())
        btnrow.addWidget(self.btn_stop, 0, 0, 1, 2)
        self.btn_resume = QPushButton("▶ Resume")
        self.btn_resume.clicked.connect(lambda: self.app.resume_from_emergency())
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._on_pause)
        btnrow.addWidget(self.btn_pause, 0, 2)
        btnrow.addWidget(self.btn_resume, 0, 3)

        self.btn_camera = QPushButton("📷 Camera: On")
        self.btn_camera.clicked.connect(self._on_camera)
        self.btn_mic = QPushButton("🎤 Mic: On")
        self.btn_mic.clicked.connect(self._on_mic)
        self.btn_privacy = QPushButton("🕶 Privacy Mode")
        self.btn_privacy.setCheckable(True)
        self.btn_privacy.clicked.connect(self._on_privacy)
        btnrow.addWidget(self.btn_camera, 1, 0)
        btnrow.addWidget(self.btn_mic, 1, 1)
        btnrow.addWidget(self.btn_privacy, 1, 2)

        self.btn_calibrate = QPushButton("🎯 Calibrate")
        self.btn_calibrate.clicked.connect(lambda: self.app._ui_calibrate())
        self.btn_keyboard = QPushButton("⌨ Keyboard")
        self.btn_keyboard.clicked.connect(lambda: self.app._ui_keyboard())
        self.btn_trainer = QPushButton("✋ Teach My Gesture")
        self.btn_trainer.clicked.connect(lambda: self.app._ui_trainer())
        self.btn_debug = QPushButton("🐞 Debug")
        self.btn_debug.clicked.connect(lambda: self.app._ui_debug())
        btnrow.addWidget(self.btn_calibrate, 2, 0)
        btnrow.addWidget(self.btn_keyboard, 2, 1)
        btnrow.addWidget(self.btn_trainer, 2, 2)
        btnrow.addWidget(self.btn_debug, 2, 3)

        self.btn_demo = QPushButton("🔵 DEMO MODE")
        self.btn_demo.setCheckable(True)
        self.btn_demo.clicked.connect(self._on_demo)
        self.btn_macro = QPushButton("🧩 Macro Studio")
        self.btn_macro.clicked.connect(lambda: self.app._ui_macros())
        self.btn_testlab = QPushButton("🧪 Test Lab")
        self.btn_testlab.clicked.connect(lambda: self.app._ui_testlab())
        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.clicked.connect(lambda: self.app._ui_settings())
        btnrow.addWidget(self.btn_demo, 3, 0)
        btnrow.addWidget(self.btn_macro, 3, 1)
        btnrow.addWidget(self.btn_testlab, 3, 2)
        btnrow.addWidget(self.btn_settings, 3, 3)
        rlay.addLayout(btnrow)

        # toast
        self.toast = QLabel("")
        self.toast.setStyleSheet("color: #ffe08a; font-size: 13px; min-height: 18px;")
        rlay.addWidget(self.toast)

        # activity log
        rlay.addWidget(QLabel("Activity log"))
        self.activity = QListWidget()
        self.activity.setMaximumHeight(110)
        rlay.addWidget(self.activity)

        # recent actions (real-time, local history)
        rlay.addWidget(QLabel("Recent actions"))
        self.recent = QListWidget()
        self.recent.setMaximumHeight(110)
        rlay.addWidget(self.recent)
        right.setLayout(rlay)
        split.addWidget(right)
        split.setSizes([560, 520])

        root.addWidget(split, 1)

    # ---- state updates --------------------------------------------------------
    def update_status(self, s: StatusSnapshot) -> None:
        self.dot_cam.set_active(s.camera_active,
                                tooltip=self._camera_tooltip(s))
        self.dot_hand.set_active(not s.tracking_paused and s.hand_tracking_active,
                                 tooltip=self._hand_tooltip(s))
        self.dot_voice.set_active(s.voice_ready)
        self.dot_gaze.set_active(s.gaze_ready, tooltip=self._gaze_tooltip(s))
        self.dot_ctl.set_active(s.control_enabled, color_on="#37d67a", color_off="#ff5b5b")
        env_colors = {"dark": "#ff6b6b", "low": "#ffb35c", "bright": "#7cc3ff",
                      "good": "#37d67a"}
        self.dot_env.set_active(s.lighting in ("good", "bright"),
                                color_on=env_colors.get(s.lighting, "#ffb35c"),
                                color_off=env_colors.get(s.lighting, "#ffb35c"))
        self.dot_env.label.setText(f"Lighting: {s.lighting.title()}")

        self.set_demo_badge(s.demo_mode)
        self.set_audio_badge(s.audio_online, s.voice_engine)
        self.gesture_big.setText(self._pretty_gesture(s.gesture, s.gesture_confidence))
        if s.action:
            self.action_label.setText(f"⚡ {s.action}")

        self.card_fps.set_value(f"{s.fps:.1f}")
        self.card_tfps.set_value(f"{s.tracking_fps:.1f}")
        self.card_lat.set_value(f"{s.latency_ms:.0f}")
        self.card_cpu.set_value(f"{s.cpu:.0f}")
        self.card_mem.set_value(f"{s.memory_mb:.0f}")
        self.card_cmd.set_value(f"{s.cmd_per_minute:.1f}")

        pc = self.profile_combo.findData(s.active_profile.lower())
        if pc >= 0 and pc != self.profile_combo.currentIndex():
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentIndex(pc)
            self.profile_combo.blockSignals(False)

        if s.recognized_text:
            self.voice_label.setText(f"🎤 {s.recognized_text}")
            self.toast.setText(s.recognized_text)

        if s.history_count != self._last_history_count:
            self._last_history_count = s.history_count
            self._refresh_recent()

    def set_demo_badge(self, on: bool) -> None:
        if on:
            self.demo_badge.setText("🔵 DEMO MODE")
            self.demo_badge.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #6fc3ff; background: #11263a;"
                "border: 1px solid #2a7ab5; border-radius: 8px; padding: 3px 10px;")
        else:
            self.demo_badge.setText("🔴 REAL")
            self.demo_badge.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #ff6b6b; background: #2a1515;"
                "border: 1px solid #b33636; border-radius: 8px; padding: 3px 10px;")
        if hasattr(self, "btn_demo"):
            self.btn_demo.blockSignals(True)
            self.btn_demo.setChecked(bool(on))
            self.btn_demo.blockSignals(False)

    def set_audio_badge(self, online: bool, engine: str = "") -> None:
        """Honest microphone-privacy badge: when the active engine sends mic
        audio to a cloud service (Google), say so out loud."""
        if not engine:
            text = "🎙 VOICE OFF"
            style = ("font-size: 12px; font-weight: bold; color: #8a8a9a; background: #191922;"
                     "border: 1px solid #44445a; border-radius: 8px; padding: 3px 8px;")
        elif online:
            text = f"🎙 AUDIO ONLINE · {engine.upper()}"
            style = ("font-size: 12px; font-weight: bold; color: #ffb35c; background: #2a2115;"
                     "border: 1px solid #b3802a; border-radius: 8px; padding: 3px 8px;")
        else:
            text = f"🎙 AUDIO LOCAL · {engine.upper()}"
            style = ("font-size: 12px; font-weight: bold; color: #37d67a; background: #13251a;"
                     "border: 1px solid #2a9d5a; border-radius: 8px; padding: 3px 8px;")
        self.audio_badge.setText(text)
        self.audio_badge.setStyleSheet(style)

    def _camera_tooltip(self, s: StatusSnapshot) -> str:
        if s.camera_active:
            return "Camera running"
        err = getattr(getattr(self.app.core, "camera", None), "error", None)
        return err or "Camera unavailable"

    def _hand_tooltip(self, s: StatusSnapshot) -> str:
        if s.tracking_paused:
            return "Tracking paused"
        if s.hand_tracking_active:
            return "Hand model ready"
        err = getattr(getattr(self.app.core, "hand_tracker", None), "error", None)
        return err or "Loading hand model (MediaPipe)…"

    def _gaze_tooltip(self, s: StatusSnapshot) -> str:
        if not s.gaze_ready:
            core = getattr(self.app, "core", None)
            if not getattr(getattr(core, "settings", None), "tracking", None) or \
                    not core.settings.tracking.gaze_enabled:
                return "Gaze tracking disabled"
            err = getattr(getattr(core, "face_tracker", None), "error", None)
            if err:
                return f"Face model error: {err}"
            return "Face model loading…"
        if s.gaze_active:
            return "Gaze active (tracking your eyes)"
        return "Gaze ready — face not in view"

    def _refresh_recent(self) -> None:
        try:
            rows = self.app.core.get_history(20)
        except Exception:
            return
        self.recent.clear()
        for r in reversed(rows):
            self.recent.addItem(
                f"[{r.get('source','?')}] {r.get('status','')} — {r.get('action','')}")

    def update_preview(self, image: QImage) -> None:
        if image.isNull():
            return
        pix = QPixmap.fromImage(image)
        self.preview.setPixmap(pix.scaled(self.preview.size(),
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))

    @staticmethod
    def _pretty_gesture(g: str, conf: float) -> str:
        names = {
            "POINT": "☝️ POINT", "PINCH": "🤏 PINCH", "RIGHT_PINCH": "🤏 RIGHT-PINCH",
            "OPEN_PALM": "🖐 PALM", "FIST": "✊ FIST", "TWO_FINGER": "✌️ TWO-FINGER",
            "THREE_FINGER": "✌️🤙 THREE", "FOUR_FINGER": "✋ FOUR", "VICTORY": "✌️ VICTORY",
            "LOCKED": "🔒 LOCKED", "REST": "—",
        }
        txt = names.get(g, g)
        return f"{txt}  {conf:>4.0%}" if conf else txt

    # ---- handlers ----------------------------------------------------------
    def _on_profile_change(self, idx: int) -> None:
        pid = self.profile_combo.itemData(idx)
        if pid:
            self.app.set_profile(pid)

    def _on_pause(self, checked: bool) -> None:
        self.app.pause_tracking(checked)
        self.btn_pause.setText("⏸ Resume" if checked else "⏸ Pause")

    def _on_camera(self) -> None:
        self.app.toggle_camera()
        self.btn_camera.setText("📷 Camera: Off" if not self.app.privacy.camera_enabled else "📷 Camera: On")

    def _on_mic(self) -> None:
        self.app.toggle_mic()
        self.btn_mic.setText("🎤 Mic: Off" if not self.app.privacy.mic_enabled else "🎤 Mic: On")

    def _on_privacy(self, checked: bool) -> None:
        self.app.toggle_privacy_mode()

    def _on_demo(self) -> None:
        self.app.core.toggle_demo()

    def on_toast(self, text: str) -> None:
        self.toast.setText(text)

    def on_log(self, level: str, message: str) -> None:
        self.activity.insertItem(0, f"[{level}] {message}")
        while self.activity.count() > 60:
            self.activity.takeItem(self.activity.count() - 1)

    def on_emergency(self) -> None:
        self.btn_stop.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.toast.setText("⛔ EMERGENCY STOP — press Resume or CTRL+ALT+H to re-enable")

    def on_resume(self) -> None:
        self.btn_stop.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.toast.setText("✓ Control re-enabled")