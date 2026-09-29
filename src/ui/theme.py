"""نظام تصميم الواجهة: رموز بصرية موحّدة (ألوان، خطوط، مسافات) + ورقة أنماط QSS.

كل المقاسات تُشتقّ من `font_scale` (0.75 → 3.0) ليكبر كل شيء معاً، ولون التباين العالي
يسلك مساراً بديلاً صريحاً (أسود + أصفر + حدود سميكة) لا مجرد تعديل على الألوان.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from PySide6.QtGui import QColor

from ui.icons import check_png, chevron_png, cross_png, dot_png, state_color

FONT_STACK = "'Segoe UI', 'Dubai', 'Noto Sans Arabic', 'Sakkal Majalla', Tahoma, sans-serif"

# تدرّج الهوية البصرية: أزرق سماوي → بنفسجي
ACCENT = "#3b82f6"
ACCENT_2 = "#8b5cf6"

_DARK = {
    "canvas": "#070b14",      # أعمق طبقة (خلف النوافذ) - أبلق داكن فخم
    "surface": "#0f172a",     # سطح البطاقات الرئيسية
    "surface_alt": "#182238",  # سطح ثانوي (حقول، أزرار، مناطق مدمجة)
    "surface_hi": "#23314f",   # سطح التحويم المضيء
    "line": "#263554",        # حدود ناعمة
    "line_strong": "#3b4f7a", # حدود بارزة
    "text": "#f1f5f9",        # نص رئيسي ناصع
    "text_dim": "#94a3b8",    # نص فرعي خفيف
    "text_faint": "#64748b",  # نص ثانوية باهت
    "accent": ACCENT,
    "accent_2": ACCENT_2,
    "on_accent": "#ffffff",
    "ok": "#10b981",          # أخضر زمرّدي
    "warn": "#f59e0b",        # كهروماني دافئ
    "err": "#f43f5e",         # وردي أحمر نيون
    "ring": "rgba(59, 130, 246, 0.5)",
}

_HIGH_CONTRAST = {
    "canvas": "#000000",
    "surface": "#000000",
    "surface_alt": "#0a0a0a",
    "surface_hi": "#141414",
    "line": "#ffffff",
    "line_strong": "#ffffff",
    "text": "#ffffff",
    "text_dim": "#ffffff",
    "text_faint": "#e0e0e0",
    "accent": "#ffd400",
    "accent_2": "#ffd400",
    "on_accent": "#000000",
    "ok": "#00ff66",
    "warn": "#ffd400",
    "err": "#ff5c5c",
    "ring": "#ffffff",
}

_BG = {"dark": _DARK, "hc": _HIGH_CONTRAST}


@dataclass(frozen=True)
class Theme:
    """رموز التصميم لوضع واحد (داكن أو تباين عالٍ) عند حجم خط معيّن."""

    scale: float = 1.0
    high_contrast: bool = False
    colors: dict[str, str] = field(default_factory=lambda: _DARK)

    # ---------- مقاسات مشتقّة ----------
    def pt(self, value: float) -> int:
        """نقاط الخط (تُستخدم في QSS وQFont معاً)."""
        return max(7, int(round(value * self.scale)))

    def px(self, value: float) -> int:
        """بكسل منطقي، ينمو مع حجم الخط بحدّ معقول (لا يتضخم عند التكبير الكبير)."""
        return int(round(value * min(self.scale, 1.6)))

    def s(self, value: float) -> str:
        return f"{self.px(value)}px"

    # ---------- ألوان ----------
    def c(self, key: str) -> str:
        return self.colors.get(key, self.colors["text"])

    def qc(self, key: str, alpha: float = 1.0) -> QColor:
        """QColor من رمز لوني (يدعم rgba())."""
        raw = self.c(key)
        col = QColor(raw)
        if alpha < 1.0:
            col.setAlphaF(alpha)
        return col

    def alpha(self, key: str, a: float) -> str:
        col = self.qc(key)
        col.setAlphaF(a)
        return f"rgba({col.red()}, {col.green()}, {col.blue()}, {round(a, 3)})"

    def state(self, name: str) -> str:
        return state_color(name, self.high_contrast)

    @property
    def hairline(self) -> int:
        """سماكة الحد: خفيف في الوضع العادي، سميك في التباين العالي."""
        return 2 if self.high_contrast else 1

    @property
    def radius(self) -> int:
        return self.px(20)

    # ---------- ورقة الأنماط ----------
    def qss(self) -> str:
        return _build_qss(self)


@lru_cache(maxsize=16)
def theme(font_scale: float = 1.0, high_contrast: bool = False) -> Theme:
    key = round(max(0.75, min(3.0, float(font_scale))), 2)
    return Theme(key, bool(high_contrast), _BG["hc" if high_contrast else "dark"])


def font(pt: float, scale: float = 1.0, weight: int | None = None):
    """خط UIFont مطبَّق المقياس (للرسم المخصّص حيث لا تصلح QSS)."""
    from PySide6.QtGui import QFont
    f = QFont("Segoe UI")
    f.setPointSizeF(pt * scale)
    if weight is not None:
        f.setWeight(QFont.Weight(weight))
    return f


def get_app_stylesheet(font_scale: float = 1.0, high_contrast: bool = False) -> str:
    """ورقة الأنماط العامة (نفس التوقيع المستدعى من main وwindows الإعدادات)."""
    return theme(font_scale, high_contrast).qss()


def apply_palette(app, font_scale: float = 1.0, high_contrast: bool = False) -> None:
    """لوحة ألوان Qt نفسها داكنة.

    # ضرورية لأن QSS لا ترسم الحاويات التي لا تحمل اسماً: بدونها يرسم Qt سطحاً
    # فاتحاً افتراضياً (أبيض) داخل التبويبات وأشرطة التمرير.
    """
    from PySide6.QtGui import QPalette
    t = theme(font_scale, high_contrast)
    p = QPalette()
    p.setColor(QPalette.Window, t.qc("canvas"))
    p.setColor(QPalette.WindowText, t.qc("text"))
    p.setColor(QPalette.Base, t.qc("surface"))
    p.setColor(QPalette.AlternateBase, t.qc("surface_alt"))
    p.setColor(QPalette.Text, t.qc("text"))
    p.setColor(QPalette.PlaceholderText, t.qc("text_faint"))
    p.setColor(QPalette.Button, t.qc("surface_alt"))
    p.setColor(QPalette.ButtonText, t.qc("text"))
    p.setColor(QPalette.BrightText, t.qc("err"))
    p.setColor(QPalette.Highlight, t.qc("accent"))
    p.setColor(QPalette.HighlightedText, t.qc("on_accent"))
    p.setColor(QPalette.ToolTipBase, t.qc("surface_alt"))
    p.setColor(QPalette.ToolTipText, t.qc("text"))
    p.setColor(QPalette.Light, t.qc("surface_hi"))
    p.setColor(QPalette.Mid, t.qc("line"))
    p.setColor(QPalette.Dark, t.qc("canvas"))
    p.setColor(QPalette.Shadow, t.qc("canvas"))
    p.setColor(QPalette.Link, t.qc("accent"))
    p.setColor(QPalette.LinkVisited, t.qc("accent_2"))
    p.setColor(QPalette.Disabled, QPalette.Text, t.qc("text_faint"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, t.qc("text_faint"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, t.qc("text_faint"))
    app.setPalette(p)


# ================================================================== QSS
def _build_qss(t: Theme) -> str:
    body = t.pt(10.5)
    r_sm, r_md, r_lg = t.s(10), t.s(14), t.s(18)
    pad_v, pad_h = t.s(11), t.s(20)
    gap = t.s(4)
    ring = t.c("ring")
    accent, accent2 = t.c("accent"), t.c("accent_2")
    gradient = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {accent2})"
                if not t.high_contrast else accent)
    hair = t.hairline
    check = check_png(t.c("on_accent") if t.high_contrast else "#ffffff")
    dot = dot_png(t.c("text_dim"))
    chev = chevron_png(t.c("text_dim"))
    chev_hc = chevron_png(t.c("text") if t.high_contrast else t.c("text_dim"))
    cross = cross_png(t.c("text_dim") if not t.high_contrast else "#ffffff", 20, 2.4)

    return f"""
