import time
import re
from typing import List, Optional, Tuple
from config.settings_manager import SettingsManager


class WakeWordDetector:
    """Local, offline wake word and emergency stop phrase detector."""

    def __init__(self):
        self.settings = SettingsManager()
        self.wake_words: List[str] = [
            "hey hadj",
            "bonjour hadj",
            "يا حاج",
            "ياحاج",
            "حاج",
            "hadj",
            "haj",
            "alhadj"
        ]
        self.emergency_phrases: List[str] = [
            "stop hadj",
            "توقف يا حاج",
            "توقف",
            "قف",
            "arrête hadj",
            "arrête",
            "urgence stop",
            "emergency stop",
            "stop"
        ]

    def check_wake_word(self, text: str) -> Tuple[bool, str]:
        """
        Checks if the recognized phrase contains a wake word.
        Returns (is_wake_word, remainder_command).
        """
        clean_text = text.strip().lower()

        for ww in self.wake_words:
            # Check prefix match or exact match
            if clean_text.startswith(ww):
                remainder = clean_text[len(ww):].strip()
                # Strip leading punctuation or conjunctions like "ثم"
                remainder = re.sub(r'^[,\.\-\s]+', '', remainder)
                return True, remainder
            elif ww in clean_text:
                parts = clean_text.split(ww, 1)
                remainder = parts[1].strip() if len(parts) > 1 else ""
                remainder = re.sub(r'^[,\.\-\s]+', '', remainder)
                return True, remainder

        return False, clean_text

    def check_emergency_stop(self, text: str) -> bool:
        clean_text = text.strip().lower()
        if not clean_text:
            return False

        for phrase in self.emergency_phrases:
            phrase_clean = phrase.strip().lower()
            # If the phrase is a single word or words, require word boundaries
            # Using unicode word boundary (?<!\w) ... (?!\w)
            pattern = r'(?<!\w)' + re.escape(phrase_clean) + r'(?!\w)'
            if re.search(pattern, clean_text, flags=re.UNICODE):
                return True
        return False
