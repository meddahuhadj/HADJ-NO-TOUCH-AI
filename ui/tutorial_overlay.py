from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QStackedWidget

import config.i18n as i18n
from config.i18n import tr
from ui import theme
from ui import widgets as W


STEPS = [
    {
        "title": "👆 1. Déplacer le curseur",
        "icon": "👆",
        "desc": "Levez l'index vers la caméra, gardez les autres doigts repliés. Le curseur virtuel suit le bout de votre index avec un lissage anti-tremblement.",
        "tip": "Astuce : La boîte de portée active s'adapte à la taille de votre écran."
    },
    {
        "title": "👌 2. Effectuer un clic (Pincement)",
        "icon": "👌",
        "desc": "Rapprochez le bout de votre pouce et de votre index jusqu'à toucher. Un clic gauche Windows est émis instantanément sous votre pointeur.",
        "tip": "Astuce : Un double pincement rapide déclenche un double-clic."
    },
    {
        "title": "✌️ 3. Défiler la page",
        "icon": "✌️",
        "desc": "Levez l'index et le majeur ensemble, puis déplacez votre main vers le haut ou le bas pour faire défiler des documents ou pages Web.",
        "tip": "Astuce : La vitesse de défilement est réglable dans le panneau d'accessibilité."
    },
    {
        "title": "👍 4. Confirmer une action sensible",
        "icon": "👍",
        "desc": "Lorsqu'une demande de sécurité s'affiche à l'écran (Niveau de risque Élevé), levez le pouce pour valider la confirmation en toute sécurité.",
        "tip": "Astuce : Vous pouvez aussi dire « Nعم » ou « Confirm » à la voix."
    },
    {
        "title": "✊ 5. Arrêt d'urgence (Kill Switch)",
        "icon": "✊",
        "desc": "Maintenez le poing fermé pendant 2 secondes pour interrompre immédiatement toutes les automatisations du système PC.",
        "tip": "Astuce : Le raccourci clavier Ctrl + Alt + Echap déclenche aussi le Kill Switch."
    }
]


class InteractiveTutorialOverlay(QDialog):
    """
    Step-by-step interactive tutorial overlay that explains hand gestures
    and touchless controls. Can be re-launched from settings or demo dialog.
    """

    def __init__(self, parent=None):
        super(InteractiveTutorialOverlay, self).__init__(parent)
        self.setWindowTitle("Tutoriel Interactif — HADJ NO-TOUCH AI")
        self.setMinimumSize(580, 420)
        self.resize(640, 460)

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4)
        root.setSpacing(theme.GAP)

        header = W.label(self, "🎓 Tutoriel Pas-à-Pas : Guide des Gestes", "pageTitle")
        root.addWidget(header)

        self.stack = QStackedWidget(self)

        for step in STEPS:
            card = W.frame(self, "card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(theme.PAD, theme.PAD, theme.PAD, theme.PAD)
            lay.setSpacing(12)

            t_lbl = W.section_title(card, step["title"])
            lay.addWidget(t_lbl)

            d_lbl = W.label(card, step["desc"], "body", wrap=True)
            d_lbl.setStyleSheet(f"font-size: 14px; color: {theme.TEXT}; line-height: 1.5;")
            lay.addWidget(d_lbl)

            tip_lbl = W.label(card, f"💡 {step['tip']}", "faint", wrap=True)
            tip_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-weight: 600; font-size: 12px;")
            lay.addWidget(tip_lbl)
            lay.addStretch()

            self.stack.addWidget(card)

        root.addWidget(self.stack)

        # Nav bar
        nav = QHBoxLayout()
        self.prev_btn = W.button(self, "⬅ Précédent", "ghost", self._prev_step)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        nav.addWidget(self.prev_btn)

        self.step_counter = W.label(self, "Étape 1 / 5", "muted")
        nav.addWidget(self.step_counter)
        nav.addStretch()

        self.next_btn = W.button(self, "Suivant ➔", "primary", self._next_step)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        nav.addWidget(self.next_btn)

        root.addLayout(nav)
        self._update_nav_state()

    def _prev_step(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav_state()

    def _next_step(self):
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_nav_state()
        else:
            self.accept()

    def _update_nav_state(self):
        idx = self.stack.currentIndex()
        total = self.stack.count()
        self.prev_btn.setEnabled(idx > 0)
        self.step_counter.setText(f"Étape {idx + 1} / {total}")
        if idx == total - 1:
            self.next_btn.setText("J'ai compris ! ✔")
        else:
            self.next_btn.setText("Suivant ➔")

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
