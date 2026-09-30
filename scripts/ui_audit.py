"""فحص آلي لمظهر الواجهة: ألوان البكسل + تجاوز النص + أهداف النقر.

لا يحتاج رؤية الصور: يتحقق من القيم المتوقّعة في مواضع محدّدة، ومن أن كل نص
داخل حدوده، وأن أهداف النقر كبيرة بما يكفي للإيماءات.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QPushButton,  # noqa: E402
                               QWidget)

FAIL: list[str] = []
OK: list[str] = []


def check(cond: bool, msg: str) -> None:
    (OK if cond else FAIL).append(msg)


def hexc(c: QColor) -> str:
    return f"#{c.red():02x}{c.green():02x}{c.blue():02x}"


def near(img, x, y, expected: str, tol: int = 26) -> bool:
    c = QColor(img.pixel(int(x), int(y)))
    e = QColor(expected)
    return (abs(c.red() - e.red()) <= tol and abs(c.green() - e.green()) <= tol
            and abs(c.blue() - e.blue()) <= tol)


def near_color(c: QColor, expected: str, tol: int = 26) -> bool:
    e = QColor(expected)
    return (abs(c.red() - e.red()) <= tol and abs(c.green() - e.green()) <= tol
            and abs(c.blue() - e.blue()) <= tol)


def report() -> int:
    for m in OK:
        print("  ok   ", m)
    for m in FAIL:
        print("  FAIL ", m)
    print(f"\n{len(OK)} ok / {len(FAIL)} fail")
    return 1 if FAIL else 0


def audit_layout(widget: QWidget, name: str, min_target: int = 44) -> None:
    """النص لا يُقصّ، وأهداف النقر كبيرة."""
    for w in (widget.findChildren(QLabel) + widget.findChildren(QPushButton)
              + widget.findChildren(QLineEdit)):
        if not w.isVisible() or w.width() <= 0:
            continue
        hint = w.sizeHint()
        if isinstance(w, QLabel) and not w.wordWrap():
            if hint.width() > w.width() + 1:
                FAIL.append(f"{name}: نص مقطوع في {w.text()[:24]!r} "
                             f"({hint.width()}>{w.width()})")
        if isinstance(w, QPushButton) and w.height() < min_target:
            FAIL.append(f"{name}: زر صغير {w.text()[:18]!r} h={w.height()}")
    check(True, f"{name}: تم فحص {len(widget.findChildren(QLabel))} تسمية")


def snap(w: QWidget) -> QImage:
    """يلتقط العنصر كما يظهر فعلاً.

    ``QWidget.grab()`` يرسم خلفية النافذة (``QPalette::Window``) أولاً، فيخفي
    شفافية البطاقات ويبتلع ما لو-layer تحتها. نرسم الأبناء فقط بلا تلك الخلفية.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPainter, QPixmap, QRegion
    app = QApplication.instance()
    app.processEvents()
    pm = QPixmap(w.size())
    pm.fill(Qt.transparent)
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    w.setAttribute(Qt.WA_NoSystemBackground, True)
    w.ensurePolished()
    for child in w.findChildren(QWidget):
        child.ensurePolished()
    painter = QPainter(pm)
    w.render(painter, QPoint())
    painter.end()
    return pm.toImage()


def _center(top: QWidget, child: QWidget) -> tuple[int, int]:
    """مركز عنصر بإحداثيات النافذة (mapTo يمرّ عبر كل الحاويات)."""
    c = child.mapTo(top, child.rect().center())
    return c.x(), c.y()


