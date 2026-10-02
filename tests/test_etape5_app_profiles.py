import unittest
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from core.app_profile_manager import AppProfileManager, AppProfile
from core.macro_engine import MacroEngine
from core.command_orchestrator import CommandOrchestrator
import config.i18n as i18n
from ui.macro_dialog import MacroEditorDialog, MacroManagerDialog


class TestAppProfileManager(unittest.TestCase):
    """Test contextual application profile detection and gesture action mapping."""

    def setUp(self):
        self.mgr = AppProfileManager()
        self.mgr.lock_profile(None)

    def test_classify_browser(self):
        prof = self.mgr._classify_profile("chrome.exe", "Google Search - Personal")
        self.assertEqual(prof, AppProfile.BROWSER)

        prof = self.mgr._classify_profile("firefox.exe", "GitHub - Dashboard")
        self.assertEqual(prof, AppProfile.BROWSER)

        prof = self.mgr._classify_profile("msedge.exe", "Bing Homepage")
        self.assertEqual(prof, AppProfile.BROWSER)

    def test_classify_media(self):
        # Dedicated media apps
        prof = self.mgr._classify_profile("vlc.exe", "BigBuckBunny.mp4")
        self.assertEqual(prof, AppProfile.MEDIA)

        prof = self.mgr._classify_profile("spotify.exe", "Spotify Free")
        self.assertEqual(prof, AppProfile.MEDIA)

        # Media in browser tab takes precedence
        prof = self.mgr._classify_profile("chrome.exe", "Lo-fi Hip Hop Live - YouTube")
        self.assertEqual(prof, AppProfile.MEDIA)

        prof = self.mgr._classify_profile("firefox.exe", "Stranger Things - Netflix")
        self.assertEqual(prof, AppProfile.MEDIA)

    def test_classify_document(self):
        prof = self.mgr._classify_profile("winword.exe", "Quarterly_Report.docx")
        self.assertEqual(prof, AppProfile.DOCUMENT)

        prof = self.mgr._classify_profile("powerpnt.exe", "Project_Pitch.pptx")
        self.assertEqual(prof, AppProfile.DOCUMENT)

        prof = self.mgr._classify_profile("acrord32.exe", "Anatomy_Atlas.pdf")
        self.assertEqual(prof, AppProfile.DOCUMENT)

        prof = self.mgr._classify_profile("notepad.exe", "notes.txt")
        self.assertEqual(prof, AppProfile.DOCUMENT)

    def test_classify_desktop_default(self):
        prof = self.mgr._classify_profile("explorer.exe", "")
        self.assertEqual(prof, AppProfile.DESKTOP)

    def test_locked_profile_override(self):
        self.mgr.lock_profile(AppProfile.MEDIA)
        self.assertEqual(self.mgr.get_active_profile(), AppProfile.MEDIA)
        self.mgr.lock_profile(None)

    def test_contextual_gestures_browser(self):
        self.mgr.lock_profile(AppProfile.BROWSER)
        act_left = self.mgr.get_contextual_action("SWIPE_LEFT")
        self.assertEqual(act_left["action"], "NAV_BACK")
        self.assertEqual(act_left["key"], "alt+left")

        act_right = self.mgr.get_contextual_action("SWIPE_RIGHT")
        self.assertEqual(act_right["action"], "NAV_FORWARD")
        self.assertEqual(act_right["key"], "alt+right")

        act_pinch = self.mgr.get_contextual_action("PINCH")
        self.assertEqual(act_pinch["action"], "CLICK")

    def test_contextual_gestures_media(self):
        self.mgr.lock_profile(AppProfile.MEDIA)
        act_left = self.mgr.get_contextual_action("SWIPE_LEFT")
        self.assertEqual(act_left["action"], "SEEK_BACK")
        self.assertEqual(act_left["key"], "left")

        act_right = self.mgr.get_contextual_action("SWIPE_RIGHT")
        self.assertEqual(act_right["action"], "SEEK_FORWARD")
        self.assertEqual(act_right["key"], "right")

        act_pinch = self.mgr.get_contextual_action("PINCH")
        self.assertEqual(act_pinch["action"], "PLAY_PAUSE")
        self.assertEqual(act_pinch["key"], "space")

    def test_contextual_gestures_document(self):
        self.mgr.lock_profile(AppProfile.DOCUMENT)
        act_left = self.mgr.get_contextual_action("SWIPE_LEFT")
        self.assertEqual(act_left["action"], "PAGE_PREV")
        self.assertEqual(act_left["key"], "pageup")

        act_right = self.mgr.get_contextual_action("SWIPE_RIGHT")
        self.assertEqual(act_right["action"], "PAGE_NEXT")
        self.assertEqual(act_right["key"], "pagedown")

        act_pinch = self.mgr.get_contextual_action("PINCH")
        self.assertEqual(act_pinch["action"], "CLICK")


