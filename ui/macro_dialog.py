import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QListWidget, QMessageBox, QTextEdit, QVBoxLayout,
)

import config.i18n as i18n
from config.i18n import tr
from core.macro_engine import MacroEngine
from core.command_orchestrator import CommandOrchestrator
from ui import theme
from ui import widgets as W


class MacroManagerDialog(QDialog):
    """Browse, run and delete the saved automation macros."""

    def __init__(self, parent=None):
        super(MacroManagerDialog, self).__init__(parent)
        self.setFixedSize(660, 500)
        self.macro_engine = MacroEngine()
        self.orchestrator = CommandOrchestrator()

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)
        self._refresh_list()
        self.retranslate()

    # ------------------------------------------------------------------ #

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 2, theme.PAD + 2, theme.PAD + 2, theme.PAD + 2)
        root.setSpacing(theme.GAP)

        self.title_label = W.label(self, "", "pageTitle")
        root.addWidget(self.title_label)

        content = W.hbox()

        # Saved macros
        left_card = W.frame(self, "card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        left_layout.setSpacing(8)
        self.saved_heading = W.section_title(left_card, "")
        left_layout.addWidget(self.saved_heading)
        self.macro_list = QListWidget(left_card)
        self.macro_list.itemClicked.connect(self._on_item_selected)
        left_layout.addWidget(self.macro_list, 1)
        content.addWidget(left_card, 1)

        # Steps preview
        right_card = W.frame(self, "card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        right_layout.setSpacing(8)
        self.preview_heading = W.section_title(right_card, "")
        right_layout.addWidget(self.preview_heading)
        self.steps_preview = QTextEdit(right_card)
        self.steps_preview.setReadOnly(True)
        right_layout.addWidget(self.steps_preview, 1)
        content.addWidget(right_card, 1)

        root.addLayout(content, 1)

        actions = W.hbox()
        self.play_btn = W.button(self, "", "primary", self._run_selected)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn = W.button(self, "", "danger", self._delete_selected)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn = W.button(self, "", "ghost", self.accept)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        for btn in (self.play_btn, self.del_btn):
            actions.addWidget(btn)
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
        self.setWindowTitle(tr("macro.title"))
        self.title_label.setText(tr("macro.heading"))
        self.saved_heading.setText(tr("macro.saved"))
        self.preview_heading.setText(tr("macro.preview"))
        self.play_btn.setText(tr("macro.run"))
        self.del_btn.setText(tr("common.delete"))
        self.close_btn.setText(tr("common.close"))
        self._refresh_list()

    # ------------------------------------------------------------------ #

    def _refresh_list(self):
        selected = self.macro_list.currentItem().text() if self.macro_list.currentItem() else None
        self.macro_list.clear()

        macros = self.macro_engine.get_all_macros()
        for name in macros:
            self.macro_list.addItem(name)

        if self.macro_list.count() == 0:
            self.steps_preview.setPlainText(tr("macro.empty"))
            return

        if selected and self.macro_list.findItems(selected, Qt.MatchExactly):
            self.macro_list.setCurrentItem(self.macro_list.findItems(selected, Qt.MatchExactly)[0])
        else:
            self.macro_list.setCurrentRow(0)
        self._on_item_selected(self.macro_list.currentItem())

    def _on_item_selected(self, item):
        if not item:
            return
        macros = self.macro_engine.get_all_macros()
        self.steps_preview.setPlainText(
            json.dumps(macros.get(item.text(), []), indent=2, ensure_ascii=False)
        )

    def _run_selected(self):
        item = self.macro_list.currentItem()
        if not item:
            return
        name = item.text()
        self.macro_engine.execute_macro(name, self.orchestrator._execute_macro_step)
        QMessageBox.information(
            self,
            tr("macro.running_title"),
            tr("macro.running_body", name=name),
        )

    def _delete_selected(self):
        item = self.macro_list.currentItem()
        if item:
            self.macro_engine.delete_macro(item.text())
            self._refresh_list()

    def done(self, result: int):
        i18n.get_translator().remove_listener(self._on_language_changed)
        super(MacroManagerDialog, self).done(result)
