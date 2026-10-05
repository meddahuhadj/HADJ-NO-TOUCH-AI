"""مؤشر الحالة الدائم: دائرة صغيرة في زاوية الشاشة، فوق كل النوافذ، لا تعترض النقرات.

- الحلقة بلون الحالة (يستمع، متوقف، خطأ…) وتنبض بالأخضر مع مستوى الصوت أثناء الكلام.
- في الوسط: هيكل اليد كما تراه الكاميرا (يتبع الإيماءات)، أو رمز الحالة إن لم تظهر يد.
- شارة صغيرة لحالة الكاميرا.
لا يُعتمد على اللون وحده: لكل حالة رمز مختلف (عمودان للإيقاف، «!» للخطأ، خط مائل للكتم).
المؤقت يعمل فقط أثناء الحركة (كلام، يد، تحميل) لكي لا يستهلك المعالج وهو ساكن.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui.hand_poses import HAND_EDGES
from ui.theme import Theme, theme
from ui.widgets import make_transparent

FRAME_MS = 33
HAND_STALE_S = 0.5      # بعدها يختفي الهيكل ويعود رمز الحالة
VOICE_COLOR = "#4ade80"
VOICE_COLOR_HC = "#69f0ae"
EDGE = 16               # المسافة عن حافة الشاشة

# حالة الكاميرا ← لون الشارة (None = لا شارة)
CAMERA_BADGE = {"tracking": "ok", "ready": "text_faint", "slow": "warn",
                "dozing": "line_strong", "asleep": "surface_hi",
                "error": "err", "no_image": "err", "loading": "warn", "off": None}


def glyph_for(visual: str) -> str:
    """رمز الوسط عند غياب اليد: pause | alert | muted | spinner | mic."""
    return {"paused": "pause", "error": "alert", "muted": "muted",
            "loading": "spinner"}.get(visual, "mic")


def fit_points(points: list[tuple[float, float]], cx: float, cy: float,
               radius: float) -> list[QPointF]:
    """يكبّر هيكل اليد ليملأ دائرة نصف قطرها radius مع الحفاظ على النسب."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    span = max(w, h, 1e-6)
    k = 2 * radius * 0.82 / span
    mx = (max(xs) + min(xs)) / 2
    my = (max(ys) + min(ys)) / 2
    return [QPointF(cx + (x - mx) * k, cy + (y - my) * k) for x, y in points]


def corner_for(setting: str, rtl: bool) -> str:
    if setting != "auto":
        return setting
    return "bottom-left" if rtl else "bottom-right"


