from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import QDialog, QLabel, QTextEdit, QVBoxLayout

import config.i18n as i18n
from config.i18n import tr
from core.command_orchestrator import CommandOrchestrator
from core.event_bus import EventBus
from ui import theme
from ui import widgets as W

# (button key, command executed)
SCENARIOS = [
    ("demo.s1", "افتح Calculator ثم ارفع الصوت"),
    ("demo.s2", "افتحه"),
    ("demo.s3", "أين زر الإغلاق؟"),
    ("demo.s4", "افتح تبويب جديد ثم ابحث عن Arduino"),
    ("demo.s5", "اكتب مرحبا بكم في تطبيقي"),
    ("demo.s6", "Morning Setup"),
]


class _ResizeLabelFilter(QObject):
    """Keeps a word-wrapped QLabel filling the QPushButton that parents it."""

    def __init__(self, button, label):
        super().__init__(button)
        self._button = button
        self._label = label
        button.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            self._label.setGeometry(self._button.rect())
        return False


class DemoModeDialog(QDialog):
    """Interactive showcase of the touchless automation layer."""

    def __init__(self, parent=None):
        super(DemoModeDialog, self).__init__(parent)
        self.setMinimumSize(660, 560)
        self.resize(700, 620)
        self.orchestrator = CommandOrchestrator()
        self.event_bus = EventBus()

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

        # Scenario buttons
        self.scenario_card = W.frame(self, "card")
        scenario_layout = QVBoxLayout(self.scenario_card)
        scenario_layout.setContentsMargins(theme.PAD - 4, theme.PAD - 4, theme.PAD - 4, theme.PAD - 4)
        scenario_layout.setSpacing(7)
        self.scenario_heading = W.section_title(self.scenario_card, "")
        scenario_layout.addWidget(self.scenario_heading)

        self.scenario_buttons = []
        self._scenario_labels = {}
        self._scenario_filters = {}
        for key, command in SCENARIOS:
            btn = W.button(self.scenario_card, "", "ghost")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(0)
            btn.setMinimumHeight(46)
            # QPushButton cannot wrap its own caption, so a word-wrapped
            # QLabel is parented inside the button and follows its geometry.
            inner = QLabel(btn)
            inner.setWordWrap(True)
            inner.setTextFormat(Qt.PlainText)
            inner.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            inner.setContentsMargins(14, 8, 14, 8)
            inner.setStyleSheet("background: transparent; border: none;")
            self._scenario_filters[key] = _ResizeLabelFilter(btn, inner)
            self._scenario_labels[key] = inner
            btn.clicked.connect(lambda _, c=command: self._run_demo_command(c))
            self.scenario_buttons.append((key, btn))
            scenario_layout.addWidget(btn)
        root.addWidget(self.scenario_card)

        self.output_label = W.section_title(self, "")
        root.addWidget(self.output_label)

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(150)
        self.console.setStyleSheet(
            f"QTextEdit {{ color: {theme.SUCCESS}; background-color: {theme.CANVAS_DEEP}; }}"
        )
        root.addWidget(self.console, 1)

        actions = W.hbox()
        actions.addWidget(W.spacer())
        self.close_btn = W.button(self, "", "ghost", self.accept)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("demo.title"))
        self.title_label.setText(tr("demo.heading"))
        self.intro_label.setText(tr("demo.intro"))
        self.scenario_heading.setText(tr("demo.scenarios_title"))
        self.output_label.setText(tr("demo.output"))
        for key, btn in self.scenario_buttons:
            label = self._scenario_labels[key]
            label.setText(tr(key))
            # Grow the button so the wrapped caption is never cut off.
            needed = label.heightForWidth(max(btn.width() - 28, 80)) + 16
            btn.setMinimumHeight(max(46, needed))
        self.close_btn.setText(tr("common.close"))

        if not self.console.toPlainText():
            self.console.setPlainText(tr("demo.ready"))

    # ------------------------------------------------------------------ #

    def _run_demo_command(self, cmd_text: str):
        self.console.append(tr("demo.executing", command=cmd_text))
        result = self.orchestrator.execute_command_text(cmd_text, source="DEMO")
        self.console.append(tr("demo.result", result=result))

    def done(self, result: int):
        i18n.get_translator().remove_listener(self._on_language_changed)
        super(DemoModeDialog, self).done(result)
