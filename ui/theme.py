"""
Centralised visual design system for HADJ NO-TOUCH OFFLINE AI.

A single token palette plus one generated Qt stylesheet keeps every window,
dialog and overlay visually coherent. Typography automatically follows the
active interface language, and the layout mirrors for right-to-left languages
such as Arabic.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

import config.i18n as i18n

# --------------------------------------------------------------------------- #
# Design tokens
# --------------------------------------------------------------------------- #

CANVAS = "#060A12"            # Window background
CANVAS_DEEP = "#04070D"       # Gradient floor
SURFACE = "#0C1322"           # Card / panel fill
SURFACE_RAISED = "#111A2C"    # Elevated surface (inputs, hovered rows)
SURFACE_SUNK = "#080D18"      # Recessed surface (log views, viewport)
BORDER = "#1B2740"            # Hairline border
BORDER_STRONG = "#26344F"     # Emphasised border / hover edge
BORDER_FAINT = "#141D30"      # Divider

TEXT = "#E9EFF9"              # Primary text
TEXT_MUTED = "#93A4C0"        # Secondary text
TEXT_FAINT = "#5F7089"        # Tertiary text / captions

ACCENT = "#4CC9F0"            # Primary accent (cyan)
ACCENT_DEEP = "#0EA5E9"       # Accent pressed
ACCENT_SOFT = "#0B2C40"       # Accent tinted fill
VIOLET = "#A78BFA"            # Secondary accent
SUCCESS = "#34D399"
SUCCESS_SOFT = "#0A2E27"
WARNING = "#FBBF24"
WARNING_SOFT = "#33240A"
DANGER = "#F87171"
DANGER_DEEP = "#7F1D1D"
DANGER_SOFT = "#2A1013"

RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14

# Layout rhythm
GAP = 14
PAD = 22


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def alpha(hex_color: str, a: int) -> str:
    """Converts ``#RRGGBB`` into an ``rgba(...)`` string usable in Qt stylesheets."""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {a})"


def qcolor(hex_color: str, a: int = 255) -> QColor:
    """Returns a QColor for the given token, optionally with reduced opacity."""
    c = QColor(hex_color)
    c.setAlpha(a)
    return c


def ui_font(size: int = 10, weight: int = QFont.Normal, mono: bool = False) -> QFont:
    """Builds a QFont bound to the language-appropriate family stack."""
    families = (i18n.MONO_STACK if mono else i18n.font_stack()).split(",")
    families = [f.strip().strip("'") for f in families]

    available = set(QFontDatabase.families())
    family = next((f for f in families if f in available), None)
    if family is None:
        family = QFont().defaultFamily()

    font = QFont(family, size)
    font.setWeight(weight)
    return font


def apply_direction(widget: QWidget) -> None:
    """Mirrors the widget layout for right-to-left languages."""
    widget.setLayoutDirection(
        Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight
    )


def repolish(widget: QWidget) -> None:
    """Re-evaluates a widget's stylesheet after a dynamic property change."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #

def stylesheet() -> str:
    """Builds the full application stylesheet for the active language."""
    fonts = i18n.font_stack()
    mono = i18n.MONO_STACK
    align = "right" if i18n.is_rtl() else "left"

    return f"""
/* ============================ Base ============================ */
QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: {fonts};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {CANVAS}, stop:1 {CANVAS_DEEP});
}}

QMainWindow::separator {{
    background: {BORDER_FAINT};
    width: 1px;
    height: 1px;
}}

QToolTip {{
    background-color: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_SM}px;
    padding: 6px 9px;
}}

/* ============================ Surfaces ============================ */
QFrame#card, QFrame.card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {SURFACE}, stop:1 #0A1120);
    border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px;
}}

QFrame#panel, QFrame.panel {{
    background-color: {SURFACE_SUNK};
    border: 1px solid {BORDER_FAINT};
    border-radius: {RADIUS_MD}px;
}}

