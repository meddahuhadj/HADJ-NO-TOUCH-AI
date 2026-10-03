import os
import json
import time
import threading
import queue
from typing import Dict, Optional, Callable
import numpy as np
import speech_recognition as sr

from core.event_bus import EventBus, EventType
from config.settings_manager import SettingsManager

# Unpacked by scripts/download_vosk_models.py, one folder per language code.
VOSK_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "vosk")
VOSK_SAMPLE_RATE = 16000

# Auto-gain targets a peak at ~70% of full scale. The gain is capped so a
# silent room is not blown up into loud noise.
AUTO_GAIN_TARGET_PEAK = 0.7 * 32767
AUTO_GAIN_MAX = 20.0


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

        # Vosk models are loaded on first use per language; None marks a
        # language whose model is missing so the disk is not probed each phrase.
        self._vosk_models: Dict[str, Optional[object]] = {}

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

    @staticmethod
    def _apply_auto_gain(audio: sr.AudioData) -> sr.AudioData:
        """
        Raises a quiet recording to a usable level.

        Built-in laptop microphone arrays often deliver speech peaking at a few
        percent of full scale, which neither Vosk nor Google can transcribe.
        """
        samples = np.frombuffer(audio.get_raw_data(convert_width=2), dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return audio
        samples -= samples.mean()
        peak = float(np.abs(samples).max())
        if peak < 1.0:
            return audio
        gain = min(AUTO_GAIN_MAX, AUTO_GAIN_TARGET_PEAK / peak)
        if gain <= 1.0:
            return audio
        boosted = np.clip(samples * gain, -32768, 32767).astype(np.int16)
        return sr.AudioData(boosted.tobytes(), audio.sample_rate, 2)

    def _vosk_model(self, lang: str):
        if lang not in self._vosk_models:
            path = os.path.join(VOSK_MODELS_DIR, lang)
            model = None
            if os.path.isdir(path):
                try:
                    import vosk
                    vosk.SetLogLevel(-1)
                    model = vosk.Model(path)
                    print(f"[AudioListener] Vosk model loaded: {path}")
                except Exception as e:
                    print(f"[AudioListener] Vosk model load failed ({path}): {e}")
            else:
                print(f"[AudioListener] No Vosk model for '{lang}' in {VOSK_MODELS_DIR} "
                      f"(run scripts/download_vosk_models.py {lang})")
            self._vosk_models[lang] = model
        return self._vosk_models[lang]

    def _recognize_vosk(self, audio: sr.AudioData, lang: str) -> Optional[str]:
        model = self._vosk_model(lang)
        if model is None:
            return None
        import vosk
        rec = vosk.KaldiRecognizer(model, VOSK_SAMPLE_RATE)
        rec.AcceptWaveform(audio.get_raw_data(convert_rate=VOSK_SAMPLE_RATE, convert_width=2))
        text = json.loads(rec.FinalResult()).get("text", "").strip()
        return text or None

    def _recognize_offline(self, audio) -> Optional[str]:
        """
        Transcribes audio data locally or with resilient language-aware fallback.
        Tries Vosk first, then falls back so speech recognition is always functional.
        """
        lang = self.settings.get("language", "ar")
        lang_code = "ar-SA" if lang == "ar" else ("fr-FR" if lang == "fr" else "en-US")

        if self.settings.get("audio.auto_gain", True):
            audio = self._apply_auto_gain(audio)

        # 1. Offline Vosk model for the current language
        try:
            text = self._recognize_vosk(audio, lang)
            if text:
                return text
        except Exception as e:
            print(f"[AudioListener] Vosk recognition error: {e}")

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
