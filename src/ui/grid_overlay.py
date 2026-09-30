"""نافذة الشبكة الصوتية: بطاقات أرقام شفافة فوق كل الشاشات، بلا اعتراض للنقرات."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import QWidget

from commands.grid import split_rect
from ui.theme import theme
from ui.widgets import make_transparent


class GridOverlay(QWidget):
    def __init__(self, font_scale: float = 1.0, high_contrast: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        make_transparent(self)
        self.th = theme(font_scale, high_contrast)
        self.line = self.th.c("accent") if not high_contrast else "#ffff00"
        self.rect_px = (0, 0, 0, 0)
        self.can_split = True
        self.level = 0

    def show_grid(self, rect, level: int, can_split: bool) -> None:
        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.virtualGeometry())
        self.rect_px = tuple(rect)
        self.level = level
        self.can_split = can_split
        self.show()
        self.raise_()
        self.update()

    def _to_local(self, x: float, y: float) -> QPointF:
        """من بكسل النظام الفعلي إلى إحداثيات Qt المنطقية داخل النافذة."""
        dpr = QGuiApplication.primaryScreen().devicePixelRatio() or 1.0
        g = self.geometry()
        return QPointF(x / dpr - g.x(), y / dpr - g.y())

    def _qrect(self, r) -> QRectF:
        a = self._to_local(r[0], r[1])
        b = self._to_local(r[0] + r[2], r[1] + r[3])
        return QRectF(a, b)

    def paintEvent(self, _e):
        t = self.th
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cur = self._qrect(self.rect_px)

        # تعتيم ما خارج المنطقة الحالية لإبرازها (بلا تعتيم في المستوى الأول)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90 if self.level else 30))

        if not self.can_split:      # وصلنا لأصغر خانة: صليب في المنتصف
            self._draw_zone(p, cur)
            c = cur.center()
            arm = t.px(26)
            p.setPen(QPen(QColor(self.line), t.px(4), cap=Qt.RoundCap))
            p.drawLine(QPointF(c.x() - arm, c.y()), QPointF(c.x() + arm, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - arm), QPointF(c.x(), c.y() + arm))
            p.end()
            return

        size = max(16, min(70, int(min(cur.width(), cur.height()) / 5.2))) * t.scale
        font = QFont("Segoe UI", int(size), QFont.DemiBold)
        radius = t.px(14)
        for n in range(1, 10):
            cell = self._qrect(split_rect(self.rect_px, n))
            self._draw_zone(p, cell, radius=radius)
            self._draw_badge(p, cell, str(n), font, radius)
        self._draw_level(p, cur)
        p.end()

    # ------------------------------------------------------------------
    def _draw_zone(self, p: QPainter, r: QRectF, radius: int | None = None) -> None:
        """إطار الخانة: خط شعري + توهّج داخلي خفيف (بلا تعبئة معتمة تُخفي الشاشة)."""
        t = self.th
        rad = t.px(12) if radius is None else radius
        inset = r.adjusted(t.px(2), t.px(2), -t.px(2), -t.px(2))
        if not t.high_contrast:
            g = QLinearGradient(inset.topLeft(), inset.bottomLeft())
            g.setColorAt(0.0, QColor(76, 141, 255, 26))
            g.setColorAt(1.0, QColor(0, 0, 0, 46))
            p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(self.line), max(2, t.px(2.5))))
        p.drawRoundedRect(inset, rad, rad)

    def _draw_badge(self, p: QPainter, cell: QRectF, text: str, font: QFont, radius: int) -> None:
        """رقم أبيض داخل قرص داكن: يُقرأ فوق أي خلفية أو لون شاشة."""
        t = self.th
        r = t.px(min(46, max(30, int(min(cell.width(), cell.height()) * 0.34))))
        c = cell.center()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(6, 10, 20, 190) if not t.high_contrast else QColor(0, 0, 0))
        p.drawEllipse(c, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(self.line), max(1, t.px(1.5))))
        p.drawEllipse(c, r, r)
        path = QPainterPath()
        adv = QFontMetricsF(font).horizontalAdvance(text)
        path.addText(QPointF(c.x() - adv / 2, c.y() + r * 0.36), font, text)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawPath(path)

    def _draw_level(self, p: QPainter, cur: QRectF) -> None:
        """شريط مستوى صغير أعلى يسار الشاشة: يوضّح عمق التقسيم."""
        t = self.th
        y = t.px(26)
        x = t.px(26)
        d = t.px(6)
        p.setPen(Qt.NoPen)
        for i in range(self.level + 1):
            col = QColor(self.line) if i == self.level else QColor(self.line)
            col.setAlphaF(1.0 if i == self.level else 0.35)
            p.setBrush(col)
            p.drawEllipse(QPointF(x + i * d * 3, y), d, d)
