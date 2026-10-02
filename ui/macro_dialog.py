import json
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QListWidget, QMessageBox, QTextEdit, QVBoxLayout,
    QHBoxLayout, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QDoubleSpinBox, QAbstractItemView
)

import config.i18n as i18n
from config.i18n import tr
from core.macro_engine import MacroEngine
from core.command_orchestrator import CommandOrchestrator
from ui import theme
from ui import widgets as W


ACTION_TYPES = [
    ("LAUNCH_APP", "macro.step_launch_app"),
    ("TYPE_TEXT", "macro.step_type_text"),
    ("KEY_PRESS", "macro.step_key_press"),
    ("HOTKEY", "macro.step_hotkey"),
    ("VOLUME_SET", "macro.step_volume"),
    ("BRIGHTNESS_SET", "macro.step_brightness"),
    ("OPEN_FOLDER", "macro.step_folder"),
    ("WAIT", "macro.step_wait"),
]

GESTURE_OPTIONS = [
    ("NONE", "macro.none"),
    ("DOUBLE_PINCH", "DOUBLE_PINCH"),
    ("SWIPE_LEFT", "SWIPE_LEFT"),
    ("SWIPE_RIGHT", "SWIPE_RIGHT"),
    ("PINCH_HOLD", "PINCH_HOLD"),
    ("TWO_FINGER_SCROLL_UP", "TWO_FINGER_SCROLL_UP"),
    ("TWO_FINGER_SCROLL_DOWN", "TWO_FINGER_SCROLL_DOWN"),
]


class MacroEditorDialog(QDialog):
    """Interactive visual composer for custom automation macros with voice/gesture triggers."""

    def __init__(self, parent=None, macro_name: Optional[str] = None):
        super(MacroEditorDialog, self).__init__(parent)
        self.setFixedSize(700, 560)
        self.macro_engine = MacroEngine()
        self.editing_name = macro_name

        theme.apply_to(self)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)

        self._init_ui()
        if self.editing_name:
            self._load_existing_macro(self.editing_name)
        self.retranslate()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4)
        root.setSpacing(theme.GAP)

        self.title_label = W.label(self, "", "pageTitle")
        root.addWidget(self.title_label)

        # Name and triggers card
        header_card = W.frame(self, "card")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        h_layout.setSpacing(8)

        # Name row
        name_row = W.hbox()
        self.name_lbl = W.label(header_card, "")
        self.name_input = QLineEdit(header_card)
        self.name_input.setPlaceholderText("")
        name_row.addWidget(self.name_lbl)
        name_row.addWidget(self.name_input, 1)
        h_layout.addLayout(name_row)

        # Triggers row (Voice + Gesture)
        trig_row = W.hbox()
        self.voice_lbl = W.label(header_card, "")
        self.voice_input = QLineEdit(header_card)
        trig_row.addWidget(self.voice_lbl)
        trig_row.addWidget(self.voice_input, 1)

        self.gesture_lbl = W.label(header_card, "")
        self.gesture_combo = QComboBox(header_card)
        for val, _ in GESTURE_OPTIONS:
            self.gesture_combo.addItem(val, val)
        trig_row.addWidget(self.gesture_lbl)
        trig_row.addWidget(self.gesture_combo, 1)
        h_layout.addLayout(trig_row)

        root.addWidget(header_card)

        # Steps Table card
        table_card = W.frame(self, "card")
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        t_layout.setSpacing(8)

        self.steps_heading = W.section_title(table_card, "")
        t_layout.addWidget(self.steps_heading)

        self.table = QTableWidget(0, 3, table_card)
        self.table.setHorizontalHeaderLabels(["Action", "Target / Input", "Delay (s)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        t_layout.addWidget(self.table, 1)

        # Step actions toolbar
        step_bar = W.hbox()
        self.add_step_btn = W.button(table_card, "", "ghost", self._add_step_row)
        self.del_step_btn = W.button(table_card, "", "danger", self._remove_selected_step)
        step_bar.addWidget(self.add_step_btn)
        step_bar.addWidget(self.del_step_btn)
        step_bar.addWidget(W.spacer())
        t_layout.addLayout(step_bar)

        root.addWidget(table_card, 1)

        # Dialog buttons
        actions = W.hbox()
        self.save_btn = W.button(self, "", "primary", self._save_macro)
        self.cancel_btn = W.button(self, "", "ghost", self.reject)
        actions.addWidget(W.spacer())
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)

    def retranslate(self):
        is_edit = bool(self.editing_name)
        self.setWindowTitle(tr("macro.create_title") if not is_edit else self.editing_name)
        self.title_label.setText(tr("macro.create_title"))
        self.name_lbl.setText(tr("macro.name") + ":")
        self.name_input.setPlaceholderText(tr("macro.name_placeholder"))
        self.voice_lbl.setText(tr("macro.voice_trigger") + ":")
        self.voice_input.setPlaceholderText(tr("macro.voice_placeholder"))
        self.gesture_lbl.setText(tr("macro.gesture_trigger") + ":")
        self.steps_heading.setText(tr("macro.steps"))
        self.add_step_btn.setText(tr("macro.add_step"))
        self.del_step_btn.setText(tr("macro.remove_step"))
        self.save_btn.setText(tr("macro.save"))
        self.cancel_btn.setText(tr("common.cancel"))

        self.table.setHorizontalHeaderLabels([
            tr("macro.action"),
            tr("macro.target"),
            tr("macro.delay")
        ])

    def _add_step_row(self, action: str = "LAUNCH_APP", target: str = "", delay: float = 0.5):
        row = self.table.rowCount()
        self.table.insertRow(row)

        combo = QComboBox()
        for act_id, key in ACTION_TYPES:
            combo.addItem(f"{act_id} ({tr(key)})", act_id)
        idx = combo.findData(action)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, combo)

        target_input = QLineEdit(str(target) if target is not None else "")
        self.table.setCellWidget(row, 1, target_input)

        delay_spin = QDoubleSpinBox()
        delay_spin.setRange(0.0, 30.0)
        delay_spin.setSingleStep(0.2)
        delay_spin.setValue(float(delay))
        self.table.setCellWidget(row, 2, delay_spin)

    def _remove_selected_step(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _load_existing_macro(self, name: str):
        self.name_input.setText(name)
        v_trig, g_trig = self.macro_engine.get_macro_triggers(name)
        if v_trig:
            self.voice_input.setText(v_trig)
        if g_trig:
            idx = self.gesture_combo.findData(g_trig)
            if idx >= 0:
                self.gesture_combo.setCurrentIndex(idx)

        steps = self.macro_engine.get_macro_steps(name)
        for s in steps:
            self._add_step_row(s.get("action", "LAUNCH_APP"), s.get("target", ""), s.get("delay", 0.5))

    def _save_macro(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr("macro.title"), tr("macro.name_placeholder"))
            return

        steps = []
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 0)
            target_in = self.table.cellWidget(r, 1)
            delay_sp = self.table.cellWidget(r, 2)
            if combo and target_in and delay_sp:
                action = combo.currentData()
                target_val = target_in.text().strip()
                delay_val = delay_sp.value()
                steps.append({
                    "action": action,
                    "target": target_val,
                    "delay": delay_val
                })

        if not steps:
            QMessageBox.warning(self, tr("macro.title"), tr("macro.add_step"))
            return

        voice_trig = self.voice_input.text().strip() or None
        g_val = self.gesture_combo.currentData()
        gesture_trig = g_val if g_val != "NONE" else None

        self.macro_engine.add_or_update_macro(
            name=name,
            steps=steps,
            voice_trigger=voice_trig,
            gesture_trigger=gesture_trig
        )
        self.accept()


