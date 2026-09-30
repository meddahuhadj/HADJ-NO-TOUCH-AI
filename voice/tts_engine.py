import time
import queue
import threading
from typing import Optional
import pyttsx3

from config.settings_manager import SettingsManager


class TTSEngine:
    """Offline Windows Text-to-Speech audio feedback engine running on an asynchronous queue."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSEngine, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.settings = SettingsManager()
        self.speech_queue = queue.Queue()
        self.running = True
        self.engine = None
        self.muted = not self.settings.get("voice.tts_feedback_enabled", True)

        # Worker thread for pyttsx3
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _init_engine(self):
        try:
            self.engine = pyttsx3.init()
            rate = self.settings.get("voice.tts_rate", 160)
            vol = self.settings.get("voice.tts_volume", 0.9)
            self.engine.setProperty("rate", rate)
            self.engine.setProperty("volume", vol)
        except Exception as e:
            print(f"[TTSEngine] pyttsx3 init error: {e}")
            self.engine = None

    def _worker_loop(self):
        # Windows COM apartment initialization is mandatory for pyttsx3/SAPI5 in background threads
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_initialized = True
        except Exception:
            com_initialized = False

        try:
            self._init_engine()

            while self.running:
                try:
                    text, lang = self.speech_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if not text or self.muted:
                    self.speech_queue.task_done()
                    continue

                if self.engine is None:
                    self._init_engine()

                if self.engine:
                    try:
                        # Select voice matching language if available
                        voices = self.engine.getProperty("voices")
                        chosen_voice = None
                        lang_lower = (lang or self.settings.get("language", "ar")).lower()

                        for v in voices:
                            v_name = v.name.lower()
                            if lang_lower == "fr" and ("french" in v_name or "hortense" in v_name):
                                chosen_voice = v.id
                                break
                            elif lang_lower == "en" and ("english" in v_name or "david" in v_name or "zira" in v_name):
                                chosen_voice = v.id
                                break
                            elif lang_lower == "ar" and "arabic" in v_name:
                                chosen_voice = v.id
                                break

                        if chosen_voice:
                            self.engine.setProperty("voice", chosen_voice)

                        self.engine.say(text)
                        self.engine.runAndWait()
                    except Exception as e:
                        print(f"[TTSEngine] TTS speech notice: {e}")
                        # Reinit engine if it crashes
                        self._init_engine()

                self.speech_queue.task_done()
        finally:
            if com_initialized:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def speak(self, text: str, lang: Optional[str] = None):
        """Queues spoken response without blocking main execution."""
        if not self.muted and text:
            self.speech_queue.put((text, lang))

    def set_muted(self, muted: bool):
        self.muted = muted

    def stop(self):
        self.running = False
