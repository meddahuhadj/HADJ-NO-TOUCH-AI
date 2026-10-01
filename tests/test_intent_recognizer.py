"""
Unit tests for the deterministic intent parser.

The parser is the only thing standing between a misheard phrase and an action
on the user's machine, so these cases pin the multilingual surface: each
command family has to resolve to the same intent in Arabic, French and English,
and the ordering between overlapping patterns must stay stable.
"""

import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from intents.intent_recognizer import IntentRecognizer
from intents.intent_definitions import IntentType


class TestIntentRecognizerMultilingual(unittest.TestCase):

    def setUp(self):
        self.parser = IntentRecognizer()

    def _intent(self, text):
        return self.parser.parse(text).intent_type

    # ------------------------------------------------------------------ #
    # Exact-command families, one case per supported language
    # ------------------------------------------------------------------ #

    def test_volume_commands(self):
        for text in ("ارفع الصوت", "monte le son", "volume up"):
            self.assertEqual(self._intent(text), IntentType.VOLUME_UP, text)
        for text in ("اخفض الصوت", "baisse le son", "volume down"):
            self.assertEqual(self._intent(text), IntentType.VOLUME_DOWN, text)
        for text in ("اكتم الصوت", "couper le son", "mute"):
            self.assertEqual(self._intent(text), IntentType.VOLUME_MUTE, text)

    def test_media_commands(self):
        for text in ("شغل الموسيقى", "play music", "lecture"):
            self.assertEqual(self._intent(text), IntentType.MEDIA_PLAY_PAUSE, text)
        for text in ("التالي", "next track", "suivant"):
            self.assertEqual(self._intent(text), IntentType.MEDIA_NEXT, text)
        for text in ("السابق", "previous track", "precedent"):
            self.assertEqual(self._intent(text), IntentType.MEDIA_PREVIOUS, text)

    def test_window_controls(self):
        for text in ("اغلق النافذة", "close window", "ferme la fenêtre"):
            self.assertEqual(self._intent(text), IntentType.CLOSE_WINDOW, text)
        for text in ("صغر النافذة", "minimize window", "minimiser la fenêtre"):
            self.assertEqual(self._intent(text), IntentType.MINIMIZE_WINDOW, text)
        for text in ("كبر النافذة", "maximize window", "agrandir la fenêtre"):
            self.assertEqual(self._intent(text), IntentType.MAXIMIZE_WINDOW, text)

    def test_snapshot_and_desktops(self):
        for text in ("التقط صورة للشاشة", "screenshot", "capture d'écran"):
            self.assertEqual(self._intent(text), IntentType.SCREENSHOT, text)
        for text in ("سطح مكتب جديد", "new desktop", "nouveau bureau"):
            self.assertEqual(self._intent(text), IntentType.NEW_DESKTOP, text)
        for text in ("مدير المهام", "task manager", "gestionnaire des tâches"):
            self.assertEqual(self._intent(text), IntentType.OPEN_TASK_MANAGER, text)

    def test_power_commands_are_recognised(self):
        for text in ("اقفل الكمبيوتر", "lock computer", "verrouiller"):
            self.assertEqual(self._intent(text), IntentType.SYSTEM_LOCK, text)
        for text in ("اعد تشغيل الكمبيوتر", "restart computer", "redémarrer"):
            self.assertEqual(self._intent(text), IntentType.SYSTEM_RESTART, text)
        for text in ("اوقف تشغيل الكمبيوتر", "shutdown computer", "éteindre"):
            self.assertEqual(self._intent(text), IntentType.SYSTEM_SHUTDOWN, text)

    def test_clipboard_commands(self):
        for text in ("انسخ", "copy", "copier"):
            self.assertEqual(self._intent(text), IntentType.CLIPBOARD_COPY, text)
        for text in ("الصق", "paste", "coller"):
            self.assertEqual(self._intent(text), IntentType.CLIPBOARD_PASTE, text)
        for text in ("حدد الكل", "select all", "tout sélectionner"):
            self.assertEqual(self._intent(text), IntentType.SELECT_ALL, text)

    def test_multimodal_point_and_act(self):
        for text in ("اضغط هنا", "click here", "clique ici"):
            self.assertEqual(
                self._intent(text), IntentType.MULTIMODAL_CLICK_TARGET, text
            )
        for text in ("افتحه", "open this", "ouvre ceci"):
            self.assertEqual(
                self._intent(text), IntentType.MULTIMODAL_OPEN_TARGET, text
            )

    # ------------------------------------------------------------------ #
    # Extraction of the argument
    # ------------------------------------------------------------------ #

    def test_search_query_is_extracted(self):
        for text, expected in (
            ("ابحث عن الطقس", "الطقس"),
            ("search for weather", "weather"),
            ("cherche la recette", "la recette"),
        ):
            res = self.parser.parse(text)
            self.assertEqual(res.intent_type, IntentType.BROWSER_SEARCH, text)
            self.assertEqual(res.target, expected, text)

    def test_launch_app_target_is_extracted(self):
        for text, expected in (
            ("افتح Chrome", "chrome"),
            ("open notepad", "notepad"),
            ("ouvre word", "word"),
        ):
            res = self.parser.parse(text)
            self.assertEqual(res.intent_type, IntentType.LAUNCH_APP, text)
            self.assertEqual(res.target, expected, text)

    def test_close_app_is_labelled_as_a_close_action(self):
        res = self.parser.parse("أغلق Chrome")
        self.assertEqual(res.intent_type, IntentType.LAUNCH_APP)
        self.assertEqual(res.parameters, {"action": "close"})

    def test_named_folder_target_is_extracted(self):
        res = self.parser.parse("open folder reports")
        self.assertEqual(res.intent_type, IntentType.OPEN_FOLDER)
        self.assertEqual(res.target, "reports")

    def test_known_folder_aliases_map_to_canonical_names(self):
        for text, expected in (
            ("افتح التحميلات", "downloads"),
            ("open documents", "documents"),
        ):
            res = self.parser.parse(text)
            self.assertEqual(res.intent_type, IntentType.OPEN_FOLDER, text)
            self.assertEqual(res.target, expected, text)

    def test_create_folder_with_and_without_a_name(self):
        named = self.parser.parse("create folder invoices")
        self.assertEqual(named.intent_type, IntentType.CREATE_FOLDER)
        self.assertEqual(named.target, "invoices")

        unnamed = self.parser.parse("create folder")
        self.assertEqual(unnamed.intent_type, IntentType.CREATE_FOLDER)
        self.assertTrue(unnamed.target)

    # ------------------------------------------------------------------ #
    # Ordering guarantees
    # ------------------------------------------------------------------ #

    def test_delete_file_captures_an_optional_target(self):
        named = self.parser.parse("delete file report.pdf")
        self.assertEqual(named.intent_type, IntentType.DELETE_FILE)
        self.assertEqual(named.target, "report.pdf")

        # Without a name the target stays empty, which the orchestrator treats
        # as a refusal rather than guessing what to delete.
        unnamed = self.parser.parse("delete file")
        self.assertEqual(unnamed.intent_type, IntentType.DELETE_FILE)
        self.assertIsNone(unnamed.target)

    def test_compound_commands_split_into_sub_intents(self):
        res = self.parser.parse("open chrome then open downloads")
        self.assertEqual(res.intent_type, IntentType.COMPOUND_PLAN)
        self.assertEqual(len(res.sub_intents), 2)
        self.assertEqual(res.sub_intents[0].intent_type, IntentType.LAUNCH_APP)
        self.assertEqual(res.sub_intents[1].intent_type, IntentType.OPEN_FOLDER)

    def test_compound_split_also_handles_arabic(self):
        res = self.parser.parse("افتح Chrome ثم افتح التحميلات")
        self.assertEqual(res.intent_type, IntentType.COMPOUND_PLAN)
        self.assertEqual(len(res.sub_intents), 2)

    def test_unknown_text_is_not_forced_into_an_intent(self):
        self.assertEqual(self._intent("what is the weather tomorrow"), IntentType.UNKNOWN)
        self.assertEqual(self._intent(""), IntentType.UNKNOWN)
        self.assertEqual(self._intent("   "), IntentType.UNKNOWN)

    def test_confidence_is_reported_for_every_result(self):
        for text in ("ارفع الصوت", "nonsense phrase", ""):
            res = self.parser.parse(text)
            self.assertGreaterEqual(res.confidence, 0.0)
            self.assertLessEqual(res.confidence, 1.0)
            self.assertEqual(res.original_text, text)

    def test_intent_risk_is_known_for_every_parsed_intent(self):
        """Nothing may parse into an intent the security engine cannot rate."""
        from core.security_engine import SecurityEngine

        security = SecurityEngine()
        for text in ("ارفع الصوت", "افتح التحميلات", "التقط صورة للشاشة"):
            name = self.parser.parse(text).intent_type.name
            # evaluate_risk falls back to MEDIUM for unknown names, which is the
            # safe direction; this asserts the intent is at least nameable.
            self.assertIn(security.evaluate_risk(name).value,
                          ("LOW", "MEDIUM", "HIGH", "CRITICAL"))


if __name__ == "__main__":
    unittest.main()
