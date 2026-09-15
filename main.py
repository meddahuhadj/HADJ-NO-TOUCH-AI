"""HADJ NO-TOUCH AI — application entry point.

Runs the PySide6 desktop application. Processing stays local by default;
no camera frames or audio are uploaded.

Startup is staged so the window appears almost instantly:
1. A lightweight splash window is shown first.
2. The event loop gets a paint pass before the heavy core is built.
3. MediaPipe models load lazily on first frame (background thread).
"""

from __future__ import annotations

import ctypes
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
    """Builds MainWindow after the splash has been painted on screen.

    Unowned QTimer.singleShot callbacks are fragile in a frozen build, so the
    timers live on this object (kept alive) and every stage logs to the app
    log file — otherwise a silent stall is impossible to diagnose.
    """

    def __init__(self, app, splash):
        self.app = app
        self.splash = splash
        self.window = None
        self.started = False
        from hadj_no_touch.logging_setup import get_logger
        self.log = get_logger("startup")
        from PySide6.QtCore import QTimer
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._paint_idle)
        self._timer.start(0)
        self._timer2 = QTimer()
        self._timer2.setSingleShot(True)
        self._timer2.timeout.connect(self._start_late)
        self.log.info("staged startup scheduled")

    def _set(self, text: str) -> None:
        try:
            self.splash._status_label.setText(text)
            self.app.processEvents()
        except Exception:
            pass

    def _paint_idle(self) -> None:
        self.log.info("building main window")
        self._set("Loading models & core …")

        from hadj_no_touch.ui.main_window import MainWindow
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()          # paint the main window first

        self._set("Starting camera & trackers …")
        self.log.info("main window shown; scheduling core start")
        self._timer2.start(50)

    def _start_late(self) -> None:
        self.log.info("calling core start")
        try:
            self.window.start()
        except Exception:
            import traceback
            self.log.error("core start crashed:\n%s", traceback.format_exc())
            raise
        self.started = True
        self.log.info("core started successfully")
        self.splash.hide()
        self.splash.close()


def _claim_single_instance() -> bool:
    """Return True when this is the first running instance.

    Multiple HADJ windows (e.g. old ZIP copies in Downloads) fight over the
    same webcam/microphone, which shows up as "camera green, FPS 0, others
    red". A named mutex guarantees exactly one instance per user session.
    """
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_wchar_p]
        k32.CreateMutexW.restype = ctypes.c_void_p
        handle = k32.CreateMutexW(None, False, "Local\\HADJ_NO_TOUCH_AI_SINGLE")
        if not handle:
            return True
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            k32.CloseHandle(handle)
            return False
        global _SINGLE_INSTANCE_HANDLE
        _SINGLE_INSTANCE_HANDLE = handle  # keep open for the app lifetime
        return True
    except Exception:
        return True  # never block in weird environments


_SINGLE_INSTANCE_HANDLE = None


def main() -> int:
    _bootstrap()
    _check_python()

    if not _claim_single_instance():
        # Inform briefly, then auto-exit so no zombie process lingers.
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        box = QMessageBox(
            QMessageBox.Icon.Information, "HADJ NO-TOUCH AI",
            "HADJ NO-TOUCH AI is already running — check the system tray.\n\n"
            "L'application est déjà ouverte — regardez la barre des tâches.")
        box.setModal(False)
        box.show()
        QTimer.singleShot(4000, app.quit)
        app.exec()
        return 0

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

    _stager = _StagedStartup(app, splash)  # kept alive by the timers

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())