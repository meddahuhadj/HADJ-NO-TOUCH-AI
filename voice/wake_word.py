import re
from typing import List, Tuple
from config.settings_manager import SettingsManager


# Words that may precede the wake word without being part of a sentence, e.g.
# "ok hey hadj open chrome". Anything else means the name appeared inside real
# speech and must not open the gate.
LEADING_FILLERS: List[str] = [
    "ok", "okay", "hey", "hi", "hello", "yo", "bonjour", "salut", "coucou",
    "allo", "هلا", "ايوه", "طيب",
]

# Emergency phrases that are specific enough to be recognised anywhere in an
# utterance. Single generic verbs are deliberately NOT here: "stop" inside
# "non-stop running" is not an emergency.
EXPLICIT_EMERGENCY_PHRASES: List[str] = [
    "stop hadj",
    "hadj stop",
    "emergency stop",
    "urgence stop",
    "arrête hadj",
    "arret hadj",
    "توقف يا حاج",
    "يا حاج توقف",
]

# Bare verbs that only count as an emergency when they are the whole utterance,
# because they occur constantly inside ordinary sentences.
SOLE_EMERGENCY_PHRASES: List[str] = [
    "stop", "arrête", "arrete", "halt", "توقف", "قف", "اوقف", "توقفي",
]


class WakeWordDetector:
    """Local, offline wake word and emergency stop phrase detector."""

    def __init__(self):
        self.settings = SettingsManager()
        # Ordered longest first so "hey hadj" wins over the bare "hadj".
        self.wake_words: List[str] = sorted([
            "hey hadj",
            "bonjour hadj",
            "salut hadj",
            "يا حاج",
            "ياحاج",
            "حاج",
            "hadj",
            "haj",
            "alhadj",
        ], key=len, reverse=True)
        self.emergency_phrases: List[str] = self._all_emergency_phrases()

    @staticmethod
    def _all_emergency_phrases() -> List[str]:
        # Kept as a single attribute so settings and callers see one list.
        return list(EXPLICIT_EMERGENCY_PHRASES) + list(SOLE_EMERGENCY_PHRASES)

    def check_wake_word(self, text: str) -> Tuple[bool, str]:
        """
        Checks whether the phrase opens with a wake word.

        Returns (is_wake_word, remainder_command).

        The wake word has to appear at the start of the utterance, optionally
        behind a greeting, and on word boundaries. Matching anywhere in the
        string meant "the hadj committee meets tomorrow" armed the engine and
        the next unrelated sentence was treated as a command.
        """
        clean_text = text.strip().lower()
        if not clean_text:
            return False, clean_text

        stripped = clean_text
        # Peel leading greetings so "ok hey hadj open chrome" still works.
        changed = True
        while changed:
            changed = False
            for filler in LEADING_FILLERS:
                pattern = r'^' + re.escape(filler) + r'(?!\w)\s*'
                new = re.sub(pattern, '', stripped, count=1, flags=re.UNICODE)
                if new != stripped:
                    stripped = new
                    changed = True

        for ww in self.wake_words:
            pattern = r'^' + re.escape(ww) + r'(?!\w)'
            match = re.match(pattern, stripped, flags=re.UNICODE)
            if match is None:
                continue
            remainder = stripped[match.end():].strip()
            # Drop punctuation and conjunctions left at the front.
            remainder = re.sub(r'^[\s,\.\-،؛:]+', '', remainder)
            remainder = re.sub(r'^ثم\s*', '', remainder)
            return True, remainder.strip()

        return False, clean_text

    def check_emergency_stop(self, text: str) -> bool:
        """
        Detects an emergency stop request.

        Explicit multi-word phrases ("emergency stop") match anywhere. Bare
        verbs like "stop" only count when they are the entire utterance, so
        "do not stop" and "non-stop running" cannot halt the machine by
        accident — an emergency that fires on ordinary speech makes the real
        one easy to miss.
        """
        clean_text = text.strip().lower()
        if not clean_text:
            return False

        for phrase in EXPLICIT_EMERGENCY_PHRASES:
            pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
            if re.search(pattern, clean_text, flags=re.UNICODE):
                return True

        # A bare verb counts only if nothing else was said, allowing for a
        # trailing filler such as "stop please".
        for phrase in SOLE_EMERGENCY_PHRASES:
            pattern = (
                r'^' + re.escape(phrase) + r'(?!\w)'
                r'(?:\s+(?:' + '|'.join(re.escape(f) for f in LEADING_FILLERS)
                + r')(?!\w))*\s*[.!\?]*$'
            )
            if re.search(pattern, clean_text, flags=re.UNICODE):
                return True

        return False
