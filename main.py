import sys
import os

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Auto-detect and re-exec with Python 3.12 if current Python lacks PySide6 or mediapipe solutions
try:
    import PySide6
    import mediapipe as mp
    if not hasattr(mp, 'solutions'):
        raise ImportError("mediapipe.solutions missing")
except (ModuleNotFoundError, ImportError, AttributeError):
    py312 = r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
    if os.path.exists(py312) and sys.executable.lower() != py312.lower():
        import subprocess
        sys.exit(subprocess.call([py312] + sys.argv))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HADJ NO-TOUCH OFFLINE AI")
    app.setOrganizationName("HADJ AI Systems")

    window = MainWindow()

    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
