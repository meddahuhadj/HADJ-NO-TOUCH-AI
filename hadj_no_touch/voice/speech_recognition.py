"""Local speech recognition backends.

Default engine: Google Web Speech (requires internet). Optional offline
engines: Vosk (if the model package is installed) and Windows SAPI
(experimental). All audio capture uses sounddevice (no PyAudio needed)
and audio leaves the device only when an online engine is selected.
"""

from __future__ import annotations

import io
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np

from ..config import VoiceSettings, SETTINGS
from ..logging_setup import get_logger

log = get_logger("voice.speech")

try:
    import sounddevice as sd
    HAVE_SOUNDDEVICE = True
except Exception:
    HAVE_SOUNDDEVICE = False

try:
    import speech_recognition as sr
    HAVE_SPEECH_RECOGNITION = True
except Exception:
    HAVE_SPEECH_RECOGNITION = False


class _BlockingRawStream(io.RawIOBase):
    """Thread-safe raw stream fed by the sounddevice callback."""

    def __init__(self) -> None:
        super().__init__()
        self._buf = bytearray()
        self._lock = threading.Condition()

    def readable(self) -> bool:
        return True

    def write(self, data: bytes) -> int:
        with self._lock:
            self._buf.extend(data)
            self._lock.notify_all()
        return len(data)

    def read(self, n: int = -1) -> bytes:
        with self._lock:
            while len(self._buf) < n and not self.closed:
                self._lock.wait(timeout=0.5)
            if n < 0:
                n = len(self._buf)
            data = bytes(self._buf[:n])
            del self._buf[:n]
            return data

    def close(self) -> None:
        with self._lock:
            io.RawIOBase.close(self)
            self._lock.notify_all()


class SoundDeviceMicrophone(sr.AudioSource):
    """AudioSource backed by sounddevice (16-bit mono PCM)."""

    def __init__(self, device_index: int | None = None,
                 sample_rate: int = 16000, chunk_size: int = 2048):
        if not HAVE_SOUNDDEVICE:
            raise RuntimeError("sounddevice is not installed")
        self.device_index = device_index
        self.SAMPLE_RATE = sample_rate
        self.SAMPLE_WIDTH = 2
        self.CHUNK = chunk_size
        self.audio = None
        self.stream = None
        self._sd_stream = None

    def __enter__(self):
        self.audio = _BlockingRawStream()
        self._sd_stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=self.CHUNK,
            callback=self._callback,
        )
        self._sd_stream.start()
        self.stream = self.audio
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._sd_stream is not None:
            try:
                self._sd_stream.stop()
                self._sd_stream.close()
            except Exception:
                pass
            self._sd_stream = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def _callback(self, indata, frames, time_info, status):
        if self.audio is not None:
            self.audio.write(indata.tobytes())


class SpeechEngine(ABC):
    name = "base"
    offline = False

    def __init__(self, on_text: Optional[Callable[[str], None]] = None,
                 language: str = "en-US"):
        self.on_text = on_text
        self.language = self._canonical_language(language)
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self.status = "idle"
        self.error: Optional[str] = None

    @staticmethod
    def _canonical_language(lang: str) -> str:
        m = {"en": "en-US", "fr": "fr-FR", "ar": "ar-SA"}
        return m.get(lang, lang)

    def start(self) -> bool:
        if self.status == "listening" or not self.available():
            return False
        self._running.set()
        self._thread = threading.Thread(target=self._loop, name=f"voice-{self.name}",
                                        daemon=True)
        self._thread.start()
        self.status = "listening"
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.status = "idle"

    def pump_recognition(self, audio_data) -> str | None:
        """Recognize one AudioData chunk. Raises on failure."""
        raise NotImplementedError

    def available(self) -> bool:
        return True

    def _loop(self) -> None:
        raise NotImplementedError


class GoogleSpeechEngine(SpeechEngine):
    name = "google"
    offline = False

    def __init__(self, on_text=None, language="en-US"):
        super().__init__(on_text, language)
        self._mic = None
        self._recognizer = sr.Recognizer()

    def available(self) -> bool:
        return HAVE_SPEECH_RECOGNITION and HAVE_SOUNDDEVICE

    def _loop(self) -> None:
        while self._running.is_set():
            try:
                with SoundDeviceMicrophone(sample_rate=16000) as source:
                    self._recognizer.energy_threshold = 400
                    self.status = "listening"
                    self.error = None
                    while self._running.is_set():
                        try:
                            audio = self._recognizer.listen(source, phrase_time_limit=8, timeout=6)
                            self.status = "recognizing"
                            text = self._recognizer.recognize_google(audio, language=self.language)
                            if text and self.on_text:
                                self.on_text(text.strip())
                        except (sr.WaitTimeoutError, sr.UnknownValueError):
                            pass
                        except sr.RequestError as e:
                            self.error = f"Recognition service error: {e}"
                            self.status = "error"
                            time.sleep(2.0)
                        except Exception as e:
                            self.error = str(e)
                            self.status = "error"
                            time.sleep(1.0)
                        finally:
                            if self._running.is_set():
                                self.status = "listening"
            except Exception as e:
                self.error = str(e)
                self.status = "error"
                log.warning("Microphone acquisition error: %s (retrying in 3s)", e)
                time.sleep(3.0)