/* ===== الأساس ===== */
/* لا لون خلفية هنا: القواعد العامة تلوّن النوافذ فقط، حتى تبقى البطاقات
   الشفافة (اللوحة، التأكيد، المعايرة) مرسومة بالـQPainter لا بطبقة صلبة. */
QWidget {{
    color: {t.c("text")};
    font-family: {FONT_STACK};
    font-size: {body}pt;
    selection-background-color: {accent};
    selection-color: {t.c("on_accent")};
}}
QWidget#windowRoot, QDialog {{
    background-color: {t.c("canvas")};
}}
QToolTip {{
    background-color: {t.c("surface_alt")};
    color: {t.c("text")};
    border: {hair}px solid {t.c("line")};
    border-radius: {r_sm};
    padding: {t.s(7)} {t.s(11)};
}}

/* ===== البطاقات والأسطح ===== */
QFrame[card="true"] {{
    background-color: {t.c("surface")};
    border: {hair}px solid {t.c("line")};
    border-radius: {r_lg};
}}
QFrame[inset="true"] {{
    background-color: {t.c("surface_alt")};
    border: {hair}px solid {t.c("line")};
    border-radius: {r_md};
}}
QFrame[rule="true"] {{
    background-color: {t.c("line")};
    border: none;
    max-height: {hair}px;
    min-height: {hair}px;
}}

