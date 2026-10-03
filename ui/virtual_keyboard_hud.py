from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import config.i18n as i18n
from config.i18n import tr
from automation.windows_control import WindowsControlEngine
from ui import theme

# Non-alphanumeric keys, rendered in the bottom action row.
_ACTION_KEYS = ["Bksp", "Tab", "Enter", "Copy", "Paste", "Undo", "DelWord", "NextLine", "Space"]

_LAYOUT_ROWS = [
    "1234567890",
    "QWERTYUIOP",
    "ASDFGHJKL",
    "ZXCVBNM,.",
]


class VirtualKeyboardHUD(QWidget):
    """
    On-screen touchless keyboard with large keys and quick voice-editing shortcuts.
    Every key caption follows the selected interface language.
    """

    def __init__(self, parent=None):
        super(VirtualKeyboardHUD, self).__init__(parent)
        self.win = WindowsControlEngine()

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.Tool | Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(720, 300)

        theme.apply_to(self)
        self._init_ui()
        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("keyboardShell")
        self.container.setStyleSheet(
            f"QWidget#keyboardShell {{"
            f"background-color: rgba(8, 12, 22, 246);"
            f"border: 1px solid {theme.alpha(theme.ACCENT, 150)};"
            f"border-radius: 18px;"
            f"}}"
        )
        shell = QVBoxLayout(self.container)
        shell.setContentsMargins(16, 13, 16, 15)
        shell.setSpacing(9)

        # Header
        header = QHBoxLayout()
        self.heading_label = QLabel(self.container)
        self.heading_label.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 10px; font-weight: 800;"
            "letter-spacing: 1.4px; background: transparent;"
        )
        header.addWidget(self.heading_label)
        header.addStretch()
        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedSize(28, 24)
        self.close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.DANGER_SOFT};"
            f"color: {theme.DANGER}; border: 1px solid {theme.alpha(theme.DANGER, 160)};"
            "border-radius: 7px; font-weight: 700; }}"
            f"QPushButton:hover {{ background-color: {theme.DANGER_DEEP}; color: #FFFFFF; }}"
        )
        self.close_btn.clicked.connect(self.hide)
        header.addWidget(self.close_btn)
        shell.addLayout(header)

        # Alphanumeric grid
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        self._char_buttons = {}
        for row_index, row in enumerate(_LAYOUT_ROWS):
            for col_index, char in enumerate(row):
                btn = self._make_key(self.container, char, special=False)
                self.grid.addWidget(btn, row_index, col_index)
                self._char_buttons[char] = btn
        shell.addLayout(self.grid)

        # Action row: 5 columns x 2 rows so long localised labels never
        # overflow the panel horizontally.
        self.action_buttons = {}
        actions = QGridLayout()
        actions.setSpacing(6)
        column_count = 5
        slots = len(_ACTION_KEYS)
        for index, token in enumerate(_ACTION_KEYS):
            row = index // column_count
            col = index % column_count
            if token == "Space":
                row = 1
                col = 0
                span = column_count
            else:
                span = 1
            btn = self._make_key(self.container, token, special=True)
            actions.addWidget(btn, row, col, 1, span)
            self.action_buttons[token] = btn
        if slots % column_count:
            actions.setRowStretch(slots // column_count + 1, 1)
        else:
            actions.setRowStretch(slots // column_count, 1)
        shell.addLayout(actions)

        root.addWidget(self.container)

    def _make_key(self, parent: QWidget, token: str, special: bool) -> QPushButton:
        btn = QPushButton(token, parent)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(40)
        if special:
            btn.setMinimumWidth(84)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {theme.SURFACE};"
                f"color: {theme.ACCENT}; border: 1px solid {theme.BORDER};"
                "border-radius: 9px; font-size: 12px; font-weight: 600; }}"
                f"QPushButton:hover {{ background-color: {theme.ACCENT_SOFT};"
                f"color: #FFFFFF; border-color: {theme.ACCENT}; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {theme.SURFACE_RAISED};"
                f"color: {theme.TEXT}; border: 1px solid {theme.BORDER};"
                "border-radius: 9px; font-size: 14px; font-weight: 600; }}"
                f"QPushButton:hover {{ background-color: {theme.ACCENT_SOFT};"
                f"color: {theme.ACCENT}; border-color: {theme.ACCENT}; }}"
            )
        btn.clicked.connect(lambda _, t=token: self._on_key_clicked(t))
        return btn

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, code: str):
        theme.apply_to(self)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("kb.title"))
        self.heading_label.setText(tr("kb.heading").upper())
        for token, btn in self.action_buttons.items():
            btn.setText(self._caption(token))

    def _caption(self, token: str) -> str:
        mapping = {
            "Bksp": "kb.bksp",
            "Tab": "kb.tab",
            "Enter": "kb.enter",
            "Space": "kb.space",
            "Copy": "kb.copy",
            "Paste": "kb.paste",
            "Undo": "kb.undo",
            "DelWord": "kb.del_word",
            "NextLine": "kb.next_line",
        }
        key = mapping.get(token)
        return tr(key) if key else token

    # ------------------------------------------------------------------ #

    def _on_key_clicked(self, key: str):
        if key == "Bksp":
            self.win.press_key("backspace")
        elif key == "Tab":
            self.win.press_key("tab")
        elif key in ("Enter", "NextLine"):
            self.win.press_key("enter")
        elif key == "Space":
            self.win.press_key("space")
        elif key == "Copy":
            self.win.copy()
        elif key == "Paste":
            self.win.paste()
        elif key == "Undo":
            self.win.undo()
        elif key == "DelWord":
            import pyautogui
            pyautogui.hotkey("ctrl", "backspace")
        else:
            self.win.type_text(key.lower())
