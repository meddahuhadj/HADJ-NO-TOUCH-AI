from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QRadioButton, QVBoxLayout,
)

import config.i18n as i18n
from config.i18n import tr
from config.settings_manager import SettingsManager
from ui import theme
from ui import widgets as W

MODES = ["MULTIMODAL", "VOICE_ONLY", "GESTURE_ONLY", "HEAD_ONLY", "VOICE_GAZE"]


class AccessibilityDialog(QDialog):
    """Accessibility control panel for adapted, hands-free operation."""

    def __init__(self, parent=None):
        super(AccessibilityDialog, self).__init__(parent)
        self.setMinimumSize(560, 500)
        self.resize(620, 560)
        self.settings = SettingsManager()

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 2, theme.PAD + 2, theme.PAD + 2, theme.PAD + 2)
        root.setSpacing(theme.GAP)

        self.title_label = W.label(self, "", "pageTitle")
        root.addWidget(self.title_label)

        self.intro_label = W.label(self, "", "muted", wrap=True)
        root.addWidget(self.intro_label)

        # Interaction profiles
        self.mode_card = W.frame(self, "card")
        mode_layout = QVBoxLayout(self.mode_card)
        mode_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        mode_layout.setSpacing(6)
        self.mode_heading = W.section_title(self.mode_card, "")
        mode_layout.addWidget(self.mode_heading)

        self.btn_group = QButtonGroup(self)
        self._mode_buttons = {}
        self._mode_descriptions = {}
        for mode in MODES:
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(1)
            radio = QRadioButton(self.mode_card)
            self._mode_buttons[mode] = radio
            self.btn_group.addButton(radio)
            row.addWidget(radio)
            # QRadioButton cannot word-wrap, so the detail lives on its own
            # wrapping line underneath.
            detail = W.label(self.mode_card, "", "faint", wrap=True)
            detail.setContentsMargins(22, 0, 0, 0)
            detail.setMinimumWidth(0)
            row.addWidget(detail)
            self._mode_descriptions[mode] = detail
            mode_layout.addLayout(row)
            radio.toggled.connect(
                lambda checked, key=mode: self._on_mode_toggled(checked, key)
            )
        root.addWidget(self.mode_card)

        # Options
        self.option_card = W.frame(self, "card")
        option_layout = QVBoxLayout(self.option_card)
        option_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        option_layout.setSpacing(4)
        self.option_heading = W.section_title(self.option_card, "")
        option_layout.addWidget(self.option_heading)

        self.dwell_cb = QCheckBox(self.option_card)
        self.dwell_cb.setChecked(self.settings.get("accessibility.dwell_click", False))
        self.dwell_cb.toggled.connect(
            lambda v: self.settings.set("accessibility.dwell_click", v)
        )
        self.dwell_desc = W.label(self.option_card, "", "faint", wrap=True)
        self.dwell_desc.setContentsMargins(22, 0, 0, 0)
        self.dwell_desc.setMinimumWidth(0)
        option_layout.addWidget(self.dwell_cb)
        option_layout.addWidget(self.dwell_desc)

        self.large_cursor_cb = QCheckBox(self.option_card)
        self.large_cursor_cb.setChecked(self.settings.get("accessibility.large_cursor", True))
        self.large_cursor_cb.toggled.connect(
            lambda v: self.settings.set("accessibility.large_cursor", v)
        )
        self.large_cursor_desc = W.label(self.option_card, "", "faint", wrap=True)
        self.large_cursor_desc.setContentsMargins(22, 0, 0, 0)
        self.large_cursor_desc.setMinimumWidth(0)
        option_layout.addWidget(self.large_cursor_cb)
        option_layout.addWidget(self.large_cursor_desc)

        # High Contrast Theme option
        self.contrast_cb = QCheckBox(self.option_card)
        self.contrast_cb.setChecked(theme.is_high_contrast())
        self.contrast_cb.toggled.connect(self._on_contrast_toggled)
        self.contrast_desc = W.label(self.option_card, "", "faint", wrap=True)
        self.contrast_desc.setContentsMargins(22, 0, 0, 0)
        self.contrast_desc.setMinimumWidth(0)
        option_layout.addWidget(self.contrast_cb)
        option_layout.addWidget(self.contrast_desc)

        # Dominant Hand options
        hand_box = W.hbox(spacing=14)
        self.hand_label = W.label(self.option_card, "", "faint")
        hand_box.addWidget(self.hand_label)
        self.right_hand_rb = QRadioButton(self.option_card)
        self.left_hand_rb = QRadioButton(self.option_card)
        self.hand_group = QButtonGroup(self)
        self.hand_group.addButton(self.right_hand_rb)
        self.hand_group.addButton(self.left_hand_rb)
        self.right_hand_rb.toggled.connect(lambda c: self.settings.set("gestures.dominant_hand", "right") if c else None)
        self.left_hand_rb.toggled.connect(lambda c: self.settings.set("gestures.dominant_hand", "left") if c else None)
        is_left = (self.settings.get("gestures.dominant_hand", "right") == "left")
        if is_left:
            self.left_hand_rb.setChecked(True)
        else:
            self.right_hand_rb.setChecked(True)
        hand_box.addWidget(self.right_hand_rb)
        hand_box.addWidget(self.left_hand_rb)
        hand_box.addWidget(W.spacer())
        option_layout.addLayout(hand_box)

        root.addWidget(self.option_card)

        root.addStretch()

        actions = W.hbox()
        actions.addWidget(W.spacer())
        self.done_btn = W.button(self, "", "primary", self.accept)
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.setMinimumWidth(124)
        actions.addWidget(self.done_btn)
        root.addLayout(actions)

    def _on_contrast_toggled(self, checked: bool):
        new_mode = "high_contrast" if checked else "dark"
        theme.set_theme_mode(new_mode)
        theme.apply_to(self)

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("access.title"))
        self.title_label.setText(tr("access.heading"))
        self.intro_label.setText(tr("access.intro"))
        self.mode_heading.setText(tr("access.profiles_title"))
        self.option_heading.setText(tr("access.options_title"))

        for mode, radio in self._mode_buttons.items():
            radio.setText(tr(f"access.mode_{mode}_name"))
            self._mode_descriptions[mode].setText(tr(f"access.mode_{mode}_desc"))
        current = self.settings.get("accessibility.mode", "MULTIMODAL")
        if current in self._mode_buttons:
            self._mode_buttons[current].setChecked(True)

        self.dwell_cb.setText(tr("access.dwell_name"))
        self.dwell_desc.setText(tr("access.dwell_desc"))
        self.large_cursor_cb.setText(tr("access.large_cursor_name"))
        self.large_cursor_desc.setText(tr("access.large_cursor_desc"))

        self.contrast_cb.setText(tr("main.theme_high_contrast"))
        self.contrast_desc.setText(tr("access.contrast_desc"))
        self.hand_label.setText("✋ " + tr("calib.dominant_hand") + ":")
        self.right_hand_rb.setText(tr("calib.hand_right"))
        self.left_hand_rb.setText(tr("calib.hand_left"))

        self.done_btn.setText(tr("common.done"))

    # ------------------------------------------------------------------ #

    def _on_mode_toggled(self, checked: bool, mode_key: str):
        if checked:
            self.settings.set("accessibility.mode", mode_key)

    def done(self, result: int):
        i18n.get_translator().remove_listener(self._on_language_changed)
        super(AccessibilityDialog, self).done(result)
