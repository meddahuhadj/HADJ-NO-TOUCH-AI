import sys
import os
import glob

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Preferred interpreters, most specific first. The previous single hardcoded
# path only worked on one machine; this finds whatever Python 3.12 install
# exists and falls back to the current interpreter.
PY312_GLOBS = (
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe"),
    r"C:\Python312\python.exe",
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Python312", "python.exe"),
)


def _runtime_available() -> bool:
    try:
        import PySide6
        import mediapipe as mp
        if not hasattr(mp, 'solutions'):
            raise ImportError("mediapipe.solutions missing")
        return True
    except (ModuleNotFoundError, ImportError, AttributeError):
        return False


def _candidate_interpreters():
    seen = set()
    for pattern in PY312_GLOBS:
        for path in glob.glob(pattern) or ([pattern] if os.path.isfile(pattern) else []):
            key = os.path.normcase(os.path.abspath(path))
            if key not in seen:
                seen.add(key)
                yield path


def _reexec_with_runtime():
    """Re-runs this script under a Python that has PySide6 and mediapipe."""
    import subprocess

    for interpreter in _candidate_interpreters():
        if os.path.normcase(interpreter) == os.path.normcase(sys.executable):
            continue
        try:
            return subprocess.call([interpreter] + sys.argv)
        except Exception:
            continue
    return None


if not _runtime_available():
    _exit_code = _reexec_with_runtime()
    if _exit_code is None:
        print(
            "[HADJ] PySide6 or mediapipe is missing and no Python 3.12 runtime was "
            "found.\n       Install the dependencies with:\n"
            f"       \"{sys.executable}\" -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(_exit_code)

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QLockFile, QDir
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HADJ NO-TOUCH OFFLINE AI")
    app.setOrganizationName("HADJ AI Systems")

    # Single-instance lock: prevents camera access collisions.
    # A stale lock time of 0 means a lock left behind by a crash is never
    # broken automatically, so the check below also probes the port-free case
    # by reporting clearly instead of exiting silently.
    lock_path = os.path.join(QDir.tempPath(), "hadj_notouch_ai.lock")
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        # Auto-remove stale lock if the process that created it is dead
        lock.removeStaleLockFile()
        if not lock.tryLock(100):
            QMessageBox.warning(
                None,
                "HADJ NO-TOUCH AI",
                "Une instance de HADJ NO-TOUCH AI est déjà en cours d'exécution.\n"
                "Veuillez fermer l'autre instance pour libérer la caméra.\n\n"
                "Si aucune fenêtre n'est ouverte, le fichier de verrou\n"
                f"({lock_path}) peut être supprimé."
            )
            lock.unlock()
            sys.exit(0)

    window = MainWindow()

    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    try:
        code = app.exec()
    finally:
        # Unlock in a finally block: an exception during startup or a crash
        # would otherwise leave a lock that blocks the next launch.
        lock.unlock()
    sys.exit(code)


if __name__ == "__main__":
    main()