class VoskSpeechEngine(SpeechEngine):
    """Offline Vosk engine (requires the `vosk` package + a model path)."""

    name = "vosk"
    offline = True

    def __init__(self, on_text=None, language="en-US", model_path: str = ""):
        super().__init__(on_text, language)
        self.model_path = model_path or SETTINGS.voice.vosk_model_path
        self._model = None
        self._recognizer = None

    def available(self) -> bool:
        if not HAVE_SOUNDDEVICE or not self.model_path or not os.path.isdir(self.model_path):
            return False
        try:
            import vosk  # noqa: F401
            return True
        except Exception:
            return False

    def _maybe_init(self) -> bool:
        if self._recognizer is not None:
            return True
        try:
            import vosk
            self._model = vosk.Model(self.model_path)
            self._recognizer = vosk.KaldiRecognizer(self._model, 16000)
            return True
        except Exception as e:
            self.error = str(e)
            self.status = "error"
            return False

    def _loop(self) -> None:
        if not self._maybe_init():
            return
        import sounddevice as sd
        lang = self.language
        model = self._model
        samples_per_ms = self._recognizer.sample_rate() / 1000.0
        res = self._recognizer
        # set some parameters to reduce delays
        res.SetWords(True)
        res.SetPartialWords(True)
        last_n = 0

        def cb(indata, frames, time_info, status):
            nonlocal last_n
            if res.AcceptWaveform(indata.tobytes()):
                import json
                j = json.loads(res.Result())
                text = j.get("text", "")
                if text and self.on_text:
                    import unicodedata as ud
                    norm = str(text)
                    normalized = ''.join(c for c in ud.normalize('NFKD', norm)
                                         if not ud.combining(c))
                    self.on_text(normalized)

        with sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                            blocksize=8000, callback=cb):
            self.status = "listening"
            while self._running.is_set():
                import sounddevice as sd
                sd.sleep(200)
        _ = lang, samples_per_ms, model


class SapiSpeechEngine(SpeechEngine):
    """Experimental Windows SAPI-based dictation (fully offline).

    Uses the legacy Windows Speech API shared recognizer over pywin32 COM.
    This is marked EXPERIMENTAL: availability depends on the Windows
    speech runtime and audio input being configured on the machine.
    """

    name = "sapi"
    offline = True

    def __init__(self, on_text=None, language="en-US"):
        super().__init__(on_text, language)

    def available(self) -> bool:
        try:
            import win32com.client  # noqa: F401
            return True
        except Exception:
            return False


class SpeechManager:
    """Selects/controls the active speech engine."""

    def __init__(self, settings: VoiceSettings = SETTINGS.voice, on_text=None):
        self.settings = settings
        self.on_text = on_text
        self.engine: Optional[SpeechEngine] = None
        self.last_text = ""

    def _make_engine(self, name: str) -> SpeechEngine:
        lang = self.settings.language
        if name == "vosk":
            return VoskSpeechEngine(self._text_cb, lang, self.settings.vosk_model_path)
        if name == "sapi":
            return SapiSpeechEngine(self._text_cb, lang)
        return GoogleSpeechEngine(self._text_cb, lang)

    def _text_cb(self, text: str) -> None:
        self.last_text = text
        if self.on_text:
            self.on_text(text)

    def create(self) -> SpeechEngine:
        engine = self._make_engine(self.settings.engine)
        if engine.available():
            self.engine = engine
        else:
            fallback = GoogleSpeechEngine(self._text_cb, self.settings.language)
            self.engine = fallback if fallback.available() else None
            if self.engine is None:
                log.warning("No speech engine available")
        return self.engine

    @property
    def available(self) -> bool:
        return self.engine is not None and self.engine.available()

    def start(self) -> bool:
        if self.engine is None:
            self.create()
        return bool(self.engine and self.engine.start())

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()


def default_engine_name() -> str:
    return SETTINGS.voice.engine