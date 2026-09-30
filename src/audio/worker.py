"""عملية الصوت: ميكروفون ← VAD ← Vosk ← SpeechEvent في طابور الأحداث.

الصوت يبقى في الذاكرة فقط ولا يُحفظ على القرص أبداً.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from audio.vad import FRAME_BYTES, SAMPLE_RATE, Segmenter
from core.events import DictationEvent, PartialSpeechEvent, SpeechEvent, StatusEvent

log = logging.getLogger(__name__)
PARTIAL_INTERVAL_S = 0.25


class AudioPipeline:
    """منطق المعالجة دون الميكروفون: يُغذّى بإطارات 30ms (int16 mono 16kHz)."""

    def __init__(self, recognizer, segmenter: Segmenter, is_speech: Callable[[bytes], bool],
                 emit: Callable[[object], None], lang: str):
        self.rec = recognizer
        self.seg = segmenter
        self.is_speech = is_speech
        self.emit = emit
        self.lang = lang
        self._last_partial = ""
        self._last_partial_t = 0.0
        self.seg_id = 0
        # الإملاء: dictation(seg_id, pcm, free_text) يُستدعى بعد SpeechEvent لكل عبارة
        self.dictation: Callable[[int, bytes, str], None] | None = None
        self._audio: list[bytes] = []

    def process(self, frame: bytes) -> None:
        for kind, data in self.seg.push(frame, self.is_speech(frame)):
            if kind == "start":
                self._audio = []
            elif kind == "audio":
                self.rec.accept(data)
                if self.dictation is not None:
                    self._audio.append(data)
                self._maybe_partial()
            elif kind == "end":
                self._finish()

    def flush(self) -> None:
        if self.seg.in_speech:
            self.seg.reset()
            self._finish()

    def _maybe_partial(self) -> None:
        now = time.monotonic()
        if now - self._last_partial_t < PARTIAL_INTERVAL_S:
            return
        self._last_partial_t = now
        p = self.rec.partial()
        if p and p != self._last_partial:
            self._last_partial = p
            self.emit(PartialSpeechEvent(p))

    def _finish(self) -> None:
        text, free = self.rec.finish()
        self._last_partial = ""
        pcm, self._audio = b"".join(self._audio), []
        if not (text or free):
            return
        self.seg_id += 1
        # SpeechEvent أولاً (فوري) ليتمكن الموزّع من اكتشاف أوامر الإملاء قبل وصول النص
        self.emit(SpeechEvent(text=text, free_text=free, lang=self.lang, seg_id=self.seg_id))
        if self.dictation is not None:
            self.dictation(self.seg_id, pcm, free)


class DictationControl:
    """تشغيل/إيقاف الإملاء داخل عملية الصوت. المحرك: whisper (أدق، أبطأ) أو vosk (فوري)."""

    def __init__(self, models_dir: Path, emit: Callable[[object], None]):
        self.models_dir = models_dir
        self.emit = emit
        self.on = False
        self.engine = "whisper"
        self.thread = None
        self.pipeline: AudioPipeline | None = None

    def configure(self, pipeline: AudioPipeline, payload: dict) -> None:
        from audio.dictation import DictationThread
        on = bool(payload.get("on"))
        if on:
            self.engine = payload.get("engine", "whisper")
            if self.engine == "whisper" and self.thread is None:
                model = self.models_dir / "whisper" / payload.get("model", "small")
                self.thread = DictationThread(model, self.emit, int(payload.get("threads", 0)),
                                              int(payload.get("beam_size", 1)))
            elif self.engine != "whisper":
                self._stop_thread()
                self.emit(StatusEvent("dictation", "ready"))
        else:
            self._stop_thread(abort=bool(payload.get("abort")))
            self.emit(StatusEvent("dictation", "off"))
        self.on = on
        self.attach(pipeline)

    def _stop_thread(self, abort: bool = False) -> None:
        if self.thread is not None:
            if abort:
                self.thread.abort()
            else:
                self.thread.stop()
            self.thread = None

    def attach(self, pipeline: AudioPipeline) -> None:
        self.pipeline = pipeline
        pipeline.dictation = self._handle if self.on else None

    def _handle(self, seg_id: int, pcm: bytes, free_text: str) -> None:
        lang = self.pipeline.lang if self.pipeline else "ar"
        if self.engine == "whisper" and self.thread is not None:
            self.thread.submit(seg_id, pcm, lang)
        else:
            self.emit(DictationEvent(free_text, seg_id, lang, "vosk", 0.0))


def _make_pipeline(cfg: dict, emit) -> AudioPipeline:
    import webrtcvad
    from audio.recognizer import VoskRecognizer

    lang = cfg["language"]
    model_dir = Path(cfg["models_dir"]) / "vosk" / lang
    rec = VoskRecognizer(model_dir, SAMPLE_RATE, cfg.get("grammar", {}).get(lang),
                         cfg.get("use_grammar", "auto"))
    vad = webrtcvad.Vad(int(cfg.get("vad_aggressiveness", 2)))
    seg = Segmenter(silence_ms=int(cfg.get("silence_ms", 600)),
                    max_ms=int(float(cfg.get("max_utterance_s", 12)) * 1000))
    log.info("الصوت: لغة=%s قواعد=%s", lang, rec.grammar_enabled)
    return AudioPipeline(rec, seg, lambda f: vad.is_speech(f, SAMPLE_RATE), emit, lang)


def run(cfg: dict, address, authkey: bytes) -> None:
    """نقطة دخول العملية الفرعية: تهيئة النموذج والميكروفون أولاً، ثم الاتصال بالرئيسية
    (انظر core/ipc.py لسبب هذا الترتيب)."""
    from core import offline_guard
    from core.ipc import Link
    offline_guard.install()
    logging.basicConfig(level=cfg.get("log_level", "INFO"),
                        format="%(asctime)s [audio] %(levelname)s %(message)s")
    from audio.capture import open_microphone

    link: Link | None = None

    def emit(ev) -> None:
        if link is not None:
            link.send(ev)

    error = None
    pipeline = mic = None
    try:
        pipeline = _make_pipeline(cfg, emit)
        mic = open_microphone(cfg.get("input_device"))
        mic.start()
    except Exception as e:  # noqa: BLE001
        log.exception("فشل تهيئة الصوت")
        error = str(e) if pipeline is None else f"mic: {e}"

    link = Link(address, authkey, "audio")
    if error:
        emit(StatusEvent("audio", "error", error))
        link.close()
        return
    assert pipeline is not None and mic is not None
    emit(StatusEvent("audio", "ready", pipeline.lang))
    dictation = DictationControl(Path(cfg["models_dir"]), emit)
    muted = False
    try:
        while True:
            for msg in link.poll_control():   # EOFError إذا أُغلقت الرئيسية
                if msg.kind == "shutdown":
                    return
                if msg.kind == "reload":
                    cfg.update(msg.payload)
                    emit(StatusEvent("audio", "starting", cfg["language"]))
                    try:
                        new = _make_pipeline(cfg, emit)
                        new.seg_id = pipeline.seg_id   # أرقام العبارات لا تتكرر
                        pipeline = new
                        dictation.attach(pipeline)
                        emit(StatusEvent("audio", "ready", pipeline.lang))
                    except Exception as e:  # noqa: BLE001
                        log.exception("فشل إعادة تحميل النموذج")
                        emit(StatusEvent("audio", "error", str(e)))
                elif msg.kind == "dictation":
                    dictation.configure(pipeline, msg.payload)
                elif msg.kind == "mute":
                    muted = bool(msg.payload.get("value", True))
                    pipeline.flush()
                    emit(StatusEvent("audio", "muted" if muted else "ready", pipeline.lang))
            frame = mic.read(timeout=0.1)
            if frame is None or muted or len(frame) != FRAME_BYTES:
                continue
            pipeline.process(frame)
    except (EOFError, OSError):
        log.info("انقطع الاتصال بالعملية الرئيسية؛ خروج")
    finally:
        mic.close()
        if dictation.on:
            dictation.configure(pipeline, {"on": False})
        try:
            emit(StatusEvent("audio", "stopped"))
        except (EOFError, OSError):
            pass
        link.close()
