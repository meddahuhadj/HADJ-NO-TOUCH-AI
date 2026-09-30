import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation.windows_control import WindowsControlEngine
from automation.app_launcher import AppLauncher
from automation.file_manager import FileManager
from core.macro_engine import MacroEngine


class TestAutomationModules(unittest.TestCase):

    def setUp(self):
        self.win = WindowsControlEngine()
        self.app_launcher = AppLauncher()
        self.file_mgr = FileManager()
        self.macro_engine = MacroEngine()

    def test_screen_resolution(self):
        w, h = self.win.screen_width, self.win.screen_height
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_app_launcher_aliases(self):
        self.assertIn("chrome", self.app_launcher.known_apps)
        self.assertIn("notepad", self.app_launcher.known_apps)
        self.assertIn("calculator", self.app_launcher.known_apps)
        self.assertIn("المفكرة", self.app_launcher.known_apps)

    def test_file_manager_paths(self):
        self.assertTrue(os.path.exists(self.file_mgr.last_accessed_dir))

    def test_macros(self):
        macros = self.macro_engine.get_all_macros()
        self.assertIn("Morning Setup", macros)
        self.assertIn("Coding Setup", macros)


if __name__ == "__main__":
    unittest.main()
