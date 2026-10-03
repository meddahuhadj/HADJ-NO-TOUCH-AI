"""
Small widget factory used across the HADJ interface.

Centralising construction keeps spacing, object names and the translatable
labels consistent between the main window, the dialogs and the overlays.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

import config.i18n as i18n
from ui import theme


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #

def frame(parent: Optional[QWidget] = None, kind: str = "card") -> QFrame:
    """Returns a themed surface frame (``card``, ``panel`` or ``notice``)."""
    box = QFrame(parent)
    box.setObjectName(kind)
    box.setProperty("class", kind)
    return box


def label(
    parent: Optional[QWidget],
    text: str = "",
    variant: str = "",
    align: Optional[Qt.AlignmentFlag] = None,
    wrap: bool = False,
) -> QLabel:
    """Returns a themed QLabel with an optional style variant."""
    lbl = QLabel(text, parent)
    if variant:
        lbl.setObjectName(variant)
        lbl.setProperty("class", variant)
    if align is not None:
        lbl.setAlignment(align)
    # Headings must always be able to reflow, otherwise longer French or
    # English strings are elided instead of wrapping.
    lbl.setWordWrap(True if (wrap or variant == "pageTitle") else False)
    lbl.setMinimumWidth(0)
    if variant:
        # Object-name selectors can be shadowed by parent stylesheets.
        lbl.setStyleSheet("")
    return lbl


def section_title(parent: QWidget, text: str) -> QLabel:
    """Small uppercase caption used above panels and lists.

    Wrapping is enabled so that long localised titles (notably French and
    English) grow to a second line instead of being elided.
    """
    lbl = label(parent, text, "sectionTitle")
    lbl.setText(text)
    lbl.setWordWrap(True)
    lbl.setMinimumWidth(0)
    return lbl


def button(
    parent: Optional[QWidget],
    text: str,
    kind: str = "",
    on_click=None,
) -> QPushButton:
    """Returns a themed QPushButton; ``kind`` maps to a theme variant."""
    btn = QPushButton(text, parent)
    if kind:
        btn.setObjectName(kind)
        btn.setProperty("class", kind)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


def switch_button(
    parent: QWidget,
    text: str,
    on_click=None,
) -> QPushButton:
    """A pill toggle used for the voice / gesture / vision switches."""
    btn = QPushButton(text, parent)
    btn.setObjectName("pill")
    btn.setProperty("class", "pill")
    btn.setCursor(Qt.PointingHandCursor)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


def set_switch_state(btn: QPushButton, enabled: bool) -> None:
    """Applies the active/inactive appearance to a pill toggle."""
    name = "pillOn" if enabled else "pill"
    btn.setObjectName(name)
    btn.setProperty("class", name)
    theme.repolish(btn)


def separator(parent: Optional[QWidget] = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("divider")
    line.setProperty("class", "divider")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def spacer() -> QWidget:
    """Flexible horizontal spacer."""
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return widget


# --------------------------------------------------------------------------- #
# Composites
# --------------------------------------------------------------------------- #

def panel_with_title(
    parent: QWidget,
    title: str,
    spacing: int = 8,
) -> tuple[QFrame, QVBoxLayout, QLabel]:
    """Card with a section caption on top.

    Returns the frame, its layout and the caption label so callers can keep a
    handle on the caption and retranslate it later.
    """
    card = frame(parent, "card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(theme.PAD - 6, theme.PAD - 6, theme.PAD - 6, theme.PAD - 6)
    lay.setSpacing(spacing)
    caption = section_title(card, title)
    caption.setVisible(bool(title))
    lay.addWidget(caption)
    return card, lay, caption


def hbox(spacing: int = theme.GAP, margins: Optional[tuple] = None) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    if margins is not None:
        lay.setContentsMargins(*margins)
    return lay


def vbox(spacing: int = theme.GAP, margins: Optional[tuple] = None) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    if margins is not None:
        lay.setContentsMargins(*margins)
    return lay


def stat_chip(parent: QWidget, key: str, value: str, variant: str = "badgeNeutral") -> QLabel:
    """Small badge combining a caption and a value."""
    chip = QLabel(value, parent)
    chip.setObjectName(variant)
    chip.setProperty("class", variant)
    chip.setToolTip(key)
    return chip
