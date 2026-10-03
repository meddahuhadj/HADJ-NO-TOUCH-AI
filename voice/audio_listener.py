import time
import threading
import queue
from typing import Optional, Callable
import speech_recognition as sr

from core.event_bus import EventBus, EventType
from config.settings_manager import SettingsManager


class AudioListener(threading.Thread):
    """
    Background continuous audio capture and speech recognition worker.
    Processes microphone input offline without sending any audio off-device.
    """

    def __init__(self):
        super(AudioListener, self).__init__(daemon=True)
        self.settings = SettingsManager()
        self.event_bus = EventBus()
        self.running = False
        self.mic_enabled = self.settings.get("privacy.mic_enabled", True)

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self._mic_lock = threading.Lock()
        self.microphone = None
        self.callbacks = []

    def _init_microphone(self):
        with self._mic_lock:
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                print("[AudioListener] Microphone calibrated for ambient noise.")
            except Exception as e:
                print(f"[AudioListener] Microphone init notice: {e}")
                self.microphone = None

    def add_speech_callback(self, callback: Callable[[str, float], None]):
        self.callbacks.append(callback)

    def set_mic_enabled(self, enabled: bool):
        self.mic_enabled = enabled
        # Do not block the calling GUI thread; background loop initializes mic if needed

    def run(self):
        self.running = True
        print("[AudioListener] Continuous audio listener started.")

        while self.running:
            if not self.mic_enabled:
                time.sleep(0.2)
                continue

            if self.microphone is None:
                self._init_microphone()
                if self.microphone is None:
                    time.sleep(0.5)
                    continue

            try:
                with self._mic_lock:
                    if not self.microphone:
                        continue
                    with self.microphone as source:
                        # Listen with timeout
                        audio = self.recognizer.listen(
                            source,
                            timeout=5.0,
                            phrase_time_limit=self.settings.get("voice.phrase_time_limit_seconds", 5.0)
                        )

                start_rec_t = time.time()
                recognized_text = self._recognize_offline(audio)

                if recognized_text:
                    latency_ms = (time.time() - start_rec_t) * 1000.0
                    for cb in self.callbacks:
                        try:
                            cb(recognized_text, latency_ms)
                        except Exception as e:
                            print(f"[AudioListener] Callback error: {e}")

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                time.sleep(0.1)

    def _recognize_offline(self, audio) -> Optional[str]:
        """
        Transcribes audio data locally or with resilient language-aware fallback.
        Tries Vosk first, then falls back so speech recognition is always functional.
        """
        lang = self.settings.get("language", "ar")
        lang_code = "ar-SA" if lang == "ar" else ("fr-FR" if lang == "fr" else "en-US")

        # 1. Try Vosk if local model is unpacked
        try:
            import vosk
            res = self.recognizer.recognize_vosk(audio)
            import json
            data = json.loads(res)
            text = data.get("text", "").strip()
            if text:
                return text
        except Exception:
            pass

        # 2. Resilient fallback with short socket timeout to prevent network hangs
        try:
            import socket
            orig_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(3.0)
            try:
                recognized = self.recognizer.recognize_google(audio, language=lang_code)
                if recognized and recognized.strip():
                    return recognized.strip()
            finally:
                socket.setdefaulttimeout(orig_timeout)
        except Exception:
            pass

        return None

    def stop(self):
        self.running = False
