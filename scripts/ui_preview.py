"""معاينة بصرية للواجهة: يلتقط صوراً لكل شاشة في أوضاع مختلفة للمراجعة.

    python scripts/ui_preview.py [مجلد الإخراج]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "ui_preview")
OUT.mkdir(parents=True, exist_ok=True)


def cfg(high_contrast=False, font_scale=1.0):
    from config.schema import AppConfig
    from core import paths
    from config import loader
    base = loader.read_yaml(loader.default_config_path())
    base["ui"]["high_contrast"] = high_contrast
    base["ui"]["font_scale"] = font_scale
    return AppConfig.model_validate(base)


def shot(widget, name: str) -> None:
    QApplication.processEvents()
    widget.adjustSize()
    QApplication.processEvents()
    img = widget.grab()
    path = OUT / f"{name}.png"
    img.save(str(path))
    print(f"{name:38s} {img.width():4d}x{img.height():4d}  -> {path.name}")


def main() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    from ui.i18n import Tr
    from ui.icons import state_icon
    from ui.theme import get_app_stylesheet

    for lang, hc, scale, tag in (("ar", False, 1.0, "ar"), ("en", False, 1.0, "en"),
                                 ("ar", True, 1.0, "hc"), ("ar", False, 1.7, "big")):
        c = cfg(hc, scale)
        app.setFont(QFont("Segoe UI", int(10.5 * scale)))
        app.setLayoutDirection(Qt.RightToLeft if Tr(lang).rtl else Qt.LeftToRight)
        app.setStyleSheet(get_app_stylesheet(scale, hc))

        from ui.control_panel import ControlPanel
        from ui.overlay import ConfirmWindow, Overlay
        from ui.settings_window import SettingsWindow
        from ui.calibration_wizard import CalibrationWizard

        tr = Tr(lang)
        panel = ControlPanel(tr, scale, hc)
        panel.set_state("ready", tr("state_ready", wake="حاسوب"),
                        tr("cam_tracking"), False, None)
        panel.set_heard("افتح المتصفح")
        panel.show()
        shot(panel, f"panel_{tag}")

        ov = Overlay(tr, scale, hc)
        ov.show_message("افتح المفكرة", "تم ✓", state="ready", color="ok")
        shot(ov, f"hud_{tag}")

        cf = ConfirmWindow(tr, scale, hc)
        cf.ask("احذف الملف")
        shot(cf, f"confirm_{tag}")

        wiz = CalibrationWizard(tr, scale, hc)
        wiz.show()
        wiz.step_label.setText(tr("calib_step_pinch"))
        wiz.title.setText(f"{tr('calib_title')} · 2/4")
        wiz.dots.set_current(1)
        wiz.progress.setValue(120)
        shot(wiz, f"wizard_{tag}")

        st = SettingsWindow(tr, c, ROOT / "models", ["Mic A", "Mic B"], on_save=lambda d: None,
                            on_calibrate=lambda: None, on_open_folder=lambda: None)
        st.show()
        shot(st, f"settings_{tag}")
        if _switch_tab(st, 2):
            shot(st, f"settings_{tag}_camera")

    # أيقونات شريط النظام
    from PySide6.QtGui import QPainter, QPixmap

    from ui.icons import STATE_COLORS
    strip = QPixmap(len(STATE_COLORS) * 96, 128)
    strip.fill(Qt.transparent)
    p = QPainter(strip)
    for i, name in enumerate(STATE_COLORS):
        p.drawPixmap(i * 96, 16, state_icon(name, 96).pixmap(96, 96))
    p.end()
    strip.save(str(OUT / "icons.png"))
    print("icons.png")
    return 0


def _switch_tab(window, index: int) -> bool:
    from PySide6.QtWidgets import QTabWidget
    tabs = window.findChildren(QTabWidget)
    if not tabs:
        return False
    tabs[0].setCurrentIndex(index)
    QApplication.processEvents()
    return True


if __name__ == "__main__":
    sys.exit(main())
