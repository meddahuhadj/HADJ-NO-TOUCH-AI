"""تحويل عبارات الإملاء إلى نص بـ Whisper في خيط مستقل داخل عملية الصوت.

التحويل بطيء على المعالج (ثوانٍ لكل عبارة)، لذلك:
- حلقة الميكروفون لا تتوقف أبداً؛ العبارات تنتظر في طابور وتُحوَّل بالترتيب.
- النموذج يُحمَّل عند بدء الإملاء فقط ويُحرَّر عند انتهائه (توفير ~500MB من الذاكرة).
الصوت يبقى في الذاكرة فقط.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

from commands.dictation import is_hallucination
from core.events import DictationEvent, StatusEvent

log = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self, model_dir: Path, threads: int = 0, beam_size: int = 1):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")   # لا محاولة تنزيل أبداً
        from faster_whisper import WhisperModel
        if not (model_dir / "model.bin").exists():
            raise FileNotFoundError(f"نموذج Whisper غير موجود: {model_dir}")
        threads = threads or max(1, min(4, (os.cpu_count() or 2) - 1))
        self.model = WhisperModel(str(model_dir), device="cpu", compute_type="int8",
                                  cpu_threads=threads, local_files_only=True)
        self.beam_size = beam_size

    def transcribe(self, pcm: bytes, lang: str) -> str:
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            audio, language=lang, beam_size=self.beam_size, condition_on_previous_text=False,
            without_timestamps=True, vad_filter=False)
        parts = []
        for s in segments:
            if not is_hallucination(s.text, s.no_speech_prob, s.avg_logprob):
                parts.append(s.text.strip())
        text = " ".join(parts).strip()
        return "" if is_hallucination(text) else text


class DictationThread:
    """خيط يحمّل Whisper ثم يحوّل العبارات من الطابور بالترتيب."""

    def __init__(self, model_dir: Path, emit: Callable[[object], None], threads: int = 0,
                 beam_size: int = 1, factory=WhisperTranscriber):
        self.emit = emit
        self.jobs: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._args = (model_dir, threads, beam_size)
        self._factory = factory
        self.thread = threading.Thread(target=self._run, daemon=True, name="whisper")
        self.thread.start()

    def submit(self, seg_id: int, pcm: bytes, lang: str) -> None:
        self.jobs.put((seg_id, pcm, lang))

    def stop(self) -> None:
        """ينهي الخيط بعد تحويل ما في الطابور (ما قيل قبل "أوقف الإملاء" لا يضيع)."""
        self.jobs.put(None)

    def abort(self) -> None:
        """إيقاف فوري دون تحويل ما تبقى (للإيقاف الطارئ)."""
        self._stop.set()
        self.jobs.put(None)

    def _run(self) -> None:
        self.emit(StatusEvent("dictation", "loading"))
        t = time.monotonic()
        try:
            model = self._factory(*self._args)
        except Exception as e:  # noqa: BLE001
            log.exception("فشل تحميل Whisper")
            self.emit(StatusEvent("dictation", "error", str(e)))
            return
        log.info("Whisper جاهز خلال %.1fs", time.monotonic() - t)
        self.emit(StatusEvent("dictation", "ready"))
        while not self._stop.is_set():
            job = self.jobs.get()
            if job is None:
                break
            seg_id, pcm, lang = job
            t = time.monotonic()
            try:
                text = model.transcribe(pcm, lang)
            except Exception:  # noqa: BLE001
                log.exception("فشل تحويل عبارة")
                text = ""
            dt = time.monotonic() - t
            log.info("إملاء: %.1fs صوت ← %.1fs تحويل", len(pcm) / 32000, dt)
            self.emit(DictationEvent(text, seg_id, lang, "whisper", dt))
        del model   # تحرير الذاكرة