/* ===== النصوص ===== */
QLabel[role="title"] {{ font-size: {t.pt(15)}pt; font-weight: 700; color: {t.c("text")}; }}
QLabel[role="heading"] {{ font-size: {t.pt(12)}pt; font-weight: 600; color: {t.c("text")}; }}
QLabel[role="dim"] {{ color: {t.c("text_dim")}; }}
QLabel[role="faint"] {{ color: {t.c("text_faint")}; font-size: {t.pt(9.5)}pt; }}
QLabel[role="caption"] {{
    color: {t.c("text_faint")}; font-size: {t.pt(9.5)}pt;
    letter-spacing: 0.6px; text-transform: uppercase;
}}
QLabel[role="accent"] {{ color: {accent}; font-weight: 600; }}
QLabel[role="ok"] {{ color: {t.c("ok")}; font-weight: 600; }}
QLabel[role="err"] {{ color: {t.c("err")}; font-weight: 600; }}

/* ===== أحجام الأهداف (عبر QSS لا عبر setMinimumHeight: محرك الأنماط يعيد
   حساب الحد الأدنى عند polish فيسقط ما يُضبط من الكود) ===== */
QPushButton[role="action"] {{
    min-height: {t.px(56)}px;
    font-size: {t.pt(11.5)}pt;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QPushButton[role="wide"] {{ min-height: {t.px(50)}px; font-size: {t.pt(11.5)}pt; }}
QPushButton[role="confirm"] {{
    min-height: {t.px(60)}px;
    font-size: {t.pt(15)}pt;
    font-weight: 700;
}}
QPushButton#iconButton {{ min-height: {t.px(40)}px; min-width: {t.px(40)}px; }}

/* ===== الأزرار ===== */
QPushButton {{
    background-color: {t.c("surface_alt")};
    color: {t.c("text")};
    border: {hair}px solid {t.c("line")};
    border-radius: {r_md};
    padding: {pad_v} {pad_h};
    font-weight: 600;
    min-height: {t.px(20)}px;
}}
QPushButton:hover {{
    background-color: {t.c("surface_hi")};
    border-color: {t.c("line_strong")};
}}
QPushButton:pressed {{
    background-color: {t.alpha("accent", 0.18) if not t.high_contrast else t.c("surface_hi")};
    border-color: {accent};
}}
QPushButton:focus {{
    border: {max(2, hair + 1)}px solid {accent};
}}
QPushButton:disabled {{
    background-color: {t.c("surface")};
    color: {t.c("text_faint")};
    border-color: {t.alpha("line", 0.5) if not t.high_contrast else t.c("line")};
}}

QPushButton#primaryButton {{
    background: {gradient};
    color: {t.c("on_accent")};
    border: {hair}px solid {t.alpha("text", 0.28) if not t.high_contrast else accent};
    font-weight: 700;
}}
QPushButton#primaryButton:hover {{
    background: {gradient};
    border-color: {t.c("text") if not t.high_contrast else accent};
    color: {t.c("on_accent")};
}}
QPushButton#primaryButton:disabled {{
    background: {t.c("surface_alt")};
    color: {t.c("text_faint")};
    border-color: {t.c("line")};
}}

