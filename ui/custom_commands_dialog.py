from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QPushButton, QLabel, QFileDialog, QMessageBox, QHeaderView
)

import config.i18n as i18n
from config.i18n import tr
from core.custom_commands import CustomCommandManager
from ui import theme
from ui import widgets as W


class CustomCommandsDialog(QDialog):
    """
    Visual editor to define, import, and export custom voice/gesture commands
    mapped to Windows system actions, guarded by the Security Risk Engine.
    """

    def __init__(self, parent=None):
        super(CustomCommandsDialog, self).__init__(parent)
        self.setWindowTitle("🛠️ Constructeur de Commandes Personnalisées — HADJ NO-TOUCH")
        self.setMinimumSize(720, 520)
        self.resize(800, 580)
        self.manager = CustomCommandManager()

        theme.apply_to(self)
        self._init_ui()
        self._load_table()
        i18n.on_language_changed(self._on_language_changed)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4)
        root.setSpacing(theme.GAP)

        header = W.label(self, "🛠️ Éditeur de Commandes Personnalisées", "pageTitle")
        root.addWidget(header)

        desc = W.label(
            self,
            "Associez vos propres phrases vocales ou gestes à des actions système. Chaque commande est évaluée par le moteur de risque et inscrite au journal d'audit.",
            "muted",
            wrap=True
        )
        root.addWidget(desc)

        # Table of custom commands
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Nom", "Déclencheur", "Type d'action", "Cible / Action", "Niveau de risque"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table)

        # Form Card to Add New Command
        form_card = W.frame(self, "card")
        form_lay = QVBoxLayout(form_card)
        form_lay.setContentsMargins(theme.PAD, theme.PAD, theme.PAD, theme.PAD)
        form_lay.setSpacing(8)

        f_title = W.section_title(form_card, "➕ Ajouter une commande personnalisée")
        form_lay.addWidget(f_title)

        row1 = QHBoxLayout()
        self.name_input = QLineEdit(form_card)
        self.name_input.setPlaceholderText("Nom (ex: Ouvrir mon dossier projet)")
        row1.addWidget(self.name_input)

        self.trigger_input = QLineEdit(form_card)
        self.trigger_input.setPlaceholderText("Phrase vocale (ex: ouvre mon projet)")
        row1.addWidget(self.trigger_input)
        form_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.action_type_combo = QComboBox(form_card)
        self.action_type_combo.addItem("Ouvrir fichier/dossier (open_path)", "open_path")
        self.action_type_combo.addItem("Lancer application (launch_app)", "launch_app")
        self.action_type_combo.addItem("Raccourci clavier (shortcut)", "shortcut")
        self.action_type_combo.addItem("Saisir du texte (type_text)", "type_text")
        self.action_type_combo.addItem("Ouvrir URL Web (open_url)", "open_url")
        row2.addWidget(self.action_type_combo)

        self.action_target_input = QLineEdit(form_card)
        self.action_target_input.setPlaceholderText("Cible (ex: C:\\MonDossier ou win+e ou https://...)")
        row2.addWidget(self.action_target_input)

        self.risk_combo = QComboBox(form_card)
        self.risk_combo.addItem("Risque FAIBLE (LOW)", "LOW")
        self.risk_combo.addItem("Risque MOYEN (MEDIUM)", "MEDIUM")
        self.risk_combo.addItem("Risque ÉLEVÉ (HIGH)", "HIGH")
        self.risk_combo.addItem("Risque CRITIQUE (CRITICAL)", "CRITICAL")
        row2.addWidget(self.risk_combo)

        self.add_btn = W.button(form_card, "Ajouter", "primary", self._add_command)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.add_btn)

        form_lay.addLayout(row2)
        root.addWidget(form_card)

        # Actions & Import/Export Row
        act_row = QHBoxLayout()

        self.delete_btn = W.button(self, "🗑️ Supprimer sélection", "ghost", self._delete_selected)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        act_row.addWidget(self.delete_btn)

        act_row.addStretch()

        self.import_btn = W.button(self, "📥 Importer JSON", "ghost", self._import_json)
        self.import_btn.setCursor(Qt.PointingHandCursor)
        act_row.addWidget(self.import_btn)

        self.export_btn = W.button(self, "📤 Exporter JSON", "ghost", self._export_json)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        act_row.addWidget(self.export_btn)

        self.close_btn = W.button(self, "Fermer", "primary", self.accept)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        act_row.addWidget(self.close_btn)

        root.addLayout(act_row)

    def _load_table(self):
        self.table.setRowCount(0)
        for cmd in self.manager.commands:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(cmd.get("name", "")))
            self.table.setItem(r, 1, QTableWidgetItem(cmd.get("trigger_value", "")))
            self.table.setItem(r, 2, QTableWidgetItem(cmd.get("action_type", "")))
            self.table.setItem(r, 3, QTableWidgetItem(cmd.get("action_target", "")))
            risk_item = QTableWidgetItem(cmd.get("risk_level", "LOW"))
            risk_item.setData(Qt.UserRole, cmd.get("id"))
            self.table.setItem(r, 4, risk_item)

    def _add_command(self):
        name = self.name_input.text().strip()
        trigger = self.trigger_input.text().strip()
        target = self.action_target_input.text().strip()
        action_type = self.action_type_combo.currentData()
        risk = self.risk_combo.currentData()

        if not name or not trigger or not target:
            QMessageBox.warning(self, "Champ manquant", "Veuillez remplir le nom, la phrase de déclenchement et la cible de l'action.")
            return

        self.manager.add_command(name, "voice", trigger, action_type, target, risk)
        self.name_input.clear()
        self.trigger_input.clear()
        self.action_target_input.clear()
        self._load_table()

    def _delete_selected(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            item = self.table.item(curr_row, 4)
            if item:
                cmd_id = item.data(Qt.UserRole)
                self.manager.delete_command(cmd_id)
                self._load_table()

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter les commandes personnalisées", "custom_commands.json", "Fichiers JSON (*.json)")
        if path:
            if self.manager.export_json(path):
                QMessageBox.information(self, "Exportation réussie", f"Commandes exportées vers : {path}")

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer des commandes personnalisées", "", "Fichiers JSON (*.json)")
        if path:
            if self.manager.import_json(path):
                self._load_table()
                QMessageBox.information(self, "Importation réussie", "Les commandes ont été importées avec succès !")

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
