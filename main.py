"""HADJ NO-TOUCH AI — application entry point.

Runs the PySide6 desktop application. Processing stays local by default;
no camera frames or audio are uploaded.

Startup is staged so the window appears almost instantly:
1. A lightweight splash window is shown first.
2. The event loop gets a paint pass before the heavy core is built.
3. MediaPipe models load lazily on first frame (background thread).
"""

from __future__ import annotations

import os
import sys


def _bootstrap() -> None:
    """Make the project root importable when launched as ``python main.py``."""
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def _check_python() -> None:
    """MediaPipe does not support Python 3.13+ yet; fail fast with a hint."""
    if not (3, 10) <= sys.version_info[:2] < (3, 13):
        print(
            "HADJ NO-TOUCH AI requires Python 3.10, 3.11 or 3.12 "
            "(MediaPipe does not support this interpreter yet).\n"
            f"Found: {sys.version.split()[0]}.\n"
            "Tip: run with `py -3.12 main.py` if Python 3.12 is installed.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _make_splash(parent=None):
    """A tiny, dependency-free splash shown while the core initialises."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    w = QWidget(parent)
    w.setWindowFlags(Qt.WindowType.FramelessWindowHint
                     | Qt.WindowType.WindowStaysOnTopHint)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setFixedSize(340, 140)

    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)

    card = QWidget(w)
    card.setStyleSheet(
        "background: #0b1622; border: 1px solid #2a4a74; border-radius: 16px;")
    cl = QVBoxLayout(card)
    cl.setContentsMargins(24, 20, 24, 20)
    cl.setSpacing(6)

    brand = QLabel("HADJ NO-TOUCH AI")
    f = QFont()
    f.setBold(True)
    f.setPointSize(16)
    brand.setFont(f)
    brand.setStyleSheet("color: #7cc3ff;")
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

    sub = QLabel("Starting · contactless control …")
    sub.setStyleSheet("color: #5f7ea0;")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

    cl.addWidget(brand)
    cl.addWidget(sub)
    lay.addWidget(card)

    w._status_label = sub
    w._brand = brand
    return w


class _StagedStartup:
    """Builds MainWindow after the splash has been painted on screen."""

    def __init__(self, app, splash):
        self.app = app
        self.splash = splash
        self.window = None
        self.started = False
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._paint_idle)

    def _set(self, text: str) -> None:
        try:
            self.splash._status_label.setText(text)
            self.app.processEvents()
        except Exception:
            pass

    def _paint_idle(self) -> None:
        self._set("Loading models & core …")

        from hadj_no_touch.ui.main_window import MainWindow
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()          # paint the main window first

        self._set("Starting camera & trackers …")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._start_late)

    def _start_late(self) -> None:
        self.window.start()
        self.started = True
        self.splash.hide()
        self.splash.close()


def main() -> int:
    _bootstrap()
    _check_python()

    from PySide6.QtWidgets import QApplication

    from hadj_no_touch.logging_setup import setup_logging

    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("HADJ NO-TOUCH AI")
    app.setOrganizationName("HADJ")
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray

    splash = _make_splash()
    splash.show()
    app.processEvents()

    _StagedStartup(app, splash)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())