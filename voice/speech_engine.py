import time
import threading
from typing import Optional, Callable
from voice.wake_word import WakeWordDetector
from voice.audio_listener import AudioListener
from voice.tts_engine import TTSEngine
from voice.dictation_engine import DictationEngine
from core.event_bus import EventBus, EventType
from core.security_engine import SecurityEngine
from core.qt_bridge import QtBridge
from core.audio_effects import AudioEffects
from intents.local_ai_adapter import LocalAIAdapter
from intents.intent_definitions import IntentType
from config.settings_manager import SettingsManager


class SpeechEngine:
    """Orchestrates wake word recognition, listening states, and voice commands."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SpeechEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.settings = SettingsManager()
        self.event_bus = EventBus()
        self.security = SecurityEngine()
        self.qt_bridge = QtBridge()
        self.audio_effects = AudioEffects()
        self.ai_adapter = LocalAIAdapter()

        self.wake_detector = WakeWordDetector()
        self.tts = TTSEngine()
        self.dictation = DictationEngine()
        self.listener = AudioListener()

        # State
        self.is_listening: bool = False
        self.listening_start_time: float = 0.0
        self.listen_timeout: float = self.settings.get("voice.listen_timeout_seconds", 6.0)
        self.current_language: str = self.settings.get("language", "ar")

        # When False, only the wake word (and a pending security prompt) can put
        # the engine into action. Off by design: an always-on recogniser acting
        # on room noise is a safety problem, not a convenience.
        self.hands_free_enabled: bool = bool(
            self.settings.get("voice.hands_free_mode", False)
        )

        # Command consumer callback
        self.command_handler: Optional[Callable[[str, float], None]] = None

        # Wire up listener callback
        self.listener.add_speech_callback(self.on_speech_received)

    def set_command_handler(self, handler: Callable[[str, float], None]):
        self.command_handler = handler

    def start(self):
        self.listener.start()

    def set_language(self, lang_code: str):
        if lang_code in ("ar", "fr", "en"):
            self.current_language = lang_code
            self.settings.set("language", lang_code)
            resp = {
                "ar": "تم التبديل إلى اللغة العربية",
                "fr": "Langue changée en Français",
                "en": "Language switched to English"
            }.get(lang_code, "Language updated")
            self.tts.speak(resp, lang_code)

    def on_speech_received(self, text: str, latency_ms: float = 0.0):
        """Processes transcribed phrase from voice input."""
        clean = text.strip()
        if not clean:
            return

        print(f"[SpeechEngine] Heard: '{clean}'")

        # 1. Check Emergency Stop Phrases first
        if self.wake_detector.check_emergency_stop(clean):
            self.security.trigger_emergency_stop("VOICE_EMERGENCY_STOP")
            self.tts.speak("تم إيقاف النظام فوراً", "ar")
            return

        # 2. Check Security Confirmation responses
        if self.security.is_waiting_confirmation():
            lower = clean.lower()
            if any(w in lower for w in ["نعم", "أكيد", "تأكيد", "yes", "oui", "confirm"]):
                self.security.confirm_pending(source="VOICE")
                self.tts.speak("تم التأكيد", self.current_language)
                return
            elif any(w in lower for w in ["لا", "إلغاء", "تراجع", "no", "non", "cancel"]):
                self.security.cancel_pending(reason="VOICE_REJECT")
                self.tts.speak("تم الإلغاء", self.current_language)
                return

        # 3. Check Wake Word
        is_ww, remainder = self.wake_detector.check_wake_word(clean)
        if is_ww:
            self.audio_effects.play_wake_chime()
            self.is_listening = True
            self.listening_start_time = time.time()
            self.qt_bridge.speech_state.emit(True)
            self.event_bus.publish(EventType.WAKE_WORD_DETECTED, {"text": clean})
            self.event_bus.publish(EventType.SPEECH_LISTENING_START, {})

            if remainder:
                # Direct command followed wake word (e.g. "Hey Hadj open chrome")
                if self._try_language_switch(remainder):
                    pass
                else:
                    self._dispatch_command(remainder, latency_ms)
                self.is_listening = False
                self.qt_bridge.speech_state.emit(False)
                self.event_bus.publish(EventType.SPEECH_LISTENING_END, {})
            else:
                # Only wake word was spoken -> prompt user
                prompt = {
                    "ar": "نعم، أنا أسمعك",
                    "fr": "Oui, je vous écoute",
                    "en": "Yes, I am listening"
                }.get(self.current_language, "Listening")
                self.tts.speak(prompt, self.current_language)
            return

        # 4. If already in Listening Mode
        if self.is_listening:
            if time.time() - self.listening_start_time > self.listen_timeout:
                self.is_listening = False
                self.qt_bridge.speech_state.emit(False)
                self.event_bus.publish(EventType.SPEECH_LISTENING_END, {})
                return

            # A language request inside the listening window switches the
            # interface instead of being parsed as a command.
            if not self._try_language_switch(clean):
                self._dispatch_command(clean, latency_ms)
            self.is_listening = False
            self.qt_bridge.speech_state.emit(False)
            self.event_bus.publish(EventType.SPEECH_LISTENING_END, {})
            return

        # 5. Nothing was spoken while the mic was closed for commands.
        #
        # Dictation and direct commands are deliberately *not* reachable from
        # this branch. An always-on recogniser would otherwise act on whatever
        # the room happens to say — a passing conversation could open apps or
        # type into the focused window. The wake word is the gate; anything
        # outside it is discarded.
        if self.hands_free_enabled:
            # 6. Dictation / Voice Editing
            if self.dictation.handle_voice_edit_or_dictation(clean):
                return

            # 7. Direct Command (e.g. "ouvre chrome", "lance le bloc-notes")
            intent_res = self.ai_adapter.parse_with_fallback(clean)
            if intent_res.intent_type != IntentType.UNKNOWN:
                self._dispatch_command(clean, latency_ms)
                return
        else:
            self.event_bus.publish(EventType.NOTIFICATION, {
                "message": "WAKE_WORD_REQUIRED",
                "heard": clean
            })

    def _try_language_switch(self, text: str) -> bool:
        """
        Switches the interface language when the phrase is a language request.

        Kept out of the idle path: "English" appearing in an ordinary sentence
        used to change the whole UI language without the wake word.
        """
        lower = text.lower()
        if "العربية" in lower or "arabic" in lower or "بالعربية" in lower:
            self.set_language("ar")
            return True
        if "français" in lower or "francais" in lower or "french" in lower:
            self.set_language("fr")
            return True
        if "english" in lower or "الإنجليزية" in lower or "anglais" in lower:
            self.set_language("en")
            return True
        return False

    def _dispatch_command(self, cmd_text: str, latency_ms: float = 0.0):
        self.qt_bridge.speech_command.emit(cmd_text, latency_ms)
        self.event_bus.publish(EventType.SPEECH_RECOGNIZED, {"command": cmd_text, "latency_ms": latency_ms})
        if self.command_handler:
            self.command_handler(cmd_text, latency_ms)

    def inject_text_command(self, text: str):
        """Allows GUI or tests to simulate a voice command directly."""
        self.on_speech_received(text, 0.0)