class TestMacroEngineAndTriggers(unittest.TestCase):
    """Test custom automation macros with voice/gesture triggers and new action step types."""

    def setUp(self):
        self.engine = MacroEngine()

    def test_add_and_get_macro(self):
        test_name = "Test Workflow 1"
        steps = [
            {"action": "LAUNCH_APP", "target": "notepad", "delay": 0.5},
            {"action": "TYPE_TEXT", "target": "Hello Hadj No-Touch!", "delay": 0.2},
            {"action": "KEY_PRESS", "target": "enter", "delay": 0.1},
            {"action": "HOTKEY", "target": "ctrl+s", "delay": 0.1},
        ]
        ok = self.engine.add_or_update_macro(
            test_name, steps, voice_trigger="start test", gesture_trigger="DOUBLE_PINCH"
        )
        self.assertTrue(ok)

        # Retrieve steps
        retrieved_steps = self.engine.get_macro_steps(test_name)
        self.assertEqual(len(retrieved_steps), 4)
        self.assertEqual(retrieved_steps[1]["action"], "TYPE_TEXT")

        # Triggers
        v_trig, g_trig = self.engine.get_macro_triggers(test_name)
        self.assertEqual(v_trig, "start test")
        self.assertEqual(g_trig, "DOUBLE_PINCH")

        # Lookup by triggers
        matched_voice = self.engine.find_macro_by_voice("please start test now")
        self.assertEqual(matched_voice, test_name)

        matched_gesture = self.engine.find_macro_by_gesture("DOUBLE_PINCH")
        self.assertEqual(matched_gesture, test_name)

        # Clean up
        self.engine.delete_macro(test_name)
        self.assertNotIn(test_name, self.engine.get_all_macros())

    def test_macro_step_executor_dispatch(self):
        orchestrator = CommandOrchestrator()
        executed_calls = []

        # Mock win_control methods
        orig_type = orchestrator.win_control.type_text
        orig_press = orchestrator.win_control.press_key
        try:
            orchestrator.win_control.type_text = lambda text: executed_calls.append(("TYPE", text))
            orchestrator.win_control.press_key = lambda key: executed_calls.append(("PRESS", key))

            orchestrator._execute_macro_step("TYPE_TEXT", "Bonjour")
            orchestrator._execute_macro_step("KEY_PRESS", "enter")

            self.assertEqual(executed_calls, [("TYPE", "Bonjour"), ("PRESS", "enter")])
        finally:
            orchestrator.win_control.type_text = orig_type
            orchestrator.win_control.press_key = orig_press


class TestI18nParityEtape5(unittest.TestCase):
    """Verify that all new app profile and macro keys exist across EN, FR, and AR."""

    def test_translation_keys_exist(self):
        keys = [
            "profile.browser",
            "profile.media",
            "profile.document",
            "profile.desktop",
            "profile.active_label",
            "profile.action.browser_back",
            "profile.action.browser_forward",
            "profile.action.media_seek_back",
            "profile.action.media_seek_forward",
            "profile.action.media_play_pause",
            "profile.action.doc_page_prev",
            "profile.action.doc_page_next",
            "macro.title",
            "macro.heading",
            "macro.saved",
            "macro.preview",
            "macro.run",
            "macro.new",
            "macro.empty",
            "macro.create_title",
            "macro.name",
            "macro.voice_trigger",
            "macro.gesture_trigger",
            "macro.steps",
            "macro.add_step",
            "macro.remove_step",
            "macro.save",
            "macro.step_launch_app",
            "macro.step_type_text",
            "macro.step_key_press",
            "macro.step_hotkey",
        ]
        for lang in ("en", "fr", "ar"):
            catalogue = i18n.STRINGS.get(lang, {})
            for k in keys:
                self.assertIn(k, catalogue, f"Missing key '{k}' in language '{lang}'")


class TestMacroDialogsInstantiation(unittest.TestCase):
    """Verify that MacroEditorDialog and MacroManagerDialog initialize and render without errors."""

    def test_macro_editor_dialog(self):
        dlg = MacroEditorDialog(None)
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.table.columnCount(), 3)
        dlg.close()

    def test_macro_manager_dialog(self):
        dlg = MacroManagerDialog(None)
        self.assertIsNotNone(dlg)
        self.assertGreater(dlg.macro_list.count(), 0)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
