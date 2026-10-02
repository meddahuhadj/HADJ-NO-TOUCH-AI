"""
Unit and integration tests for Étape 4: Voice Commands & Arabic Dialects.
Validates Arabic normalization, phonetic tolerance, Levenshtein fuzzy distance,
and dialect recognition (Maghrebi/Darija, Egyptian, Gulf/Levantine, and Standard Fusha)
with zero regressions on French and English.
"""

import unittest

from intents.intent_definitions import IntentType
from intents.intent_recognizer import IntentRecognizer, normalize_arabic, levenshtein_distance
from voice.speech_engine import is_confirmation_reply, AFFIRMATIVE_REPLIES, NEGATIVE_REPLIES


class TestArabicNormalization(unittest.TestCase):
    def test_tashkeel_and_tatweel_removal(self):
        text = "أَغْلِقِ النَّافِـذَةَ"
        norm = normalize_arabic(text)
        self.assertEqual(norm, "اغلق النافذه")

    def test_alif_and_ta_marbuta_normalization(self):
        text = "إلغاء لقطة شاشة"
        norm = normalize_arabic(text)
        self.assertEqual(norm, "الغاء لقطه شاشه")

    def test_levenshtein_distance(self):
        self.assertEqual(levenshtein_distance("افتح", "افتح"), 0)
        self.assertEqual(levenshtein_distance("افتح", "افتحه"), 1)
        self.assertEqual(levenshtein_distance("كابتير", "كابتيري"), 1)


class TestArabicDialectsRecognition(unittest.TestCase):
    def setUp(self):
        self.recognizer = IntentRecognizer()

    def _intent(self, text: str) -> IntentType:
        return self.recognizer.parse(text).intent_type

    def test_standard_fusha(self):
        self.assertEqual(self._intent("التقط صورة للشاشة"), IntentType.SCREENSHOT)
        self.assertEqual(self._intent("ارفع الصوت"), IntentType.VOLUME_UP)
        self.assertEqual(self._intent("اخفض الصوت"), IntentType.VOLUME_DOWN)
        self.assertEqual(self._intent("اغلق النافذة"), IntentType.CLOSE_WINDOW)
        self.assertEqual(self._intent("مرر للأعلى"), IntentType.SCROLL_UP)

    def test_maghrebi_darija(self):
        # Open app: "حل"
        res = self.recognizer.parse("حل كروم")
        self.assertEqual(res.intent_type, IntentType.LAUNCH_APP)
        self.assertEqual(res.target, "كروم")

        # Close: "بلع" / "سد"
        self.assertEqual(self._intent("بلع النافذة"), IntentType.CLOSE_WINDOW)
        self.assertEqual(self._intent("سد النافذة"), IntentType.CLOSE_WINDOW)

        # Volume: "زيد الصوت" / "نقص الصوت"
        self.assertEqual(self._intent("زيد الصوت"), IntentType.VOLUME_UP)
        self.assertEqual(self._intent("نقص الصوت"), IntentType.VOLUME_DOWN)

        # Screenshot: "دير كابتير" / "صور ليكرون"
        self.assertEqual(self._intent("دير كابتير"), IntentType.SCREENSHOT)
        self.assertEqual(self._intent("صور ليكرون"), IntentType.SCREENSHOT)

        # Scroll: "طلع" / "هبط"
        self.assertEqual(self._intent("طلع للفوق"), IntentType.SCROLL_UP)
        self.assertEqual(self._intent("هبط لتحت"), IntentType.SCROLL_DOWN)

    def test_egyptian_dialect(self):
        self.assertEqual(self._intent("علي الصوت"), IntentType.VOLUME_UP)
        self.assertEqual(self._intent("وطي الصوت"), IntentType.VOLUME_DOWN)
        self.assertEqual(self._intent("اقفل النافذة"), IntentType.CLOSE_WINDOW)
        self.assertEqual(self._intent("صور الشاشة"), IntentType.SCREENSHOT)

    def test_gulf_levantine_dialect(self):
        self.assertEqual(self._intent("صك النافذة"), IntentType.CLOSE_WINDOW)
        self.assertEqual(self._intent("طول على الصوت"), IntentType.VOLUME_UP)
        self.assertEqual(self._intent("قصر على الصوت"), IntentType.VOLUME_DOWN)

    def test_fuzzy_fallback(self):
        # 1 letter missing due to noise: "التقط صوره للشاش" -> still resolves to SCREENSHOT
        res = self.recognizer.parse("التقط صوره للشاش")
        self.assertEqual(res.intent_type, IntentType.SCREENSHOT)


class TestDialectConfirmationReplies(unittest.TestCase):
    def test_affirmative_replies_across_dialects(self):
        affirmative_samples = [
            "نعم", "أجل", "ايوه", "تمام", "ماشي",   # Fusha / Egyptian
            "ايه", "واه", "ديرها", "صافي", "صحا",   # Darija / Maghrebi
            "ابشر", "تم", "صار", "حاضر",            # Gulf / Levantine
            "yes", "oui", "d'accord"                # EN / FR
        ]
        for phrase in affirmative_samples:
            self.assertTrue(
                is_confirmation_reply(phrase, AFFIRMATIVE_REPLIES),
                f"Failed to recognize affirmative reply: '{phrase}'"
            )

    def test_negative_replies_across_dialects(self):
        negative_samples = [
            "لا", "إلغاء", "تراجع",                 # Fusha
            "لا لا", "حبس", "ماديرش", "بلاش",       # Darija / Egyptian
            "ما بدي", "ما ابغى", "لا تسوي", "وقف",  # Gulf / Levantine
            "no", "cancel", "non", "annuler"        # EN / FR
        ]
        for phrase in negative_samples:
            self.assertTrue(
                is_confirmation_reply(phrase, NEGATIVE_REPLIES),
                f"Failed to recognize negative reply: '{phrase}'"
            )


class TestEnglishAndFrenchNonRegression(unittest.TestCase):
    def setUp(self):
        self.recognizer = IntentRecognizer()

    def test_english_commands(self):
        self.assertEqual(self.recognizer.parse("screenshot").intent_type, IntentType.SCREENSHOT)
        self.assertEqual(self.recognizer.parse("volume up").intent_type, IntentType.VOLUME_UP)
        self.assertEqual(self.recognizer.parse("close window").intent_type, IntentType.CLOSE_WINDOW)
        self.assertEqual(self.recognizer.parse("open notepad").intent_type, IntentType.LAUNCH_APP)

    def test_french_commands(self):
        self.assertEqual(self.recognizer.parse("capture d'écran").intent_type, IntentType.SCREENSHOT)
        self.assertEqual(self.recognizer.parse("monte le son").intent_type, IntentType.VOLUME_UP)
        self.assertEqual(self.recognizer.parse("ferme la fenêtre").intent_type, IntentType.CLOSE_WINDOW)
        self.assertEqual(self.recognizer.parse("ouvre calculatrice").intent_type, IntentType.LAUNCH_APP)
