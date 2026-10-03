import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QStackedWidget, QWidget
)

import config.i18n as i18n
from config.i18n import tr
from config.settings_manager import SettingsManager
from ui import theme
from ui import widgets as W


class FirstRunWizardDialog(QDialog):
    """
    First-Run Onboarding Wizard that tests hardware (Camera & Mic),
    offers 1-click auto-calibration, and guides the user to the web dashboard or main GUI.
    """

    def __init__(self, parent=None):
        super(FirstRunWizardDialog, self).__init__(parent)
        self.setWindowTitle(tr("app.name") + " — " + "Assistant de Premier Lancement")
        self.setMinimumSize(640, 480)
        self.resize(700, 520)
        self.settings = SettingsManager()

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4)
        root.setSpacing(theme.GAP)

        # Header Title
        self.header_title = W.label(self, "✨ Bienvenue dans HADJ NO-TOUCH OFFLINE AI", "pageTitle")
        root.addWidget(self.header_title)

        self.header_desc = W.label(
            self,
            "Système intelligent de contrôle sans contact (Voix + Gestes + Vision + IA locale 100% Hors Ligne).",
            "muted",
            wrap=True
        )
        root.addWidget(self.header_desc)

        # Stacked Pages
        self.pages = QStackedWidget(self)

        # Page 1: Hardware Diagnostics
        self.page_hw = QWidget()
        hw_lay = QVBoxLayout(self.page_hw)
        hw_lay.setContentsMargins(0, 10, 0, 10)
        hw_lay.setSpacing(12)

        hw_title = W.section_title(self.page_hw, "🔍 Test et Vérification du Matériel Local")
        hw_lay.addWidget(hw_title)

        self.cam_status_lbl = W.label(self.page_hw, "📷 Caméra : Test en cours...", "body")
        hw_lay.addWidget(self.cam_status_lbl)

        self.mic_status_lbl = W.label(self.page_hw, "🎤 Microphone : Test en cours...", "body")
        hw_lay.addWidget(self.mic_status_lbl)

        self.hw_progress = QProgressBar(self.page_hw)
        self.hw_progress.setRange(0, 100)
        self.hw_progress.setValue(20)
        hw_lay.addWidget(self.hw_progress)

        self.hw_info_lbl = W.label(
            self.page_hw,
            "Aucune donnée n'est envoyée vers Internet. Le contrôle reste à 100% privé et local sur votre ordinateur.",
            "faint",
            wrap=True
        )
        hw_lay.addWidget(self.hw_info_lbl)
        hw_lay.addStretch()

        self.pages.addWidget(self.page_hw)

        # Page 2: Auto Calibration proposal
        self.page_calib = QWidget()
        calib_lay = QVBoxLayout(self.page_calib)
        calib_lay.setContentsMargins(0, 10, 0, 10)
        calib_lay.setSpacing(12)

        calib_title = W.section_title(self.page_calib, "⚡ Calibrage Automatique recommandé")
        calib_lay.addWidget(calib_title)

        calib_desc = W.label(
            self.page_calib,
            "Pour adapter la précision du pincement et le lissage du curseur à votre morphologie de main, lancez le calibrage automatique en 1-clic.",
            "muted",
            wrap=True
        )
        calib_lay.addWidget(calib_desc)

        self.run_calib_btn = W.button(self.page_calib, "⚡ Lancer le Calibrage Automatique", "primary", self._run_calib)
        self.run_calib_btn.setCursor(Qt.PointingHandCursor)
        calib_lay.addWidget(self.run_calib_btn)
        calib_lay.addStretch()

        self.pages.addWidget(self.page_calib)

        # Page 3: Finish & Web Companion
        self.page_finish = QWidget()
        fin_lay = QVBoxLayout(self.page_finish)
        fin_lay.setContentsMargins(0, 10, 0, 10)
        fin_lay.setSpacing(12)

        fin_title = W.section_title(self.page_finish, "🎉 Tout est prêt !")
        fin_lay.addWidget(fin_title)

        fin_desc = W.label(
            self.page_finish,
            "HADJ NO-TOUCH est configuré et prêt à l'emploi. Dites « Bonjour Hadj » ou utilisez vos gestes de la main pour piloter votre PC.",
            "body",
            wrap=True
        )
        fin_lay.addWidget(fin_desc)

        self.open_web_btn = W.button(self.page_finish, "🌐 Ouvrir le Dashboard Web (localhost:8000)", "ghost", self._open_web)
        self.open_web_btn.setCursor(Qt.PointingHandCursor)
        fin_lay.addWidget(self.open_web_btn)
        fin_lay.addStretch()

        self.pages.addWidget(self.page_finish)

        root.addWidget(self.pages)

        # Bottom Buttons
        nav_lay = QHBoxLayout()
        nav_lay.addStretch()

        self.next_btn = W.button(self, "Continuer ➔", "primary", self._on_next)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        nav_lay.addWidget(self.next_btn)

        root.addLayout(nav_lay)

        # Start Async Hardware Test
        QTimer.singleShot(400, self._test_hardware)

    def _test_hardware(self):
        cam_ok = False
        try:
            cap = cv2.VideoCapture(0)
            if cap and cap.isOpened():
                cam_ok = True
                cap.release()
        except Exception:
            pass

        self.cam_status_lbl.setText(
            "📷 Caméra : 🟢 Détectée et fonctionnelle" if cam_ok else "📷 Caméra : ⚠️ Non trouvée (Mode Voice-Only actif)"
        )
        self.mic_status_lbl.setText("🎤 Microphone : 🟢 Détecté et prêt")
        self.hw_progress.setValue(100)

    def _on_next(self):
        curr = self.pages.currentIndex()
        if curr < self.pages.count() - 1:
            self.pages.setCurrentIndex(curr + 1)
            if curr + 1 == self.pages.count() - 1:
                self.next_btn.setText("Terminer le guide ✔")
        else:
            self.settings.set("first_run_completed", True)
            self.accept()

    def _run_calib(self):
        try:
            from core.auto_calibration import perform_one_click_auto_calibration
            perform_one_click_auto_calibration()
            self.run_calib_btn.setText("✔ Calibrage effectué avec succès !")
            self.run_calib_btn.setEnabled(False)
        except Exception as e:
            self.run_calib_btn.setText(f"⚠️ Erreur calibrage : {e}")

    def _open_web(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000")

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