QPushButton#dangerButton {{
    background-color: {t.alpha("err", 0.10) if not t.high_contrast else "transparent"};
    color: {t.c("err") if not t.high_contrast else "#ff8a8a"};
    border: {hair}px solid {t.alpha("err", 0.38) if not t.high_contrast else t.c("err")};
}}
QPushButton#dangerButton:hover {{
    background-color: {t.alpha("err", 0.22) if not t.high_contrast else t.c("surface_hi")};
    border-color: {t.c("err")};
    color: {t.c("text") if not t.high_contrast else "#ff8a8a"};
}}

QPushButton#confirmYes {{
    background: {t.c("ok") if t.high_contrast else "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2fbf83, stop:1 #23a06a)"};
    color: #06231a;
    border: {hair}px solid {t.c("ok")};
    font-size: {t.pt(15)}pt;
    font-weight: 700;
}}
QPushButton#confirmYes:hover {{ color: #06231a; border-color: {t.c("text")}; }}
QPushButton#confirmNo {{
    background-color: {t.alpha("err", 0.10) if not t.high_contrast else "transparent"};
    color: {t.c("err")};
    border: {hair}px solid {t.alpha("err", 0.5) if not t.high_contrast else t.c("err")};
    font-size: {t.pt(15)}pt;
    font-weight: 700;
}}
QPushButton#confirmNo:hover {{
    background-color: {t.alpha("err", 0.22) if not t.high_contrast else t.c("surface_hi")};
    color: {t.c("text") if not t.high_contrast else t.c("err")};
    border-color: {t.c("err")};
}}

QPushButton#ghostButton {{
    background: transparent;
    border: {hair}px solid {t.alpha("line", 0.8) if not t.high_contrast else t.c("line")};
    color: {t.c("text_dim")};
    font-weight: 600;
}}
QPushButton#ghostButton:hover {{
    background: {t.c("surface_alt")};
    color: {t.c("text")};
    border-color: {t.c("line_strong")};
}}

QPushButton#iconButton {{
    background: transparent;
    border: none;
    border-radius: {r_md};
    padding: {t.s(6)};
}}
QPushButton#iconButton:hover {{ background: {t.alpha("text", 0.10)}; }}
QPushButton#iconButton {{ image: url({cross}); }}

/* ===== الحقول ===== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background-color: {t.c("surface_alt")};
    color: {t.c("text")};
    border: {hair}px solid {t.c("line")};
    border-radius: {r_md};
    padding: {t.s(8)} {t.s(12)};
    min-height: {t.px(22)}px;
    selection-background-color: {accent};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {t.c("line_strong")};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: {max(2, hair + 1)}px solid {accent};
    background-color: {t.c("surface_hi")};
}}
QLineEdit::placeholder {{ color: {t.c("text_faint")}; }}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: {t.px(28)}px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{ image: url({chev}); width: {t.px(13)}px; height: {t.px(13)}px; }}
QComboBox QAbstractItemView {{
    background-color: {t.c("surface")};
    color: {t.c("text")};
    border: {hair}px solid {t.c("line_strong")};
    border-radius: {r_md};
    padding: {t.s(6)};
    outline: none;
    selection-background-color: {t.alpha("accent", 0.28) if not t.high_contrast else accent};
    selection-color: {t.c("on_accent") if not t.high_contrast else t.c("text")};
}}
QComboBox QAbstractItemView::item {{ padding: {t.s(7)} {t.s(9)}; border-radius: {r_sm}; min-height: {t.px(20)}px; }}
QComboBox QAbstractItemView::item:hover {{ background: {t.c("surface_hi")}; }}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: {t.px(26)}px;
    border: none;
    background: transparent;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {t.c("surface_hi")};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({chevron_png(t.c("text_dim"), 14, 2.0, True)});
    width: {t.px(12)}px; height: {t.px(12)}px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({chev});
    width: {t.px(12)}px; height: {t.px(12)}px;
}}

/* ===== خيارات ===== */
QCheckBox, QRadioButton {{ spacing: {t.s(10)}; color: {t.c("text")}; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {t.px(20)}px;
    height: {t.px(20)}px;
    border: {hair}px solid {t.c("line_strong")};
    background: {t.c("surface_alt")};
    border-radius: {r_sm};
}}
QRadioButton::indicator {{ border-radius: {t.px(10)}px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {gradient};
    border-color: {accent};
}}
QCheckBox::indicator:checked {{ image: url({check}); }}
QRadioButton::indicator:checked {{ image: url({dot}); }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {t.c("text_faint")}; }}

