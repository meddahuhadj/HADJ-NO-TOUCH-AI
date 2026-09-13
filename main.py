"""HADJ NO-TOUCH AI — application entry point.

Runs the PySide6 desktop application. Processing stays local by default;
no camera frames or audio are uploaded.
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


def main() -> int:
    _bootstrap()
    _check_python()

    from PySide6.QtWidgets import QApplication

    from hadj_no_touch.ui.main_window import MainWindow
    from hadj_no_touch.logging_setup import setup_logging

    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("HADJ NO-TOUCH AI")
    app.setOrganizationName("HADJ")
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray

    window = MainWindow()
    window.show()
    window.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())