class StatusOrb(QWidget):
    def __init__(self, font_scale: float = 1.0, high_contrast: bool = False,
                 corner: str = "auto", rtl: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        make_transparent(self)
        self.th: Theme = theme(font_scale, high_contrast)
        self.corner = corner_for(corner, rtl)
        self.diameter = self.th.px(54)
        side = self.diameter + 2 * self.th.px(16)   # فراغ للهالة والنبض
        self.setFixedSize(side, side)

        self.visual = "loading"
        self.camera = "off"
        self.voice_active = False
        self._level = 0.0          # المستوى المنعَّم المرسوم
        self._target_level = 0.0
        self.hand: list[tuple[float, float]] | None = None
        self.pose = "none"
        self._hand_t = 0.0
        self._spin = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    # ---- الواجهة العامة ----
    def place(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        m = EDGE - self.th.px(16) // 2
        x = screen.left() + m if "left" in self.corner else screen.right() - self.width() - m
        y = screen.top() + m if "top" in self.corner else screen.bottom() - self.height() - m
        self.move(x, y)

    def set_state(self, visual: str, camera: str) -> None:
        if (visual, camera) != (self.visual, self.camera):
            self.visual, self.camera = visual, camera
            if visual == "paused":   # الإيقاف الطارئ يمسح أي أثر للصوت أو اليد فوراً
                self.voice_active = False
                self._target_level = 0.0
                self.hand = None
            self._wake()

    def set_voice(self, active: bool, level: float = 0.0) -> None:
        self.voice_active = active
        self._target_level = max(0.0, min(1.0, level)) if active else 0.0
        self._wake()

    def set_hand(self, points: list[tuple[float, float]], pose: str) -> None:
        if len(points) < 21 or self.visual == "paused":
            return
        self.hand, self.pose = points, pose
        self._hand_t = time.monotonic()
        self._wake()

    # ---- الحركة ----
    def _animating(self) -> bool:
        return (self.voice_active or self._level > 0.01 or self.visual == "loading"
                or self.hand is not None)

    def _wake(self) -> None:
        if self._animating() and not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self) -> None:
        self._level += (self._target_level - self._level) * 0.35
        self._spin = (self._spin + 9) % 360
        if self.hand is not None and time.monotonic() - self._hand_t > HAND_STALE_S:
            self.hand = None
        if not self._animating():
            self._level = 0.0
            self._timer.stop()
        self.update()

    # ---- الرسم ----
    def _color(self, key: str) -> QColor:
        return QColor(self.th.state(key))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.th
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.diameter / 2
        state_col = self._color(self.visual)
        voice_col = QColor(VOICE_COLOR_HC if t.high_contrast else VOICE_COLOR)

        # نبض الصوت: هالة تتمدد مع المستوى
        if self._level > 0.01:
            halo = QColor(voice_col)
            halo.setAlphaF(0.18 + 0.32 * self._level)
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            hr = r + t.px(4) + t.px(10) * self._level
            p.drawEllipse(c, hr, hr)

        # القرص
        bg = t.qc("surface")
        bg.setAlphaF(0.96 if t.high_contrast else 0.88)
        p.setBrush(bg)
        ring = voice_col if self.voice_active else state_col
        p.setPen(QPen(ring, t.px(4 if t.high_contrast else 3)))
        p.drawEllipse(c, r, r)

        if self.hand is not None:
            self._paint_hand(p, c, r * 0.72)
        else:
            self._paint_glyph(p, c, r * 0.5, state_col)
        self._paint_camera_badge(p, c, r)
        p.end()

    def _paint_hand(self, p: QPainter, c: QPointF, radius: float) -> None:
        t = self.th
        pts = fit_points(self.hand, c.x(), c.y(), radius)
        col = t.qc("text")
        p.setPen(QPen(col, max(1.5, t.px(1.6)), Qt.SolidLine, Qt.RoundCap))
        for a, b in HAND_EDGES:
            p.drawLine(pts[a], pts[b])
        # القرص (نقر): يربط الإبهام والسبابة بخط ملوّن، والقبضة تلوّن الكف
        accent = QColor(self.th.state("grid"))
        if self.pose in ("pinch", "middle_pinch"):
            tip = 8 if self.pose == "pinch" else 12
            p.setPen(QPen(accent, t.px(3), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(pts[4], pts[tip])
        elif self.pose == "fist":
            p.setPen(Qt.NoPen)
            p.setBrush(t.qc("warn", 0.8))
            p.drawEllipse(pts[9], t.px(4), t.px(4))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(pts[8], t.px(2.4), t.px(2.4))   # طرف السبابة = المؤشر

    def _paint_glyph(self, p: QPainter, c: QPointF, s: float, col: QColor) -> None:
        t = self.th
        g = glyph_for(self.visual)
        pen = QPen(col, max(2.0, t.px(2.4)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if g == "pause":
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            w = s * 0.32
            p.drawRoundedRect(QRectF(c.x() - s * 0.55, c.y() - s * 0.7, w, s * 1.4), 2, 2)
            p.drawRoundedRect(QRectF(c.x() + s * 0.55 - w, c.y() - s * 0.7, w, s * 1.4), 2, 2)
        elif g == "alert":
            p.drawLine(QPointF(c.x(), c.y() - s * 0.7), QPointF(c.x(), c.y() + s * 0.2))
            p.setBrush(col)
            p.drawEllipse(QPointF(c.x(), c.y() + s * 0.62), pen.widthF() * 0.6, pen.widthF() * 0.6)
        elif g == "spinner":
            rect = QRectF(c.x() - s * 0.75, c.y() - s * 0.75, s * 1.5, s * 1.5)
            p.drawArc(rect, int(-self._spin * 16), 100 * 16)
        else:
            # ميكروفون: كبسولة + قوس + ساق؛ ممتلئ عند انتظار أمر (armed)
            cap = QRectF(c.x() - s * 0.3, c.y() - s * 0.8, s * 0.6, s * 1.05)
            if self.visual in ("armed", "dictation") or self.voice_active:
                p.setBrush(col)
            p.drawRoundedRect(cap, s * 0.3, s * 0.3)
            p.setBrush(Qt.NoBrush)
            arc = QRectF(c.x() - s * 0.55, c.y() - s * 0.45, s * 1.1, s * 0.95)
            p.drawArc(arc, 200 * 16, 140 * 16)
            p.drawLine(QPointF(c.x(), c.y() + s * 0.5), QPointF(c.x(), c.y() + s * 0.78))
            if g == "muted":
                p.setPen(QPen(QColor(self.th.state("error")), pen.widthF(), Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(c.x() - s * 0.7, c.y() - s * 0.8),
                           QPointF(c.x() + s * 0.7, c.y() + s * 0.8))

    def _paint_camera_badge(self, p: QPainter, c: QPointF, r: float) -> None:
        key = CAMERA_BADGE.get(self.camera, "text_faint")
        if key is None:
            return
        t = self.th
        a = math.radians(45)
        b = QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a))
        br = t.px(6)
        p.setPen(QPen(t.qc("surface"), t.px(2)))
        p.setBrush(t.qc(key))
        p.drawEllipse(b, br, br)
