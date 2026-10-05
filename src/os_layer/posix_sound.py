"""تشغيل أصوات wav على macOS وLinux عبر sounddevice (مثبّتة أصلاً هناك لالتقاط الميكروفون).

بديل winsound لطبقات النظام القادمة. التشغيل في خيط منفصل: لا يوقف المستدعي أبداً.
"""
from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path

log = logging.getLogger(__name__)


def read_wav(path: Path):
    """(عينات int16 كمصفوفة numpy، معدل العينة)."""
    import numpy as np
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"wav 16-bit فقط: {path}")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels())
        return data, w.getframerate()


def play_wav(path: Path) -> threading.Thread:
    def run():
        try:
            import sounddevice as sd
            data, rate = read_wav(path)
            sd.play(data, rate)
            sd.wait()
        except Exception:  # noqa: BLE001 - صوت التأكيد لا يجب أن يُسقط التطبيق
            log.debug("تعذّر تشغيل %s", path, exc_info=True)
    t = threading.Thread(target=run, daemon=True, name="sound")
    t.start()
    return t
