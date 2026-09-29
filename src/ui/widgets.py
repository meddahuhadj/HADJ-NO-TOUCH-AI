"""مكوّنات واجهة مشتركة: بطاقات، كرة الحالة، شرائح، وأدوات الرسم بالـQPainter.

كل شيء هنا يحترم `Theme` (وضع داكن أو تباين عالٍ) و`font_scale`.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from ui.theme import Theme, theme

# الحالات التي "تتنفّس" (نبض خفيف) لأنها تنتظر شيئاً من المستخدم
PULSING_STATES = {"ready", "armed", "dictation", "loading", "grid"}


# ------------------------------------------------------------------ أدوات رسم
def make_transparent(w: QWidget) -> None:
    """نافذة بطاقة: شفافية فعلية.

    ``WA_TranslucentBackground`` وحده لا يكفي: Qt يظلّ يرسم لون ``QPalette::Window``
    فيبقى المستطيل معتماً. لا بدّ من جعل لوني Window وBase شفافين معاً.
    """
    from PySide6.QtGui import QPalette
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    w.setAttribute(Qt.WA_ShowWithoutActivating, True)
    pal = w.palette()
    pal.setColor(QPalette.Window, Qt.transparent)
    pal.setColor(QPalette.Base, Qt.transparent)
    w.setPalette(pal)
    w.setAutoFillBackground(False)


def paint_shadow(p: QPainter, rect: QRectF, radius: float, spread: int = 6,
                 alpha: float = 0.28) -> None:
    """ظل ناعم بالطبقات (بديل خفيف عن QGraphicsDropShadowEffect)."""
    p.setPen(Qt.NoPen)
    for i in range(spread, 0, -1):
        a = alpha * (1 - i / (spread + 1.0)) ** 1.6
        p.setBrush(QColor(0, 0, 0, int(round(255 * a))))
        p.drawRoundedRect(rect.adjusted(-i, -i * 0.6, i, i * 1.6), radius + i, radius + i)


def paint_card(p: QPainter, rect: QRectF, t: Theme, radius: int | None = None,
               accent: str | None = None, shadow: bool = True,
               accent_side: str = "left") -> None:
    """بطاقة زجاجية فخمة: ظل عالي الدقة + خلفية تدرجية داكنة + حد شعري ملوّن + لمعة علوية + شريط حالة."""
    r = float(t.radius if radius is None else radius)
    if shadow and not t.high_contrast:
        paint_shadow(p, rect, r, spread=8, alpha=0.32)
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if t.high_contrast:
        g.setColorAt(0.0, QColor("#0b0b0b"))
        g.setColorAt(1.0, QColor("#000000"))
    else:
        g.setColorAt(0.0, QColor("#141f38"))
        g.setColorAt(0.6, QColor("#0e172a"))
        g.setColorAt(1.0, QColor("#090f1d"))
    p.setBrush(QBrush(g))
    pen_color = QColor(t.c("line_strong") if t.high_contrast else t.c("line"))
    if accent:
        pen_color = QColor(accent)
    p.setPen(QPen(pen_color, t.hairline))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

    # لمعة علوية رفيعة تعطي إحساس الزجاج البلوري
    if not t.high_contrast:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(QRectF(rect.left() + r * 0.4, rect.top() + 1, rect.width() - r * 0.8,
                                 max(1, t.px(1.5))), r * 0.6, r * 0.6)
    if accent:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(accent), max(2.5, t.px(3.0))))
        bar = max(3, t.px(3.5))
        x = rect.right() - bar - 1 if accent_side == "right" else rect.left() + 1
        side = QRectF(x, rect.top() + r * 0.6, bar, rect.height() - r * 1.2)
        p.drawRoundedRect(side, bar / 2, bar / 2)


def paint_glow_dot(p: QPainter, center: QPointF, radius: float, color: str,
                   strength: float = 1.0) -> None:
    """نقطة ضوء: هالة متوهجة ناعمة + لبّ صلب."""
    g = QRadialGradient(center, radius * 3.0)
    c = QColor(color)
    c.setAlphaF(0.35 * strength)
    g.setColorAt(0.0, c)
    c2 = QColor(color)
    c2.setAlphaF(0.0)
    g.setColorAt(1.0, c2)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(center, radius * 3.0, radius * 3.0)
    p.setBrush(QColor(color))
    p.drawEllipse(center, radius, radius)


def chip_qss(t: Theme, fg: str, bold: bool = True) -> str:
    """نمط شريحة صغيرة (نص على خلفية ملوّنة خفيفة) — للمؤشرات والحالات."""
    bg = t.alpha(fg, 0.18) if not t.high_contrast else "transparent"
    border = t.alpha(fg, 0.50) if not t.high_contrast else fg
    return (f"background-color: {bg}; color: {fg}; border: {t.hairline}px solid {border}; "
            f"border-radius: {t.px(12)}px; padding: {t.px(4)}px {t.px(12)}px; "
            f"font-weight: {'700' if bold else '600'}; font-size: {t.pt(9.5)}pt;")


# ------------------------------------------------------------------ عناصر جاهزة
class Card(QFrame):
    """بطاقة بسمة (property = card) ليأخذ مظهر الأسطح من QSS."""

    def __init__(self, parent: QWidget | None = None, inset: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("inset" if inset else "card", True)


class Rule(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("rule", True)
        self.setFixedHeight(1)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())


class StateOrb(QWidget):
    """كرة الحالة: هالة مزدوجة تتنفّس وتنبض حول لبّ كريستالي ملوّن."""

    def __init__(self, t: Theme, diameter: int = 40, state: str = "ready",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.t = t
        self.d = diameter
        self._state = state
        self._phase = 0.0
        self.setFixedSize(diameter, diameter)
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._sync()

    # ---- واجهة ----
    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._sync()
            self.update()

    def _sync(self) -> None:
        wants = self._state in PULSING_STATES and not self.t.high_contrast
        if wants != self._timer.isActive():
            (self._timer.start if wants else self._timer.stop)()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.045) % 1.0
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    # ---- الرسم ----
    def paintEvent(self, _e) -> None:
        t = self.t
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = t.state(self._state)
        center = QPointF(self.width() / 2, self.height() / 2)
        r = self.d / 2 - t.px(3)
        wave = (1 - math.cos(self._phase * 2 * math.pi)) / 2      # 0→1 ناعم

        if not t.high_contrast:
            # هالة ناعمة خارجية
            halo = QRadialGradient(center, r * 2.4)
            base = QColor(c)
            base.setAlphaF(0.38 + 0.22 * wave)
            halo.setColorAt(0.0, base)
            edge = QColor(c)
            edge.setAlphaF(0.0)
            halo.setColorAt(1.0, edge)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(center, r * 2.4, r * 2.4)

            # موجة نبض حلقة
            ring = QColor(c)
            ring.setAlphaF(0.35 + 0.35 * (1 - wave))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(ring, max(1.2, t.px(1.6))))
            pulse_r = r + t.px(2.0) + t.px(3.5) * wave
            p.drawEllipse(center, pulse_r, pulse_r)

        # اللب المضيء
        g = QRadialGradient(center - QPointF(0, r * 0.35), r * 1.5)
        col = QColor(c)
        g.setColorAt(0.0, col.lighter(135))
        g.setColorAt(0.8, col)
        g.setColorAt(1.0, col.darker(115))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(center, r, r)
        if not t.high_contrast:   # لمعة بلورية علوية
            p.setBrush(QColor(255, 255, 255, 75))
            p.drawEllipse(QPointF(center.x() - r * 0.3, center.y() - r * 0.42), r * 0.36, r * 0.24)
        p.end()


class StepDots(QWidget):
    """مؤشر خطوات (نقاط): يظهر موضع المستخدم في المعايرة."""

    def __init__(self, t: Theme, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.t = t
        self.count = max(1, count)
        self.current = 0
        self.ok = True
        self.setFixedHeight(t.px(10))

    def set_current(self, index: int) -> None:
        self.current = index
        self.update()

    def set_ok(self, ok: bool) -> None:
        self.ok = ok
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.t.px(3)
        w = r * 2 + self.t.px(6)
        step = w + self.t.px(6)
        x = (self.width() - (step * self.count - self.t.px(6))) / 2
        y = self.height() / 2
        for i in range(self.count):
            done = i < self.current
            active = i == self.current
            col = QColor(self.t.c("ok") if done else
                         (self.t.c("accent") if active else self.t.c("line")))
            if active and not self.ok and i == self.count - 1:
                col = QColor(self.t.c("err"))
            p.setBrush(col if (done or active) else QColor(self.t.c("line_strong")))
            p.drawEllipse(QPointF(x + r, y), r * (1.5 if active else 1.0), r * (1.5 if active else 1.0))
            x += step
        p.end()


class Transcript(QLabel):
    """سطر «آخر ما سُمع» — يُلوَّن حسب نجاح الأمر."""

    def __init__(self, t: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.t = t
        self.setFont(QFont("Segoe UI", t.pt(11.5), QFont.DemiBold))
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setMinimumHeight(t.px(42))
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setText("…")
        self.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;")
        self.ok: bool | None = None

    def show_text(self, text: str, ok: bool | None = None) -> None:
        t = self.t
        self.ok = ok
        if ok is None:
            color, mark = t.c("text"), ""
        elif ok:
            color, mark = t.c("ok"), "✓  "
        else:
            color, mark = t.c("err"), "✕  "
        shown = " ".join(text.split())      # يوحّد المسافات ( espeech قد يُعيد أسطراً )
        self.setText(f"{mark}{shown or '…'}")
        self.setStyleSheet(f"color: {color}; background: transparent;")
        self.setFont(QFont("Segoe UI", t.pt(11.5), QFont.DemiBold if ok is not None else QFont.Normal))


class AudioWaveVisualizer(QWidget):
    """مستشعر موجات الصوت: أعمدة متحركة تنبض مع الصوت/الزمن لإضفاء إحساس الذكاء الاصطناعي الحي."""

    def __init__(self, t: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.t = t
        self.setFixedSize(t.px(36), t.px(22))
        self._phase = 0.0
        self._active = True
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            if active and not self._timer.isActive():
                self._timer.start()
            elif not active:
                self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.08) % (2 * math.pi)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.t
        bars = 5
        bw = t.px(3.5)
        gap = t.px(3)
        total_w = bars * bw + (bars - 1) * gap
        x0 = (self.width() - total_w) / 2
        cy = self.height() / 2
        max_h = self.height() * 0.82

        for i in range(bars):
            if self._active and not t.high_contrast:
                h_factor = 0.25 + 0.75 * abs(math.sin(self._phase + i * 0.95))
            else:
                h_factor = 0.2
            h = max(t.px(3), max_h * h_factor)
            rect = QRectF(x0 + i * (bw + gap), cy - h / 2, bw, h)
            col = QColor(t.c("accent") if i % 2 == 0 else t.c("accent_2"))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(col))
            p.drawRoundedRect(rect, bw / 2, bw / 2)
        p.end()