QFrame#notice {{
    background-color: {ACCENT_SOFT};
    border: 1px solid {alpha(ACCENT, 70)};
    border-left: 3px solid {ACCENT};
    border-radius: {RADIUS_MD}px;
}}

QFrame#divider {{
    background-color: {BORDER_FAINT};
    border: none;
    max-height: 1px;
}}

/* ============================ Typography ============================ */
QLabel#brandTitle, QLabel.brand-title {{
    font-size: 21px;
    font-weight: 700;
    color: {TEXT};
    background: transparent;
}}

QLabel#brandSubtitle, QLabel.brand-subtitle {{
    font-size: 12px;
    font-weight: 400;
    color: {TEXT_FAINT};
    background: transparent;
}}

QLabel#sectionTitle, QLabel.section-title {{
    font-size: 10px;
    font-weight: 700;
    color: {TEXT_FAINT};
    letter-spacing: 1.4px;
    background: transparent;
}}

QLabel#pageTitle, QLabel.page-title {{
    font-size: 19px;
    font-weight: 700;
    color: {ACCENT};
    background: transparent;
}}

QLabel#metric, QLabel.metric {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
    background: transparent;
}}

QLabel#muted, QLabel.muted {{
    font-size: 12px;
    color: {TEXT_MUTED};
    background: transparent;
}}

QLabel#faint, QLabel.faint {{
    font-size: 11px;
    color: {TEXT_FAINT};
    background: transparent;
}}

QLabel#mono, QLabel.mono {{
    font-family: {mono};
    font-size: 12px;
    color: {TEXT_MUTED};
    background: transparent;
}}

/* ============================ Badges ============================ */
QLabel#badgeAccent, QLabel.badge-accent {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid {alpha(ACCENT, 90)};
    border-radius: {RADIUS_SM}px;
    padding: 4px 11px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}

QLabel#badgeSuccess, QLabel.badge-success {{
    background-color: {SUCCESS_SOFT};
    color: {SUCCESS};
    border: 1px solid {alpha(SUCCESS, 90)};
    border-radius: {RADIUS_SM}px;
    padding: 4px 11px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}

QLabel#badgeNeutral, QLabel.badge-neutral {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_SM}px;
    padding: 4px 11px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}

/* ============================ Buttons ============================ */
QPushButton {{
    background-color: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    padding: 9px 16px;
    font-size: 12px;
    font-weight: 600;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: #16223A;
    border-color: {alpha(ACCENT, 110)};
    color: #FFFFFF;
}}
QPushButton:pressed {{
    background-color: #0D1626;
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    border-color: {BORDER_FAINT};
    background-color: {SURFACE};
}}
QPushButton:focus {{
    border-color: {ACCENT};
}}

QPushButton#primary, QPushButton.primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ACCENT}, stop:1 {ACCENT_DEEP});
    color: #04121C;
    border: 1px solid {ACCENT};
    font-weight: 700;
}}
QPushButton#primary:hover, QPushButton.primary:hover {{
    background: #6FD6F7;
    color: #04121C;
    border-color: #6FD6F7;
}}
QPushButton#primary:pressed, QPushButton.primary:pressed {{
    background: {ACCENT_DEEP};
}}

QPushButton#danger, QPushButton.danger {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #E05252, stop:1 {DANGER_DEEP});
    color: #FFFFFF;
    border: 1px solid #E05252;
    font-weight: 700;
}}
QPushButton#danger:hover, QPushButton.danger:hover {{
    background: #EF6A6A;
    border-color: #EF6A6A;
}}

QPushButton#ghost, QPushButton.ghost {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
}}
QPushButton#ghost:hover, QPushButton.ghost:hover {{
    color: {ACCENT};
    border-color: {alpha(ACCENT, 110)};
    background-color: {ACCENT_SOFT};
}}

