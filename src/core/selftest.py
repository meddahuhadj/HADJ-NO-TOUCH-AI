"""فحص ذاتي: تحميل كل نموذج وتشغيله مرة، وكتابة تقرير في user_data/logs/selftest.txt.

    HADJ-NoTouch.exe --selftest

مفيد بعد النقل لجهاز جديد، ولكشف مكتبة ناقصة في النسخة المحمولة.
لا يستخدم الميكروفون ولا الكاميرا (يكتفي بسردها)، ولا يحتاج شبكة.
"""
from __future__ import annotations

import socket
import time
import traceback

from core import offline_guard, paths


def _check(name: str, fn, report: list[str]) -> bool:
    t = time.monotonic()
    try:
        detail = fn()
        report.append(f"✓ {name}  ({time.monotonic() - t:.1f}s)  {detail or ''}")
        return True
    except Exception as e:  # noqa: BLE001
        report.append(f"✗ {name}: {e}")
        report.append("   " + traceback.format_exc().strip().replace("\n", "\n   "))
        return False


def run() -> int:
    report: list[str] = [f"HADJ No-Touch self-test  {time.strftime('%Y-%m-%d %H:%M:%S')}",
                         f"app: {paths.app_root()}", ""]
    models = paths.models_dir()
    ok = True

    def guard():
        offline_guard.install()
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=1)
        except offline_guard.OfflineViolation:
            return "external connections blocked"
        raise RuntimeError("اتصال خارجي لم يُمنع")

    def vosk(lang):
        def f():
            from audio.recognizer import VoskRecognizer
            rec = VoskRecognizer(models / "vosk" / lang, 16000, ["test"], "auto")
            rec.accept(b"\0" * 32000)
            rec.finish()
            return f"grammar={rec.grammar_enabled}"
        return f

    def hands():
        from config.schema import VisionConfig
        from vision.worker import HandTracker
        import numpy as np
        tr = HandTracker(models / "mediapipe" / "hand_landmarker.task", VisionConfig())
        found = tr.detect(np.zeros((480, 640, 3), np.uint8), 1.0)
        tr.close()
        return f"hands on blank image: {len(found)}"

    def whisper():
        from audio.dictation import WhisperTranscriber
        from config.loader import load_config
        name = load_config().dictation.whisper_model
        w = WhisperTranscriber(models / "whisper" / name)
        text = w.transcribe(b"\0" * 32000, "ar")
        return f"model={name}, silence → {text!r}"

    def mics():
        from audio.capture import list_input_devices
        return ", ".join(list_input_devices()) or "(none)"

    def apps():
        from os_layer.factory import create_backend
        return f"{len(create_backend().list_apps())} start-menu apps"

    for name, fn in [("offline guard", guard), ("vosk ar", vosk("ar")), ("vosk en", vosk("en")),
                     ("mediapipe hand landmarker", hands), ("whisper", whisper),
                     ("microphones (WinMM)", mics), ("app index", apps)]:
        ok &= _check(name, fn, report)
    report += ["", "RESULT: " + ("OK" if ok else "FAILED")]
    out = paths.user_dir() / "logs" / "selftest.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report), encoding="utf-8")
    return 0 if ok else 1
