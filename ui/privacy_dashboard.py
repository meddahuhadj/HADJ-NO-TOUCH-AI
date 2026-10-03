from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QVBoxLayout

import config.i18n as i18n
from config.i18n import tr
from config.settings_manager import SettingsManager
from ui import theme
from ui import widgets as W

# (label key, value key, badge variant)
_STATUS_ROWS = [
    ("privacy.microphone", "privacy.status_enabled", "badgeSuccess"),
    ("privacy.camera", "privacy.status_active", "badgeSuccess"),
    ("privacy.voice_processing", "privacy.status_local", "badgeAccent"),
    ("privacy.gesture_processing", "privacy.status_local", "badgeAccent"),
    ("privacy.internet", "privacy.status_offline", "badgeSuccess"),
    ("privacy.telemetry", "privacy.status_disabled", "badgeNeutral"),
    ("privacy.biometric", "privacy.status_never", "badgeSuccess"),
    ("privacy.remote_apis", "privacy.status_blocked", "badgeNeutral"),
]


class PrivacyDashboardDialog(QDialog):
    """Shows the local-processing guarantees and the privacy toggles."""

    def __init__(self, parent=None):
        super(PrivacyDashboardDialog, self).__init__(parent)
        self.setFixedSize(580, 560)
        self.settings = SettingsManager()

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4)
        root.setSpacing(theme.GAP)

        header = W.hbox()
        self.title_label = W.label(self, "", "pageTitle")
        header.addWidget(self.title_label)
        header.addWidget(W.spacer())
        self.offline_badge = W.label(self, "", "badgeSuccess")
        header.addWidget(self.offline_badge)
        root.addLayout(header)

        self.intro_label = W.label(self, "", "muted", wrap=True)
        root.addWidget(self.intro_label)

        # Status grid
        self.status_card = W.frame(self, "card")
        grid = QGridLayout(self.status_card)
        grid.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        grid.setHorizontalSpacing(theme.GAP)
        grid.setVerticalSpacing(12)

        self._status_labels = []
        self._status_badges = []
        for index, (_, _, variant) in enumerate(_STATUS_ROWS):
            row, col = divmod(index, 2)
            # Key names and status badges both need to reflow for the longer
            # French and English wording.
            key_label = W.label(self.status_card, "", "faint", wrap=True)
            badge = W.label(self.status_card, "", variant, align=Qt.AlignCenter, wrap=True)
            key_label.setMinimumWidth(0)
            badge.setMinimumWidth(0)
            grid.addWidget(key_label, row, col * 2)
            grid.addWidget(badge, row, col * 2 + 1)
            self._status_labels.append(key_label)
            self._status_badges.append(badge)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        root.addWidget(self.status_card)

        # Guarantee notice
        self.notice = W.frame(self, "notice")
        notice_layout = QVBoxLayout(self.notice)
        notice_layout.setContentsMargins(theme.PAD - 4, 12, theme.PAD - 4, 12)
        self.notice_label = W.label(self.notice, "", "faint", wrap=True)
        self.notice_label.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 12px; line-height: 160%;"
        )
        notice_layout.addWidget(self.notice_label)
        root.addWidget(self.notice)

        root.addStretch()

        # Actions
        actions = W.hbox()
        self.offline_toggle_btn = W.button(self, "", "primary", self._toggle_offline_enforcement)
        self.offline_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn = W.button(self, "", "ghost", self.accept)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        actions.addWidget(self.offline_toggle_btn)
        actions.addWidget(W.spacer())
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("privacy.title"))
        self.title_label.setText(tr("privacy.heading"))
        self.offline_badge.setText("● " + tr("app.offline_first").upper())
        self.intro_label.setText(tr("privacy.intro"))
        self.notice_label.setText(tr("privacy.guarantee"))

        for (label_key, value_key, _), key_label, badge in zip(
            _STATUS_ROWS, self._status_labels, self._status_badges
        ):
            key_label.setText(tr(label_key))
            badge.setText(tr(value_key))

        self._refresh_offline_button()
        self.close_btn.setText(tr("common.close"))

    def _refresh_offline_button(self):
        offline = self.settings.get("privacy.offline_mode", True)
        if offline:
            self.offline_toggle_btn.setText(tr("privacy.offline_active"))
            self.offline_toggle_btn.setObjectName("primary")
            self.offline_toggle_btn.setProperty("class", "primary")
            self.offline_toggle_btn.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                f"stop:0 {theme.ACCENT}, stop:1 {theme.ACCENT_DEEP});"
                f"color: #04121C; border: 1px solid {theme.ACCENT};"
            )
        else:
            self.offline_toggle_btn.setText(tr("privacy.hybrid_mode"))
            self.offline_toggle_btn.setObjectName("ghost")
            self.offline_toggle_btn.setProperty("class", "ghost")
            self.offline_toggle_btn.setStyleSheet(
                f"background: transparent; color: {theme.WARNING};"
                f"border: 1px solid {theme.WARNING};"
            )
        theme.repolish(self.offline_toggle_btn)

    # ------------------------------------------------------------------ #

    def _toggle_offline_enforcement(self):
        new_value = not self.settings.get("privacy.offline_mode", True)
        self.settings.set("privacy.offline_mode", new_value)
        self._refresh_offline_button()

    def done(self, result: int):
        i18n.get_translator().remove_listener(self._on_language_changed)
        super(PrivacyDashboardDialog, self).done(result)
