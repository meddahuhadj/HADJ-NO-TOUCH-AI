"""نقطة الدخول: التحكم في الحاسوب بدون لمس (صوت + إيماءات)، دون إنترنت."""
from __future__ import annotations

import logging
import multiprocessing
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import offline_guard, paths  # noqa: E402


def setup_logging(debug: bool) -> None:
    log_dir = paths.user_dir() / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:
        try:   # وإلا تظهر العربية كرموز \u في بعض الطرفيات
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
        handlers.append(logging.StreamHandler())
    # ملاحظة خصوصية: نص الكلام لا يُسجَّل إلا في وضع DEBUG
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, handlers=handlers,
                        format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s")
    # أي انهيار أصلي (segfault) يُكتب مع مكدّس كل الخيوط في crash.log
    import faulthandler
    global _crash_file
    _crash_file = open(log_dir / "crash.log", "a", encoding="utf-8")  # noqa: SIM115
    faulthandler.enable(_crash_file, all_threads=True)


_crash_file = None


def main() -> int:
    offline_guard.install()
    setup_logging("--debug" in sys.argv)
    if "--selftest" in sys.argv:
        from core import selftest
        return selftest.run()
    from core import instance
    cmd = instance.cli_command(sys.argv)
    if cmd:   # HADJ-NoTouch --pause | --resume | --toggle-pause | --show ← للنسخة العاملة
        from PySide6.QtCore import QCoreApplication
        QCoreApplication(sys.argv)
        ok = instance.send_command(cmd)
        print("ok" if ok else "HADJ No-Touch is not running or did not answer")
        return 0 if ok else 2
    log = logging.getLogger("main")

    from PySide6.QtCore import QLockFile, Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox

    from config.loader import load_config
    from core.controller import Controller
    from os_layer.factory import create_backend
    from ui.i18n import Tr
    from ui.tray import Bridge, TrayApp

    config = load_config()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")   # أنماط Qt المتسقة: QSS يتصرّف على كل المنصّات بنفس الشكل
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("HADJ No-Touch")
    tr = Tr(config.ui.ui_language)
    if tr.rtl:
        app.setLayoutDirection(Qt.RightToLeft)
    from ui.theme import apply_palette, get_app_stylesheet
    font = QFont("Segoe UI")
    font.setPointSizeF(10.5 * config.ui.font_scale)
    app.setFont(font)
    apply_palette(app, config.ui.font_scale, config.ui.high_contrast)
    app.setStyleSheet(get_app_stylesheet(config.ui.font_scale, config.ui.high_contrast))

    lock = QLockFile(str(paths.user_dir() / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        # النسخة العاملة تُظهر لوحتها؛ الرسالة فقط إن تعذّر الاتصال بها
        if not instance.send_command("show"):
            QMessageBox.information(None, tr("app_name"), tr("already_running"))
        return 0

    bridge = Bridge()
    controller = Controller(create_backend(), bridge.notify, config)
    controller.vision_dry_run = "--vision-dry-run" in sys.argv
    ui = TrayApp(app, controller, bridge)  # noqa: F841 - يجب أن يبقى حياً

    def on_command(command: str) -> None:
        paused = controller.paused.is_set()
        if command == "pause" and not paused:
            controller.pause()
        elif command == "resume" and paused:
            controller.resume()
        elif command == "toggle-pause":
            controller.toggle_pause()
        elif command == "show":
            ui.show_panel()
    commands = instance.CommandServer(on_command)  # noqa: F841 - يجب أن يبقى حياً
    controller.start()
    log.info("بدأ التطبيق (اللغة=%s)", config.speech.language)
    if "--exit-after" in sys.argv:  # للاختبار: خروج نظيف بعد N ثانية
        from PySide6.QtCore import QTimer
        secs = float(sys.argv[sys.argv.index("--exit-after") + 1])
        QTimer.singleShot(int(secs * 1000), ui.quit)
    try:
        code = app.exec()
    finally:
        controller.shutdown()
        lock.unlock()
    # بعد انتهاء التنظيف الفعلي (العمليات الفرعية، القفل، السجلات): خروج مباشر.
    # تفريغ مكتبات DLL عند نهاية العملية كان يسبب أحياناً انهياراً أصلياً (access violation)
    # داخل os._exit نفسها، دون أي فائدة لأن كل شيء قد حُفظ وأُغلق.
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr, _crash_file):
        if stream is not None:
            stream.flush()
    controller.os.hard_exit(code)
    return code  # لا يُبلغ عادةً (hard_exit ينهي العملية)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
