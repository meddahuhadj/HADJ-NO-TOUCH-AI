"""رسوم متحركة لخطوات المعايرة: يد مرسومة برمجياً (بلا صور ولا فيديو) تُري الحركة المطلوبة.

اليد تُرسم بنفس هيكل المعالم الـ21 الذي تراه الكاميرا (ونفس شكل مؤشر الحالة)،
وتنتقل بسلاسة بين وضعيات ثابتة: مفتوحة، قرص، إشارة.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui.hand_poses import HAND_EDGES, OPEN, PINCH, POINT, lerp_pose  # noqa: F401
from ui.theme import Theme

FRAME_MS = 33

def ease(f: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, f)))


def pinch_phase(t: float, period: float = 2.4) -> float:
    """0 = مفتوحة، 1 = قرص: فتح ← إغلاق ← تثبيت ← فتح."""
    u = (t % period) / period
    if u < 0.3:
        return ease(u / 0.3)
    if u < 0.75:
        return 1.0
    return 1.0 - ease((u - 0.75) / 0.25)


def zone_point(t: float, period: float = 6.0) -> tuple[float, float]:
    """موضع على محيط مستطيل (0..1) يمرّ بالزوايا الأربع مع توقف قصير عند كل زاوية."""
    corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    u = (t % period) / period * 4
    i = int(u)
    f = ease(min(1.0, (u - i) / 0.75))     # آخر ربع من كل ضلع = توقف عند الزاوية
    (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
    return ax + (bx - ax) * f, ay + (by - ay) * f


class CalibrationArt(QWidget):
    """scene: prepare | open | pinch | point | zone | done | none."""

    def __init__(self, th: Theme, parent: QWidget | None = None, rtl: bool = False,
                 distance_label: str = "≈ 50 cm"):
        super().__init__(parent)
        self.th = th
        self.rtl = rtl
        self.distance_label = distance_label
        self.scene = "none"
        self.setFixedHeight(th.px(150))
        self._t0 = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.update)

    def set_scene(self, scene: str) -> None:
        if scene != self.scene:
            self.scene = scene
            self._t0 = time.monotonic()
        animated = scene not in ("none", "done")
        if animated and not self._timer.isActive():
            self._timer.start()
        elif not animated:
            self._timer.stop()
        self.update()

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.set_scene(self.scene)

    # ---- الرسم ----
    def paintEvent(self, _e) -> None:
        if self.scene == "none":
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = time.monotonic() - self._t0
        draw = getattr(self, f"_draw_{self.scene}", None)
        if draw is not None:
            draw(p, t)
        p.end()

    def _hand(self, p: QPainter, pose: list, cx: float, cy: float, unit: float,
              angle: float = 0.0, accent_tip: bool = False) -> list[QPointF]:
        """يرسم اليد: الرسغ عند (cx, cy + unit*0.4) تقريباً. يرجع النقاط المرسومة."""
        th = self.th
        ca, sa = math.cos(angle), math.sin(angle)
        pts = []
        for x, y in pose:
            y -= 0.4                                   # مركز اليد قرب منتصف الكف
            rx, ry = x * ca - y * sa, x * sa + y * ca
            pts.append(QPointF(cx + rx * unit, cy + ry * unit))
        p.setPen(QPen(th.qc("text"), max(2.0, unit * 0.075), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for a, b in HAND_EDGES:
            p.drawLine(pts[a], pts[b])
        p.setPen(Qt.NoPen)
        p.setBrush(th.qc("text"))
        for q in pts:
            p.drawEllipse(q, unit * 0.035, unit * 0.035)
        if accent_tip:
            p.setBrush(self.th.qc("accent"))
            p.drawEllipse(pts[8], unit * 0.07, unit * 0.07)
        return pts

    def _unit(self) -> float:
        return self.height() * 0.62

    def _draw_open(self, p: QPainter, t: float) -> None:
        # ترتفع اليد ثم تلوّح بلطف
        rise = ease(min(1.0, t / 0.7))
        cy = self.height() * (0.95 - 0.43 * rise)
        angle = math.radians(9) * math.sin(t * 3.2) * rise
        self._hand(p, OPEN, self.width() / 2, cy, self._unit(), angle)

    def _draw_pinch(self, p: QPainter, t: float) -> None:
        f = pinch_phase(t)
        pts = self._hand(p, lerp_pose(OPEN, PINCH, f), self.width() / 2, self.height() * 0.52,
                         self._unit())
        if f > 0.98:   # لحظة التلامس: حلقة مضيئة
            pulse = (t * 2.5) % 1.0
            col = self.th.qc("ok")
            col.setAlphaF(1.0 - pulse)
            p.setPen(QPen(col, self.th.px(2)))
            p.setBrush(Qt.NoBrush)
            r = self._unit() * (0.08 + 0.12 * pulse)
            p.drawEllipse(pts[8], r, r)

    def _draw_point(self, p: QPainter, t: float) -> None:
        f = ease(min(1.0, t / 0.6))
        cx = self.width() / 2 + math.sin(t * 2.2) * self.width() * 0.04 * f
        self._hand(p, lerp_pose(OPEN, POINT, f), cx, self.height() * 0.52, self._unit(),
                   accent_tip=True)

    def _draw_zone(self, p: QPainter, t: float) -> None:
        th = self.th
        h = self.height()
        rect = QRectF(self.width() / 2 - h * 0.75, h * 0.1, h * 1.5, h * 0.8)
        p.setPen(QPen(th.qc("line_strong"), th.px(1.5), Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, th.px(6), th.px(6))
        # الزوايا المطلوبة
        for i, (x, y) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            c = QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height())
            p.setPen(Qt.NoPen)
            p.setBrush(th.qc("text_faint"))
            p.drawEllipse(c, th.px(3.5), th.px(3.5))
        # أثر السبابة
        trail = 14
        for k in range(trail, -1, -1):
            u, v = zone_point(t - k * 0.04)
            q = QPointF(rect.left() + u * rect.width(), rect.top() + v * rect.height())
            col = th.qc("accent")
            col.setAlphaF(1.0 - k / (trail + 1))
            p.setBrush(col)
            p.drawEllipse(q, th.px(4.5) * (1 - k / (trail * 2)), th.px(4.5) * (1 - k / (trail * 2)))

    def _draw_prepare(self, p: QPainter, t: float) -> None:
        """كاميرا ← سهم «~50 سم» ← رأس وكتفان، ومصباح أمام الشخص (لا نافذة خلفه)."""
        th = self.th
        h, w = self.height(), self.width()
        sign = -1 if self.rtl else 1
        cam = QPointF(w / 2 - sign * h * 0.95, h * 0.45)
        person = QPointF(w / 2 + sign * h * 0.75, h * 0.4)
        # الكاميرا
        p.setPen(QPen(th.qc("text"), th.px(2)))
        p.setBrush(th.qc("surface_alt"))
        p.drawRoundedRect(QRectF(cam.x() - h * 0.14, cam.y() - h * 0.1, h * 0.28, h * 0.2), 4, 4)
        p.setBrush(th.qc("accent"))
        p.drawEllipse(cam, h * 0.05, h * 0.05)
        # الشخص
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(th.qc("text"), th.px(2.2), Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(person, h * 0.11, h * 0.13)
        p.drawArc(QRectF(person.x() - h * 0.26, person.y() + h * 0.17, h * 0.52, h * 0.5), 0, 180 * 16)
        # سهم المسافة يتنفس بين 45 و55 سم
        y = h * 0.82
        x0, x1 = cam.x() + sign * h * 0.2, person.x() - sign * h * 0.3
        wob = math.sin(t * 2.4) * h * 0.04
        x1 += sign * wob
        p.setPen(QPen(th.qc("ok"), th.px(2), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0, y), QPointF(x1, y))
        for x, d in ((x0, sign), (x1, -sign)):
            p.drawLine(QPointF(x, y), QPointF(x + d * h * 0.06, y - h * 0.05))
            p.drawLine(QPointF(x, y), QPointF(x + d * h * 0.06, y + h * 0.05))
        p.setPen(th.qc("text"))
        p.setFont(QFont("Segoe UI", th.pt(10), QFont.DemiBold))
        p.drawText(QRectF(min(x0, x1), y - h * 0.2, abs(x1 - x0), h * 0.16), Qt.AlignCenter, self.distance_label)
        # مصباح بين الكاميرا والشخص: الضوء على الوجه
        lamp = QPointF((cam.x() + person.x()) / 2, h * 0.16)
        glow = th.qc("warn")
        glow.setAlphaF(0.25 + 0.15 * math.sin(t * 3))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(lamp, h * 0.1, h * 0.1)
        p.setBrush(th.qc("warn"))
        p.drawEllipse(lamp, h * 0.045, h * 0.045)
