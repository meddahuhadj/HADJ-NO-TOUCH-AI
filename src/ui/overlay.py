"""الشريط الشفاف (HUD) أسفل الشاشة: حالة الاستماع، آخر ما سُمع، ونتيجة الأمر.
لا يأخذ التركيز ولا يعترض النقرات. ونافذة تأكيد ببطاقة أنيقة وأزرار كبيرة للخطرة.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

from ui.i18n import Tr
from ui.theme import Theme, theme
from ui.widgets import make_transparent, paint_card, paint_glow_dot

MARGIN = 22      # ارتفاع الفراغ أسفل الشاشة قبل إخفاء الهامش


class Overlay(QWidget):
    """بطاقة زجاجية صغيرة: سطران للرسالة + نقطة حالة + شريط جانبي ملوّن."""

    def __init__(self, tr: Tr, font_scale: float = 1.0, high_contrast: bool = False,
                 hide_after_s: float = 4.0):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        make_transparent(self)
        self.tr_ = tr
        self.th: Theme = theme(font_scale, high_contrast)
        t = self.th
        self.hide_after_ms = int(hide_after_s * 1000)
        self.state = "loading"
        self.sticky = False
        self.accent = ""

        self.line1 = QLabel()
        self.line2 = QLabel()
        self.line1.setFont(QFont("Segoe UI", t.pt(13.5), QFont.DemiBold))
        self.line2.setFont(QFont("Segoe UI", t.pt(11)))
        for lbl in (self.line1, self.line2):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: transparent;")
        self.line1.setStyleSheet(f"color: {t.c('text')}; background: transparent;")
        self.line2.setStyleSheet(f"color: {t.c('text_dim')}; background: transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(t.px(30), t.px(14), t.px(30), t.px(14))
        lay.setSpacing(t.px(3))
        lay.addWidget(self.line1)
        lay.addWidget(self.line2)
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        self.setFixedWidth(t.px(600))
        self._accent = QRectF()      # مكان نقطة الحالة داخل البطاقة

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_hide)

    # ---- الرسم ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = self.accent or self.th.state(self.state)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        paint_card(p, rect, self.th, radius=self.th.px(20), accent=color,
                   accent_side="right" if self.tr_.rtl else "left")
        # نقطة الحالة عند بداية السطر (يمين في العربية)
        r = self.th.px(5)
        cx = (rect.right() - self.th.px(24)) if self.tr_.rtl else (rect.left() + self.th.px(24))
        cy = self.line1.mapTo(self, self.line1.rect().topLeft()).y() + self.line1.height() / 2
        self._accent = QRectF(cx - r, cy - r, r * 2, r * 2)
        paint_glow_dot(p, self._accent.center(), r, color, 0.9)
        p.end()

    def _place(self):
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - MARGIN)

    # ---- الواجهة العامة ----
    def show_message(self, line1: str, line2: str = "", state: str | None = None,
                     sticky: bool = False, color: str | None = None):
        if state:
            self.state = state
        self.accent = {"ok": self.th.c("ok"), "err": self.th.c("err")}.get(color or "", "")
        self.line1.setText(line1)
        self.line2.setText(line2)
        self.line2.setVisible(bool(line2))
        self.line1.setStyleSheet(
            f"color: {self.th.c(color) if color in ('ok', 'err') else self.th.c('text')};"
            " background: transparent;")
        self.sticky = sticky
        self._place()
        self.show()
        self.raise_()
        self.update()
        if sticky:
            self._timer.stop()
        else:
            self._timer.start(self.hide_after_ms)

    def _auto_hide(self):
        if not self.sticky:
            self.hide()


class ConfirmWindow(QWidget):
    """تأكيد بصري ببطاقة داكنة وأزرار كبيرة (يمكن النقر عليها بمؤشر الإيماءات أيضاً)."""

    answered = Signal(bool)

    def __init__(self, tr: Tr, font_scale: float = 1.0, high_contrast: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus)
        make_transparent(self)
        self.tr_ = tr
        self.th = theme(font_scale, high_contrast)
        t = self.th
        self.setStyleSheet(t.qss())
        self._radius = t.px(22)
        self._margin = t.px(8)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        self._body = body

        badge = QLabel(body)
        badge.setText("!")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(t.px(52), t.px(52))
        badge.setStyleSheet(f"background: {t.alpha('warn', 0.14)};"
                            f" color: {t.c('warn')}; border: {t.hairline}px solid {t.alpha('warn', 0.5)};"
                            f" border-radius: {t.px(26)}px; font-size: {t.pt(24)}pt; font-weight: 700;")

        self.msg = QLabel()
        self.msg.setFont(QFont("Segoe UI", t.pt(14), QFont.DemiBold))
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setStyleSheet("background: transparent;")

        head = QWidget(body)
        head.setStyleSheet("background: transparent;")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(t.px(12))
        head_layout.addWidget(badge, 0, Qt.AlignTop)
        head_layout.addWidget(self.msg, 1)

        yes = QPushButton(tr("yes"))
        yes.setObjectName("confirmYes")
        no = QPushButton(tr("no"))
        no.setObjectName("confirmNo")
        for b in (yes, no):
            b.setProperty("role", "confirm")
            b.setFocusPolicy(Qt.NoFocus)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        yes.clicked.connect(lambda: self._answer(True))
        no.clicked.connect(lambda: self._answer(False))
        row = QHBoxLayout()
        row.setSpacing(t.px(12))
        row.addWidget(yes)
        row.addWidget(no)

        lay = QVBoxLayout(body)
        lay.setContentsMargins(t.px(28), t.px(24), t.px(28), t.px(22))
        lay.setSpacing(t.px(20))
        lay.addWidget(head)
        lay.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        outer.addWidget(body)
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        self.setFixedWidth(t.px(600))

    # ---- الرسم ----
    def _rect(self) -> QRectF:
        m = self._margin
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def _relayout(self) -> None:
        m = self._margin
        self._body.setGeometry(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_card(p, self._rect(), self.th, radius=self._radius, accent=self.th.c("warn"),
                   accent_side="right" if self.tr_.rtl else "left")
        p.end()

    # ---- الواجهة ----
    def ask(self, heard: str):
        self.msg.setText(self.tr_("confirm_prompt", heard=heard))
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.show()
        self.raise_()
        self.update()

    def _answer(self, value: bool):
        self.hide()
        self.answered.emit(value)