class MacroManagerDialog(QDialog):
    """Browse, run, create, edit and delete saved automation workflows."""

    def __init__(self, parent=None):
        super(MacroManagerDialog, self).__init__(parent)
        self.setFixedSize(720, 520)
        self.macro_engine = MacroEngine()
        self.orchestrator = CommandOrchestrator()

        theme.apply_to(self)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)

        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)
        self._refresh_list()
        self.retranslate()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 2, theme.PAD + 2, theme.PAD + 2, theme.PAD + 2)
        root.setSpacing(theme.GAP)

        self.title_label = W.label(self, "", "pageTitle")
        root.addWidget(self.title_label)

        content = W.hbox()

        # Saved macros list
        left_card = W.frame(self, "card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        left_layout.setSpacing(8)
        self.saved_heading = W.section_title(left_card, "")
        left_layout.addWidget(self.saved_heading)
        self.macro_list = QListWidget(left_card)
        self.macro_list.itemClicked.connect(self._on_item_selected)
        self.macro_list.itemDoubleClicked.connect(self._edit_selected)
        left_layout.addWidget(self.macro_list, 1)

        # Quick New Macro button under list
        self.new_btn = W.button(left_card, "", "secondary", self._create_new_macro)
        self.new_btn.setCursor(Qt.PointingHandCursor)
        left_layout.addWidget(self.new_btn)

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
        self.edit_btn = W.button(self, "✎ Edit", "ghost", self._edit_selected)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn = W.button(self, "", "danger", self._delete_selected)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn = W.button(self, "", "ghost", self.accept)
        self.close_btn.setCursor(Qt.PointingHandCursor)

        actions.addWidget(self.play_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.del_btn)
        actions.addWidget(W.spacer())
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("macro.title"))
        self.title_label.setText(tr("macro.heading"))
        self.saved_heading.setText(tr("macro.saved"))
        self.preview_heading.setText(tr("macro.preview"))
        self.new_btn.setText(tr("macro.new"))
        self.play_btn.setText(tr("macro.run"))
        self.del_btn.setText(tr("common.delete"))
        self.close_btn.setText(tr("common.close"))
        self._refresh_list()

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
        name = item.text()
        steps = self.macro_engine.get_macro_steps(name)
        v_trig, g_trig = self.macro_engine.get_macro_triggers(name)

        preview_lines = [f"=== {name} ==="]
        if v_trig:
            preview_lines.append(f"🎙 {tr('macro.voice_trigger')}: '{v_trig}'")
        if g_trig:
            preview_lines.append(f"✋ {tr('macro.gesture_trigger')}: {g_trig}")
        preview_lines.append(f"\n{tr('macro.steps')} ({len(steps)}):")

        for idx, step in enumerate(steps, 1):
            act = step.get("action", "")
            tgt = step.get("target", "")
            delay = step.get("delay", 0.5)
            preview_lines.append(f"  {idx}. [{act}]  ➜  {tgt}   (delay {delay}s)")

        self.steps_preview.setPlainText("\n".join(preview_lines))

    def _create_new_macro(self):
        dlg = MacroEditorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_list()

    def _edit_selected(self):
        item = self.macro_list.currentItem()
        if not item:
            return
        dlg = MacroEditorDialog(self, macro_name=item.text())
        if dlg.exec() == QDialog.Accepted:
            self._refresh_list()

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
