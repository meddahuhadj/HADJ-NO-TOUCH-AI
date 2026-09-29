"""أيقونات ورسومات الواجهة: كل شيء مرسوم برمجياً (لا ملفات صور، لا تحميل)."""
from __future__ import annotations

import base64
from functools import lru_cache

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient)

# ألوان الحالات: متسقة مع جدول شريط النظام في README
STATE_COLORS = {
    "ready": "#22c55e",      # أخضر: يستمع لكلمة التنبيه
    "armed": "#3b82f6",      # أزرق: ينتظر أمراً
    "paused": "#64748b",     # رمادي: متوقف
    "loading": "#f59e0b",    # أصفر: تحميل
    "error": "#ef4444",      # أحمر: خطأ
    "muted": "#8d6e63",
    "dictation": "#a855f7",  # بنفسجي: وضع الإملاء
    "grid": "#22d3ee",       # أزرق مخضر: الشبكة الصوتية
}

# نسخة عالية التباين: ألوان مشرقة تُقرأ على خلفية سوداء
STATE_COLORS_HC = {
    "ready": "#00e676", "armed": "#40c4ff", "paused": "#b0bec5", "loading": "#ffd600",
    "error": "#ff5252", "muted": "#d7ccc8", "dictation": "#e040fb", "grid": "#00e5ff",
}

FALLBACK_STATE = STATE_COLORS["ready"]


def state_color(state: str, high_contrast: bool = False) -> str:
    table = STATE_COLORS_HC if high_contrast else STATE_COLORS
    return table.get(state, FALLBACK_STATE)


# ------------------------------------------------------------------ أدوات
def data_uri(pm: QPixmap) -> str:
    """QPixmap → نص data-URI صالح للاستخدام في QSS (url(...))."""
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(bytes(buf.data())).decode("ascii")


def _canvas(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return p, pm


def _pen(color: str, width: float) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _draw_mic(p: QPainter, cx: float, cy: float, height: float, color: str = "#ffffff") -> None:
    """رمز ميكروفون بسيط ومتمركز (يعمل من 16px إلى 128px)."""
    w = height * 0.40
    top = cy - height * 0.52
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(cx - w / 2, top, w, height * 0.52), w / 2, w / 2)   # الرأس
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(color, max(1.0, height * 0.075)))
    p.drawArc(QRectF(cx - height * 0.24, top + height * 0.16, height * 0.48, height * 0.46),
              180 * 16, 180 * 16)                                                # القوس
    p.drawLine(QPointF(cx, top + height * 0.62), QPointF(cx, top + height * 0.90))  # الساق
    p.drawLine(QPointF(cx - height * 0.15, top + height * 0.92), QPointF(cx + height * 0.15, top + height * 0.92))


# ------------------------------------------------------- رسومات للاستعمال في QSS
@lru_cache(maxsize=32)
def check_png(color: str = "#ffffff", size: int = 24, width: float = 3.0) -> str:
    p, pm = _canvas(size)
    p.setPen(_pen(color, width))
    p.drawPolyline([QPointF(size * 0.24, size * 0.54), QPointF(size * 0.44, size * 0.74),
                    QPointF(size * 0.78, size * 0.28)])
    p.end()
    return data_uri(pm)


@lru_cache(maxsize=32)
def dot_png(color: str = "#ffffff", size: int = 16) -> str:
    p, pm = _canvas(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    r = size * 0.28
    p.drawEllipse(QRectF((size - r * 2) / 2, (size - r * 2) / 2, r * 2, r * 2))
    p.end()
    return data_uri(pm)


@lru_cache(maxsize=32)
def chevron_png(color: str = "#9aa7c2", size: int = 14, width: float = 2.0, up: bool = False) -> str:
    p, pm = _canvas(size)
    p.setPen(_pen(color, width))
    lo, hi = (size * 0.30, size * 0.70) if up else (size * 0.70, size * 0.30)
    p.drawPolyline([QPointF(size * 0.26, hi), QPointF(size * 0.5, lo), QPointF(size * 0.74, hi)])
    p.end()
    return data_uri(pm)


@lru_cache(maxsize=32)
def cross_png(color: str = "#9aa7c2", size: int = 20, width: float = 2.2) -> str:
    p, pm = _canvas(size)
    p.setPen(_pen(color, width))
    m = size * 0.30
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    p.end()
    return data_uri(pm)


# ------------------------------------------------------------------ الأيقونات
def state_icon(state: str, size: int = 64, high_contrast: bool = False) -> QIcon:
    """أيقونة شريط النظام: دائرة بلون الحالة + ميكروفون أبيض + حلقة تعريف."""
    color = QColor(state_color(state, high_contrast))
    p, pm = _canvas(size)
    inset = size * 0.04
    body = QRectF(inset, inset, size - inset * 2, size - inset * 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_radial(color, body)))
    p.drawEllipse(body)
    _draw_mic(p, size / 2, size * 0.46, size * 0.42)
    if state == "paused":      # خط مائل: التحكم متوقف
        p.setPen(_pen("#fde047" if not high_contrast else "#ffd600", max(2.0, size * 0.09)))
        p.drawLine(QPointF(size * 0.22, size * 0.78), QPointF(size * 0.78, size * 0.22))
    p.end()
    return QIcon(pm)


def app_icon(size: int = 64, high_contrast: bool = False) -> QIcon:
    """أيقونة التطبيق: مربّع مستدير بتدرّج شفق + ميكروفون (لنافذتَي اللوحة والإعدادات)."""
    p, pm = _canvas(size)
    r = size * 0.24
    rect = QRectF(0, 0, size, size)
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    if high_contrast:
        p.setBrush(QColor("#000000"))
        p.setPen(QPen(QColor("#ffffff"), max(1.5, size * 0.045)))
        p.drawPath(path)
    else:
        g = QLinearGradient(0, 0, size, size)
        g.setColorAt(0.0, QColor("#4c8dff"))
        g.setColorAt(1.0, QColor("#8b5cf6"))
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
    _draw_mic(p, size / 2, size * 0.47, size * 0.44)
    p.end()
    return QIcon(pm)


def _radial(color: QColor, rect: QRectF) -> QRadialGradient:
    """تدرّج دائري: لون الحالة في المركز، أفتح قليلاً عند الحافة (انعكاس ناعم)."""
    g = QRadialGradient(rect.center(), max(1.0, rect.width() / 2))
    lighter = QColor(color)
    lighter = lighter.lighter(118)
    g.setColorAt(0.0, lighter)
    g.setColorAt(1.0, color)
    return g
