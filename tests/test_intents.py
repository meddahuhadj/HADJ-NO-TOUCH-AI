import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from intents.intent_definitions import IntentType
from intents.intent_recognizer import IntentRecognizer


class TestIntentRecognizer(unittest.TestCase):

    def setUp(self):
        self.recognizer = IntentRecognizer()

    def test_arabic_commands(self):
        res = self.recognizer.parse("افتح Chrome")
        self.assertEqual(res.intent_type, IntentType.LAUNCH_APP)
        self.assertEqual(res.target, "chrome")

        res = self.recognizer.parse("ارفع الصوت")
        self.assertEqual(res.intent_type, IntentType.VOLUME_UP)

        res = self.recognizer.parse("انسخ")
        self.assertEqual(res.intent_type, IntentType.CLIPBOARD_COPY)

        res = self.recognizer.parse("اقفل الكمبيوتر")
        self.assertEqual(res.intent_type, IntentType.SYSTEM_LOCK)

        res = self.recognizer.parse("افتح Downloads")
        self.assertEqual(res.intent_type, IntentType.OPEN_FOLDER)

    def test_french_commands(self):
        res = self.recognizer.parse("ferme la fenêtre")
        self.assertEqual(res.intent_type, IntentType.CLOSE_WINDOW)

        res = self.recognizer.parse("ouvre les téléchargements")
        self.assertEqual(res.intent_type, IntentType.OPEN_FOLDER)

        res = self.recognizer.parse("copier")
        self.assertEqual(res.intent_type, IntentType.CLIPBOARD_COPY)

    def test_english_commands(self):
        res = self.recognizer.parse("open vs code")
        self.assertEqual(res.intent_type, IntentType.LAUNCH_APP)

        res = self.recognizer.parse("volume down")
        self.assertEqual(res.intent_type, IntentType.VOLUME_DOWN)

        res = self.recognizer.parse("screenshot")
        self.assertEqual(res.intent_type, IntentType.SCREENSHOT)

    def test_multimodal_commands(self):
        res = self.recognizer.parse("اضغط هنا")
        self.assertEqual(res.intent_type, IntentType.MULTIMODAL_CLICK_TARGET)

        res = self.recognizer.parse("افتحه")
        self.assertEqual(res.intent_type, IntentType.MULTIMODAL_OPEN_TARGET)

        res = self.recognizer.parse("أين زر الإغلاق؟")
        self.assertEqual(res.intent_type, IntentType.FIND_ELEMENT)

    def test_compound_commands(self):
        res = self.recognizer.parse("افتح Chrome ثم افتح Downloads")
        self.assertEqual(res.intent_type, IntentType.COMPOUND_PLAN)
        self.assertIsNotNone(res.sub_intents)
        self.assertEqual(len(res.sub_intents), 2)
        self.assertEqual(res.sub_intents[0].intent_type, IntentType.LAUNCH_APP)
        self.assertEqual(res.sub_intents[1].intent_type, IntentType.OPEN_FOLDER)


    def test_enriched_commands(self):
        res = self.recognizer.parse("قسم الشاشة لليمين")
        self.assertEqual(res.intent_type, IntentType.SNAP_WINDOW_RIGHT)

        res = self.recognizer.parse("snap left")
        self.assertEqual(res.intent_type, IntentType.SNAP_WINDOW_LEFT)

        res = self.recognizer.parse("سطح مكتب جديد")
        self.assertEqual(res.intent_type, IntentType.NEW_DESKTOP)

        res = self.recognizer.parse("عرض المهام")
        self.assertEqual(res.intent_type, IntentType.TASK_VIEW)

        res = self.recognizer.parse("مدير المهام")
        self.assertEqual(res.intent_type, IntentType.OPEN_TASK_MANAGER)

        res = self.recognizer.parse("أفرغ سلة المحذوفات")
        self.assertEqual(res.intent_type, IntentType.EMPTY_RECYCLE_BIN)

        res = self.recognizer.parse("تكبير الشاشة")
        self.assertEqual(res.intent_type, IntentType.ZOOM_IN)

        res = self.recognizer.parse("لوحة المفاتيح")
        self.assertEqual(res.intent_type, IntentType.TOGGLE_KEYBOARD_HUD)


if __name__ == "__main__":
    unittest.main()