/* ===== التبويبات (شكل أشرطة جانبية أنيقة) ===== */
QTabWidget::pane {{
    border: {hair}px solid {t.c("line")};
    border-radius: {r_lg};
    background: {t.c("surface")};
    top: -1px;
}}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {t.c("text_dim")};
    border: {hair}px solid transparent;
    border-radius: {r_md};
    padding: {t.s(9)} {t.s(16)};
    margin: {gap};
    font-weight: 600;
}}
QTabBar::tab:hover {{ background: {t.c("surface_alt")}; color: {t.c("text")}; }}
QTabBar::tab:selected {{
    background: {t.alpha("accent", 0.14) if not t.high_contrast else t.c("surface_hi")};
    color: {accent if not t.high_contrast else t.c("text")};
    border-color: {t.alpha("accent", 0.45) if not t.high_contrast else t.c("line")};
}}

/* ===== أشرطة التمرير والتقدّم ===== */
QScrollBar:vertical {{ background: transparent; width: {t.px(12)}px; margin: {t.s(2)}; }}
QScrollBar::handle:vertical {{
    background: {t.c("line")};
    border-radius: {t.px(6)}px;
    min-height: {t.px(28)}px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.c("line_strong")}; }}
QScrollBar:horizontal {{ background: transparent; height: {t.px(12)}px; margin: {t.s(2)}; }}
QScrollBar::handle:horizontal {{
    background: {t.c("line")};
    border-radius: {t.px(6)}px;
    min-width: {t.px(28)}px;
}}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; width: 0; height: 0; border: none;
}}
QProgressBar {{
    background: {t.c("surface_alt")};
    border: {hair}px solid {t.c("line")};
    border-radius: {t.s(9)}px;
    height: {t.px(12)}px;
    text-align: center;
    color: {t.c("text_dim")};
}}
QProgressBar::chunk {{ background: {gradient}; border-radius: {t.s(8)}px; }}
QProgressBar[chunkAccent="state"]::chunk {{ background: {t.c("accent")}; }}

/* ===== القوائم ===== */
QMenu {{
    background-color: {t.c("surface")};
    color: {t.c("text")};
    border: {hair}px solid {t.c("line_strong")};
    border-radius: {r_md};
    padding: {t.s(7)};
}}
QMenu::item {{
    padding: {t.s(8)} {t.s(24)};
    border-radius: {r_sm};
    min-width: {t.px(160)}px;
}}
QMenu::item:selected {{
    background: {t.alpha("accent", 0.26) if not t.high_contrast else accent};
    color: {t.c("on_accent") if not t.high_contrast else t.c("text")};
}}
QMenu::item:disabled {{ color: {t.c("text_faint")}; }}
QMenu::separator {{ height: 1px; background: {t.c("line")}; margin: {t.s(5)} {t.s(8)}; }}
QMenu::icon {{ padding-left: {t.s(8)}; }}

/* ===== عناصر أخرى ===== */
QSpinBox, QDoubleSpinBox {{ text-align: {("right" if not t.high_contrast else "center")}; }}
QStatusBar {{ background: {t.c("surface")}; color: {t.c("text_dim")}; }}
QSlider::groove:horizontal {{ height: {t.px(6)}px; background: {t.c("surface_alt")}; border-radius: {t.px(3)}px; }}
QSlider::handle:horizontal {{
    width: {t.px(18)}px; margin: {t.s(-6)} 0; border-radius: {t.px(9)}px; background: {accent};
}}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: {t.px(3)}px; }}
"""