def checkmark_present(img, rect, tag: str) -> None:
    """يبحث عن علامة الصح: مربّع بلون التمييز يحوي بكسلات فاتحة/داكنة شاذة عنه."""
    left, top, right, bottom = rect
    accent, found = [], False
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            c = QColor(img.pixel(x, y))
            if (abs(c.red() - 0x4C) < 46 and abs(c.green() - 0x8D) < 46 and abs(c.blue() - 0xFF) < 46) or (abs(c.red() - 0x00) < 46 and abs(c.green() - 0xFF) < 46 and abs(c.blue() - 0x66) < 46):
                accent.append((x, y))
    if accent:
        xs = [a[0] for a in accent]
        ys = [a[1] for a in accent]
        inside = 0
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                c = QColor(img.pixel(x, y))
                if c.lightness() > 240 or c.lightness() < 20:
                    inside += 1
        found = inside > 6
    check(found, f"[{tag}] إعدادات: علامة صح داخل مربع الاختيار ({len(accent)} بكسل تمييز)")


def main() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    from config import loader
    from config.schema import AppConfig
    from ui.control_panel import ControlPanel
    from ui.icons import STATE_COLORS, state_icon
    from ui.i18n import Tr
    from ui.overlay import ConfirmWindow, Overlay
    from ui.settings_window import SettingsWindow
    from ui.theme import apply_palette, get_app_stylesheet, theme

    def config(hc=False, scale=1.0) -> AppConfig:
        base = loader.read_yaml(loader.default_config_path())
        base["ui"]["high_contrast"] = hc
        base["ui"]["font_scale"] = scale
        return AppConfig.model_validate(base)

    for lang, hc, scale, tag in (("ar", False, 1.0, "ar"), ("ar", True, 1.0, "hc"),
                                 ("en", False, 1.4, "big")):
        c = config(hc, scale)
        app.setFont(QFont("Segoe UI", int(10.5 * scale)))
        app.setLayoutDirection(Qt.RightToLeft if Tr(lang).rtl else Qt.LeftToRight)
        apply_palette(app, scale, hc)
        app.setStyleSheet(get_app_stylesheet(scale, hc))
        th = theme(scale, hc)
        tr = Tr(lang)
        top, bottom = ("#0b0b0b", "#000000") if hc else ("#182340", "#0e1729")

        # ---------- اللوحة ----------
        panel = ControlPanel(tr, scale, hc)
        panel.set_state("ready", tr("state_ready", wake="حاسوب"), tr("cam_tracking"), False, None)
        panel.set_heard("افتح المتصفح")
        panel.show()
        img = snap(panel)
        w, h = img.width(), img.height()
        corner = QColor(img.pixel(0, 0))
        check(corner.alpha() < 14, f"[{tag}] اللوحة: زاوية شفافة (a={corner.alpha()}) = ظل ناعم")
        check(near(img, w // 2, th.px(30), top, 30), f"[{tag}] اللوحة: سطح البطاقة العلوي")
        check(near(img, w // 2, h - th.px(30), bottom, 30), f"[{tag}] اللوحة: تدرّج البطاقة للأسفل")
        b = panel.buttons["dictation"]
        tl = b.mapTo(panel, b.rect().topLeft())
        left = QColor(img.pixel(tl.x() + th.px(24), tl.y() + b.height() // 2))
        right = QColor(img.pixel(tl.x() + b.width() - th.px(24), tl.y() + b.height() // 2))
        check(left.blue() > left.red() + 40 and right.blue() > right.red() + 40,
              f"[{tag}] اللوحة: الزر الأساسي بتدرّج الهوية ({hexc(left)}→{hexc(right)})")
        check(b.height() >= th.px(50), f"[{tag}] اللوحة: زر الإملاء h={b.height()} ≥ هدف الإيماءات")
        orb_c = QColor(img.pixel(*_center(panel, panel.orb)))
        check(near_color(orb_c, th.state("ready"), 70),
              f"[{tag}] اللوحة: كرة الحالة بلون الحالة ({hexc(orb_c)})")
        audit_layout(panel, f"[{tag}] لوحة")

        # ---------- الشريط ----------
        ov = Overlay(tr, scale, hc)
        ov.show_message("افتح المفكرة", "تم", state="ready", color="ok")
        oi = snap(ov)
        check(QColor(oi.pixel(0, 0)).alpha() < 14, f"[{tag}] HUD: زوايا شفافة")
        check(near(oi, oi.width() // 2, 6, top, 30), f"[{tag}] HUD: بطاقة زجاجية")
        dot = ov._accent.center()
        dc = QColor(oi.pixel(int(dot.x()), int(dot.y())))
        check(near_color(dc, th.c("ok"), 90),
              f"[{tag}] HUD: نقطة الحالة بلون النتيجة ({hexc(dc)})")
        bar = QColor(oi.pixel(2 if not tr.rtl else oi.width() - 3, oi.height() // 2))
        check(near_color(bar, th.c("ok"), 90),
              f"[{tag}] HUD: شريط الحالة الجانبي ({hexc(bar)})")
        check(oi.height() >= th.px(60), f"[{tag}] HUD: ارتفاع مقروء {oi.height()}")

        # ---------- التأكيد ----------
        cf = ConfirmWindow(tr, scale, hc)
        cf.ask("احذف الملف")
        cf.show()
        ci = snap(cf)
        check(QColor(ci.pixel(0, 0)).alpha() < 14, f"[{tag}] تأكيد: زوايا شفافة")
        yes = cf.findChild(QPushButton, "confirmYes")
        spot = yes.mapTo(cf, yes.rect().topLeft())
        yc = QColor(ci.pixel(spot.x() + th.px(30), spot.y() + yes.height() // 2))
        check(near_color(yc, "#2fbf83" if not hc else "#00ff66", 70),
              f"[{tag}] تأكيد: زر «نعم» أخضر بارز ({hexc(yc)})")
        check(yes.height() >= th.px(52), f"[{tag}] تأكيد: زر كبير h={yes.height()}")
        audit_layout(cf, f"[{tag}] تأكيد")

        # ---------- المعايرة ----------
        from ui.calibration_wizard import CalibrationWizard
        wiz = CalibrationWizard(tr, scale, hc)
        wiz.show()
        wiz.step_label.setText(tr("calib_step_pinch"))
        wiz.progress.setValue(120)
        wi = snap(wiz)
        check(QColor(wi.pixel(0, 0)).alpha() < 14, f"[{tag}] معايرة: زوايا شفافة")
        check(wi.height() >= th.px(260), f"[{tag}] معايرة: بطاقة كبيرة")
        audit_layout(wiz, f"[{tag}] معايرة")

        # ---------- الإعدادات ----------
        st = SettingsWindow(tr, c, ROOT / "models", ["Mic A", "Mic B"], on_save=lambda d: None)
        st.show()
        si = snap(st)
        check(near(si, si.width() // 2, 6, th.c("canvas")), f"[{tag}] إعدادات: خلفية النافذة")
        from PySide6.QtWidgets import QTabWidget
        tabs = st.findChild(QTabWidget)
        origin = tabs.mapTo(st, QPoint(4, 4))
        inner = QColor(si.pixel(origin.x() + tabs.width() // 2, origin.y() + tabs.height() // 2))
        check(inner.lightness() < 70, f"[{tag}] إعدادات: داخل التبويب داكن ({hexc(inner)})")
        cb = st.continuous
        cb.setChecked(True)
        si2 = snap(st)
        o = cb.mapTo(st, cb.rect().topLeft())
        checkmark_present(si2, (o.x(), o.y(), o.x() + cb.width(), o.y() + cb.height()), tag)
        audit_layout(st, f"[{tag}] إعدادات")
        st.close()

    # ---------- الأيقونات ----------
    for state in STATE_COLORS:
        pm = state_icon(state, 64).pixmap(64, 64)
        if pm.isNull():
            FAIL.append(f"أيقونة {state} فارغة")
    strip = QPixmap(STATE_COLORS.__len__() * 72, 72)
    strip.fill(Qt.transparent)
    p = QPainter(strip)
    for i, state in enumerate(STATE_COLORS):
        p.drawPixmap(i * 72, 4, state_icon(state, 64).pixmap(64, 64))
    p.end()
    strip.save(str(ROOT / "ui_preview" / "icons.png"))
    check(True, "أيقونات الحالات الثماني مرسومة")

    return report()


if __name__ == "__main__":
    sys.exit(main())

