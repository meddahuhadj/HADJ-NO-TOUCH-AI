"""نافذة الإعدادات: تبويبات بالعربية (من اليمين لليسار)، عناصر كبيرة تصلح للنقر بالإيماءات.

collect() يرجع التغييرات كقاموس يُدمج في user_data/config.yaml.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from config.schema import AppConfig
from ui.i18n import Tr
from ui.icons import app_icon
from ui.theme import theme

GESTURES = ["pinch_tap", "middle_pinch_tap", "fist_hold", "palm_hold_long", "two_scroll",
            "swipe_right", "swipe_left", "zoom_in", "zoom_out"]
GESTURE_ACTIONS = ["none", "click", "double_click", "right_click", "middle_click", "scroll",
                   "zoom_in", "zoom_out", "switch_window", "switch_window_prev", "show_desktop",
                   "minimize_window", "maximize_window", "snap_left", "snap_right", "task_view",
                   "open_explorer", "open_task_manager", "media_play_pause",
                   "app.pause", "app.show_grid", "app.start_dictation", "screenshot",
                   "volume_up", "volume_down", "mute", "browser_back", "browser_forward",
                   "browser_refresh"]


def _combo(items: list[tuple[str, str]], current: str) -> QComboBox:
    """items: [(القيمة، النص المعروض)]."""
    c = QComboBox()
    for value, label in items:
        c.addItem(label, value)
    idx = c.findData(current)
    if idx < 0 and current not in (None, ""):
        c.addItem(str(current), current)   # قيمة مخصصة من ملف الإعدادات
        idx = c.count() - 1
    c.setCurrentIndex(max(idx, 0))
    return c


def _dspin(value: float, lo: float, hi: float, step: float, decimals: int = 2) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    s.setValue(value)
    return s


def _spin(value: int, lo: int, hi: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    return s


class SettingsWindow(QWidget):
    def __init__(self, tr: Tr, config: AppConfig, models_dir: Path, mic_names: list[str],
                 on_save: Callable[[dict], None], on_calibrate: Callable[[], None] | None = None,
                 on_open_folder: Callable[[], None] | None = None, profiles_api=None):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.t = tr
        self.cfg = config
        self.on_save = on_save
        self.models_dir = models_dir
        self.setObjectName("windowRoot")
        self.setWindowTitle(tr("set_title"))
        self.setWindowIcon(app_icon(64, config.ui.high_contrast))
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        scale = config.ui.font_scale
        self.th = theme(scale, config.ui.high_contrast)
        t = self.th
        self.setFont(QFont("Segoe UI", t.pt(10.5)))
        self.setStyleSheet(t.qss())

        header = QLabel(tr("set_title"), self)
        header.setStyleSheet(f"color: {t.c('text')}; background: transparent;"
                             f" font-size: {t.pt(16)}pt; font-weight: 700;")
        subtitle = QLabel(tr("app_name"), self)
        subtitle.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;"
                               f" font-size: {t.pt(9.5)}pt;")

        tabs = QTabWidget()
        tabs.addTab(self._general(), f"⚙️ {tr('tab_general')}")
        tabs.addTab(self._speech(models_dir, mic_names), f"🎙️ {tr('tab_speech')}")
        tabs.addTab(self._camera(on_calibrate), f"📷 {tr('tab_camera')}")
        tabs.addTab(self._gestures(), f"✋ {tr('tab_gestures')}")
        tabs.addTab(self._safety(), f"🛡️ {tr('tab_safety')}")
        self.profiles_tab = None
        if profiles_api is not None:
            from ui.profiles_tab import ProfilesTab
            self.profiles_tab = ProfilesTab(tr, t, profiles_api, GESTURE_ACTIONS, _combo)
            tabs.addTab(self.profiles_tab, f"🗂️ {tr('tab_profiles')}")
            from ui.macros_tab import MacrosTab
            self.macros_tab = MacrosTab(tr, t, profiles_api, _combo)
            tabs.addTab(self.macros_tab, f"⚡ {tr('tab_macros')}")
        tabs.setDocumentMode(True)

        save = QPushButton(tr("set_save"))
        save.setObjectName("primaryButton")
        save.setProperty("role", "wide")
        save.clicked.connect(self._save)
        cancel = QPushButton(tr("set_cancel"))
        cancel.setObjectName("ghostButton")
        cancel.setProperty("role", "wide")
        cancel.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.setSpacing(t.px(10))
        buttons.addWidget(save, 2)
        buttons.addWidget(cancel, 1)
        if on_open_folder:
            folder = QPushButton(tr("set_open_folder"))
            folder.setObjectName("ghostButton")
            folder.setProperty("role", "wide")
            folder.clicked.connect(on_open_folder)
            buttons.addWidget(folder, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(t.px(24), t.px(22), t.px(24), t.px(20))
        lay.setSpacing(t.px(14))
        lay.addWidget(header)
        lay.addWidget(subtitle)
        lay.addWidget(tabs, 1)
        lay.addLayout(buttons)
        self.resize(t.px(700), t.px(620))

    # ---------------- التبويبات ----------------
    def _form(self) -> tuple[QWidget, QFormLayout]:
        """صفحة تبويب: نموذج بمسافات واسعة داخل منطقة قابلة للتمرير (حجم خط كبير)."""
        holder = QWidget()
        margin = self.th.px(6)
        outer = QVBoxLayout(holder)
        outer.setContentsMargins(margin, margin, margin, margin)
        inner = QWidget()
        f = QFormLayout(inner)
        f.setContentsMargins(0, 0, 0, 0)
        f.setVerticalSpacing(self.th.px(14))
        f.setHorizontalSpacing(self.th.px(18))
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        outer.addWidget(inner)
        outer.addStretch(1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(holder)
        area.setFocusPolicy(Qt.NoFocus)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setStyleSheet("background: transparent;")
        area.viewport().setStyleSheet("background: transparent;")
        return area, f

    def _style_labels(self, form: QFormLayout) -> None:
        """تسميات الحقول: لون باهت ومحاذاة موحّدة (تُبنى بعد addRow)."""
        for i in range(form.rowCount()):
            item = form.itemAt(i, QFormLayout.LabelRole)
            label = item.widget() if item else None
            if isinstance(label, QLabel):
                label.setStyleSheet(f"color: {self.th.c('text_dim')}; background: transparent;")

    def _general(self) -> QWidget:
        t, c = self.t, self.cfg
        w, f = self._form()
        langs = [("ar", "العربية"), ("en", "English"), ("fr", "Français")]
        self.ui_lang = _combo(langs, c.ui.ui_language)
        from core.edition import available_languages, fallback_language
        installed = available_languages(self.models_dir) or [code for code, _ in langs]
        self.cmd_lang = _combo([x for x in langs if x[0] in installed],
                               fallback_language(c.speech.language, installed))
        self.wake_ar = QLineEdit(", ".join(c.speech.wake_words.get("ar", [])))
        self.wake_en = QLineEdit(", ".join(c.speech.wake_words.get("en", [])))
        self.wake_fr = QLineEdit(", ".join(c.speech.wake_words.get("fr", [])))
        self.continuous = QCheckBox()
        self.continuous.setChecked(c.speech.continuous_listening)
        self.sounds = QCheckBox()
        self.sounds.setChecked(c.feedback.sounds)
        self.sound_volume = _spin(c.feedback.sound_volume, 10, 100)
        self.hand_sounds = QCheckBox()
        self.hand_sounds.setChecked(c.feedback.hand_sounds)
        self.status_orb = QCheckBox()
        self.status_orb.setChecked(c.ui.status_orb)
        self.orb_corner = _combo([(k, t(f"orb_{k}")) for k in
                                  ("auto", "top-left", "top-right", "bottom-left", "bottom-right")],
                                 c.ui.orb_corner)
        self.overlay = QCheckBox()
        self.overlay.setChecked(c.ui.overlay)
        self.overlay_s = _dspin(c.ui.overlay_seconds, 1, 30, 0.5, 1)
        self.font_scale = _dspin(c.ui.font_scale, 0.75, 3.0, 0.25)
        self.high_contrast = QCheckBox()
        self.high_contrast.setChecked(c.ui.high_contrast)
        for key, widget in [("set_ui_language", self.ui_lang), ("set_cmd_language", self.cmd_lang),
                            ("set_wake_ar", self.wake_ar), ("set_wake_en", self.wake_en),
                            ("set_wake_fr", self.wake_fr),
                            ("set_continuous", self.continuous), ("set_sounds", self.sounds),
                            ("set_sound_volume", self.sound_volume), ("set_hand_sounds", self.hand_sounds),
                            ("set_status_orb", self.status_orb), ("set_orb_corner", self.orb_corner),
                            ("set_overlay", self.overlay), ("set_overlay_seconds", self.overlay_s),
                            ("set_font_scale", self.font_scale), ("set_high_contrast", self.high_contrast)]:
            f.addRow(t(key), widget)
        self._style_labels(f)
        return w

    def _speech(self, models_dir: Path, mic_names: list[str]) -> QWidget:
        t, c = self.t, self.cfg
        w, f = self._form()
        mics = [(None, t("set_default_device"))] + [(i, n) for i, n in enumerate(mic_names)]
        self.mic = _combo(mics, c.speech.input_device)
        self.vad = _spin(c.speech.vad_aggressiveness, 0, 3)
        self.threshold = _spin(c.speech.match_threshold, 50, 100)
        self.followup = _dspin(c.speech.followup_s, 0, 60, 1, 0)
        from core.edition import whisper_available
        engines = ([("whisper", t("engine_whisper"))] if whisper_available(models_dir) else []) + \
            [("vosk", t("engine_vosk"))]
        self.engine = _combo(engines, c.dictation.engine if len(engines) > 1 else "vosk")
        wdir = models_dir / "whisper"
        models = sorted(p.name for p in wdir.iterdir() if (p / "model.bin").exists()) if wdir.exists() else []
        self.whisper_model = _combo([(m, m) for m in models], c.dictation.whisper_model)
        for key, widget in [("set_mic", self.mic), ("set_vad", self.vad), ("set_threshold", self.threshold),
                            ("set_followup", self.followup), ("set_dict_engine", self.engine),
                            ("set_dict_model", self.whisper_model)]:
            f.addRow(t(key), widget)
        self._style_labels(f)
        return w

    def _camera(self, on_calibrate) -> QWidget:
        t, v = self.t, self.cfg.vision
        w, f = self._form()
        self.cam_enabled = QCheckBox()
        self.cam_enabled.setChecked(v.enabled)
        self.cam_index = _spin(v.camera_index, 0, 9)
        self.preview = QCheckBox()
        self.preview.setChecked(v.preview)
        self.hand = _combo([("any", t("hand_any")), ("right", t("hand_right")), ("left", t("hand_left"))], v.hand)
        self.min_cutoff = _dspin(v.min_cutoff, 0.05, 20, 0.1)
        self.beta = _dspin(v.beta, 0, 1, 0.005, 3)
        zone_row = QHBoxLayout()
        self.zone = [_dspin(val, 0, 1, 0.01) for val in v.control_zone]
        for s in self.zone:
            zone_row.addWidget(s)
        pinch_row = QHBoxLayout()
        self.pinch_enter = _dspin(v.tuning.pinch_enter, 0.05, 0.6, 0.01)
        self.pinch_exit = _dspin(v.tuning.pinch_exit, 0.1, 0.9, 0.01)
        pinch_row.addWidget(self.pinch_enter)
        pinch_row.addWidget(self.pinch_exit)
        self.scroll_invert = QCheckBox()
        self.scroll_invert.setChecked(v.tuning.scroll_invert)
        self.idle_light = _dspin(v.idle_light_s / 60, 0, 60, 0.5, 1)
        self.idle_deep = _dspin(v.idle_deep_s / 60, 0, 120, 1, 0)
        self.wake_on_input = QCheckBox()
        self.wake_on_input.setChecked(v.wake_on_input)
        for key, widget in [("set_cam_enabled", self.cam_enabled), ("set_cam_index", self.cam_index),
                            ("set_preview", self.preview), ("set_hand", self.hand),
                            ("set_smooth", self.min_cutoff), ("set_speed", self.beta)]:
            f.addRow(t(key), widget)
        f.addRow(t("set_zone"), zone_row)
        f.addRow(t("set_pinch"), pinch_row)
        f.addRow(t("set_scroll_invert"), self.scroll_invert)
        f.addRow(t("set_idle_light"), self.idle_light)
        f.addRow(t("set_idle_deep"), self.idle_deep)
        f.addRow(t("set_wake_on_input"), self.wake_on_input)
        if on_calibrate:
            btn = QPushButton(t("set_calibrate"))
            btn.setObjectName("ghostButton")
            btn.setProperty("role", "wide")
            btn.clicked.connect(lambda: (self.close(), on_calibrate()))
            f.addRow(btn)
        self._style_labels(f)
        return w

    def _gestures(self) -> QWidget:
        t = self.t
        w, f = self._form()
        actions = [(a, t(f"act_{a}")) for a in GESTURE_ACTIONS]
        self.bindings = {}
        for g in GESTURES:
            combo = _combo(actions, self.cfg.vision.bindings.get(g, "none"))
            self.bindings[g] = combo
            f.addRow(t(f"g_{g}"), combo)
        self._style_labels(f)
        return w

    def _safety(self) -> QWidget:
        t, s = self.t, self.cfg.safety
        w, f = self._form()
        self.hotkey = QLineEdit(s.emergency_hotkey)
        self.confirm = QCheckBox()
        self.confirm.setChecked(s.confirm_dangerous)
        self.confirm_timeout = _dspin(s.confirm_timeout_s, 2, 60, 1, 0)
        f.addRow(t("set_hotkey"), self.hotkey)
        f.addRow(t("set_confirm"), self.confirm)
        f.addRow(t("set_confirm_timeout"), self.confirm_timeout)
        self._style_labels(f)
        return w

    # ---------------- الحفظ ----------------
    @staticmethod
    def _words(edit: QLineEdit) -> list[str]:
        return [w.strip() for w in edit.text().replace("،", ",").split(",") if w.strip()]

    def collect(self) -> dict:
        zone = [round(s.value(), 3) for s in self.zone]
        if zone[2] - zone[0] < 0.1 or zone[3] - zone[1] < 0.1:   # منطقة غير صالحة ← بلا تغيير
            zone = list(self.cfg.vision.control_zone)
        enter, exit_ = self.pinch_enter.value(), self.pinch_exit.value()
        if exit_ <= enter:
            exit_ = round(enter + 0.1, 2)
        wake = {lang: self._words(edit) or self.cfg.speech.wake_words.get(lang, [])
                for lang, edit in (("ar", self.wake_ar), ("en", self.wake_en), ("fr", self.wake_fr))}
        return {
            "ui": {"ui_language": self.ui_lang.currentData(), "font_scale": self.font_scale.value(),
                   "high_contrast": self.high_contrast.isChecked(), "overlay": self.overlay.isChecked(),
                   "overlay_seconds": self.overlay_s.value(),
                   "status_orb": self.status_orb.isChecked(), "orb_corner": self.orb_corner.currentData()},
            "speech": {"language": self.cmd_lang.currentData(), "wake_words": wake,
                       "continuous_listening": self.continuous.isChecked(),
                       "input_device": self.mic.currentData(), "vad_aggressiveness": self.vad.value(),
                       "match_threshold": self.threshold.value(), "followup_s": self.followup.value()},
            "feedback": {"sounds": self.sounds.isChecked(), "sound_volume": self.sound_volume.value(),
                         "hand_sounds": self.hand_sounds.isChecked()},
            "dictation": {"engine": self.engine.currentData(),
                          "whisper_model": self.whisper_model.currentData() or self.cfg.dictation.whisper_model},
            "vision": {"enabled": self.cam_enabled.isChecked(), "camera_index": self.cam_index.value(),
                       "preview": self.preview.isChecked(), "hand": self.hand.currentData(),
                       "min_cutoff": self.min_cutoff.value(), "beta": self.beta.value(),
                       "control_zone": zone,
                       "idle_light_s": int(round(self.idle_light.value() * 60)),
                       "idle_deep_s": int(round(self.idle_deep.value() * 60)),
                       "wake_on_input": self.wake_on_input.isChecked(),
                       "tuning": {"pinch_enter": enter, "pinch_exit": exit_,
                                  "scroll_invert": self.scroll_invert.isChecked()},
                       "bindings": {g: c.currentData() for g, c in self.bindings.items()}},
            "safety": {"emergency_hotkey": self.hotkey.text().strip(),
                       "confirm_dangerous": self.confirm.isChecked(),
                       "confirm_timeout_s": self.confirm_timeout.value()},
        }

    def _save(self) -> None:
        self.on_save(self.collect())
        self.close()