/* Small toggle pill used for the sensor on/off switches */
QPushButton#pill, QPushButton.pill {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 999px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#pill:hover, QPushButton.pill:hover {{
    border-color: {alpha(ACCENT, 110)};
    color: {TEXT};
}}
QPushButton#pillOn, QPushButton.pill-on {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid {alpha(ACCENT, 130)};
    border-radius: 999px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#pillOn:hover, QPushButton.pill-on:hover {{
    background-color: #0F3E58;
    color: #7FDCFA;
}}

/* ============================ Inputs ============================ */
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget, QTableWidget {{
    background-color: {SURFACE_SUNK};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_MD}px;
    color: {TEXT};
    padding: 9px 12px;
    selection-background-color: {alpha(ACCENT, 90)};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {alpha(ACCENT, 160)};
    background-color: #0A1120;
}}
QLineEdit::placeholder {{
    color: {TEXT_FAINT};
}}
QLineEdit:disabled {{
    color: {TEXT_FAINT};
}}

QTextEdit, QPlainTextEdit {{
    font-family: {mono};
    font-size: 12px;
}}

QListWidget::item {{
    padding: 8px 10px;
    border-radius: {RADIUS_SM}px;
    margin: 1px 3px;
}}
QListWidget::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
}}
QListWidget::item:hover {{
    background-color: {SURFACE_RAISED};
}}

/* ============================ Table ============================ */
QTableWidget {{
    gridline-color: {BORDER_FAINT};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 7px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 9px 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-align: {align};
}}
QTableCornerButton::section {{
    background-color: {SURFACE};
    border: none;
}}

/* ============================ Combo box ============================ */
QComboBox {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    color: {TEXT};
    padding: 8px 30px 8px 12px;
    font-size: 12px;
    font-weight: 600;
    min-width: 108px;
}}
QComboBox:hover {{
    border-color: {alpha(ACCENT, 120)};
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    width: 0;
    height: 0;
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    padding: 5px;
    outline: none;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT};
    font-family: {fonts};
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 12px;
    border-radius: {RADIUS_SM}px;
    min-height: 22px;
}}

/* ============================ Checks & radios ============================ */
QCheckBox, QRadioButton {{
    color: {TEXT};
    font-size: 13px;
    spacing: 10px;
    padding: 5px 2px;
    background: transparent;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid {BORDER_STRONG};
    background-color: {SURFACE_SUNK};
}}
QCheckBox::indicator {{
    border-radius: {RADIUS_SM}px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {alpha(ACCENT, 150)};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}
QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border: 5px solid {SURFACE_SUNK};
    outline: 1px solid {ACCENT};
}}

/* ============================ Progress & sliders ============================ */
QProgressBar {{
    background-color: {SURFACE_SUNK};
    border: 1px solid {BORDER_FAINT};
    border-radius: 999px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT_DEEP}, stop:1 {ACCENT});
    border-radius: 999px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {SURFACE_SUNK};
    border: 1px solid {BORDER_FAINT};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_DEEP};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: 2px solid {CANVAS};
    width: 15px;
    height: 15px;
    margin: -7px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #7FDCFA;
}}

/* ============================ Scrollbars ============================ */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {alpha(ACCENT, 130)};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {alpha(ACCENT, 130)};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
    border: none;
    background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ============================ Menus ============================ */
QMenu {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 22px 8px 14px;
    border-radius: {RADIUS_SM}px;
    font-size: 12px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
}}
QMenu::item:disabled {{
    color: {TEXT_FAINT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_FAINT};
    margin: 5px 8px;
}}
"""


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #

def apply_theme(app: Optional[QApplication] = None) -> None:
    """Applies the theme globally to the QApplication and refreshes fonts."""
    app = app or QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(stylesheet())
    app.setFont(ui_font(10))


def apply_to(widget: QWidget, extra: str = "") -> QWidget:
    """Applies the theme to a single widget and mirrors it for RTL languages."""
    widget.setStyleSheet((stylesheet() + extra).strip())
    apply_direction(widget)
    return widget
