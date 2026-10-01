"""
Unit tests for the dictation / voice-editing dispatcher.

The engine is a plain pattern matcher sitting in front of the keyboard, so the
cases that matter are the ones where it must *not* fire: ordinary dictated
prose that happens to end in a command word.
"""

import os
import sys
import types
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from voice.dictation_engine import DictationEngine


class DictationTestCase(unittest.TestCase):
    """
    Patches the keyboard layer for the whole test, not just at construction.

    The edit helpers resolve ``pyautogui`` from the module globals when they
    are called, so the patch has to still be in place at call time.
    """

    def setUp(self):
        self.calls = []

        def hotkey(*keys):
            self.calls.append(("hotkey",) + keys)

        def press(*keys):
            self.calls.append(("press",) + keys)

        def type_text(text):
            self.calls.append(("type_text", text))

        self.fake_pyautogui = types.SimpleNamespace(
            hotkey=hotkey,
            press=press,
            type_text=type_text,
            sleep=lambda _s: None,
        )
        self.fake_win = mock.MagicMock()
        self.fake_win.type_text = type_text
        self.fake_win.copy = lambda: self.calls.append(("win", "copy"))
        self.fake_win.paste = lambda: self.calls.append(("win", "paste"))
        self.fake_win.select_all = lambda: self.calls.append(("win", "select_all"))
        self.fake_win.undo = lambda: self.calls.append(("win", "undo"))

        p1 = mock.patch("voice.dictation_engine.pyautogui", self.fake_pyautogui)
        p2 = mock.patch("voice.dictation_engine.WindowsControlEngine",
                        return_value=self.fake_win)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

        # type_dictated_text imports pyperclip lazily inside the function, so
        # patching sys.modules is what actually intercepts it.
        self.clipboard = mock.MagicMock()
        self.clipboard.paste.return_value = ""
        p3 = mock.patch.dict(sys.modules, {"pyperclip": self.clipboard})
        p3.start()
        self.addCleanup(p3.stop)

        self.engine = DictationEngine()

    def ran(self, *expected):
        return any(tuple(call) == expected for call in self.calls)

    def clear(self):
        self.calls.clear()


class TestDictationEditing(DictationTestCase):

    # ------------------------------------------------------------------ #
    # Editing commands do fire
    # ------------------------------------------------------------------ #

    def test_delete_last_word(self):
        for text in ("delete last word", "احذف آخر كلمة", "supprime le dernier mot"):
            self.clear()
            self.assertTrue(self.engine.handle_voice_edit_or_dictation(text), text)
            self.assertTrue(self.ran("hotkey", "ctrl", "backspace"), text)

    def test_delete_sentence(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("delete sentence"))
        self.assertTrue(self.ran("hotkey", "shift", "home"))
        self.assertTrue(self.ran("press", "backspace"))

    def test_next_line(self):
        for text in ("next line", "سطر جديد", "nouvelle ligne"):
            self.clear()
            self.assertTrue(self.engine.handle_voice_edit_or_dictation(text), text)
            self.assertTrue(self.ran("press", "enter"), text)

    def test_select_paragraph(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("select paragraph"))
        self.assertTrue(self.ran("hotkey", "ctrl", "shift", "down"))

    def test_select_all_and_undo(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("select all"))
        self.assertTrue(self.ran("win", "select_all"))

        self.clear()
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("undo"))
        self.assertTrue(self.ran("win", "undo"))

    def test_copy_and_paste(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("copy text"))
        self.assertTrue(self.ran("win", "copy"))

        self.clear()
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("paste"))
        self.assertTrue(self.ran("win", "paste"))

    def test_punctuation_commands_insert_the_right_mark(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("comma"))
        self.assertTrue(self.ran("type_text", ", "))

        self.clear()
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("فاصلة"))
        self.assertTrue(self.ran("type_text", "، "))

        self.clear()
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("period"))
        self.assertTrue(self.ran("type_text", ". "))

    def test_command_is_matched_case_insensitively(self):
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("DELETE LAST WORD"))

    def test_multi_word_command_survives_a_wake_prefix(self):
        self.assertTrue(
            self.engine.handle_voice_edit_or_dictation("hey hadj delete last word")
        )
        self.assertTrue(self.ran("hotkey", "ctrl", "backspace"))

    def test_single_word_command_survives_an_instruction_prefix(self):
        for text in ("please undo", "now annuler", "can you coller", "just تراجع"):
            self.clear()
            self.assertTrue(self.engine.handle_voice_edit_or_dictation(text), text)

    # ------------------------------------------------------------------ #
    # Dictation prefix
    # ------------------------------------------------------------------ #

    def test_type_prefix_injects_the_content(self):
        expected = {
            "type hello world": "hello world",
            "write the report": "the report",
            "ecris le rapport": "le rapport",
        }
        for text, _content in expected.items():
            self.clear()
            self.assertTrue(self.engine.handle_voice_edit_or_dictation(text), text)
            self.clipboard.copy.assert_called_with(expected[text] + " ")

    def test_type_prefix_restores_the_previous_clipboard(self):
        self.clipboard.paste.return_value = "previous contents"
        self.engine.handle_voice_edit_or_dictation("type hello")
        self.clipboard.copy.assert_any_call("previous contents")

    def test_type_prefix_recovers_when_the_clipboard_fails(self):
        self.clipboard.copy.side_effect = RuntimeError("clipboard unavailable")
        self.assertTrue(self.engine.handle_voice_edit_or_dictation("type hello"))
        self.assertTrue(self.ran("type_text", "hello "))

    def test_empty_content_is_not_typed(self):
        self.assertIsNone(self.engine.type_dictated_text(""))
        self.assertEqual(self.calls, [])

    # ------------------------------------------------------------------ #
    # Prose must reach the user unchanged
    # ------------------------------------------------------------------ #

    def test_plain_prose_is_not_treated_as_a_command(self):
        for text in ("this is just a sentence", "hello there", "good morning"):
            self.clear()
            self.assertFalse(self.engine.handle_voice_edit_or_dictation(text), text)
            self.assertEqual(self.calls, [], text)

    def test_prose_ending_in_a_single_word_command_is_not_swallowed(self):
        """
        The regression that motivated narrowing the suffix rule.

        Matching on the bare suffix made "i need to undo" destroy the selection
        instead of typing the sentence the user actually said.
        """
        for text in ("send me a copy", "i need to undo", "that will select all"):
            self.clear()
            self.assertFalse(self.engine.handle_voice_edit_or_dictation(text), text)
            self.assertEqual(self.calls, [], text)

    def test_prose_containing_a_command_word_is_not_executed(self):
        for text in ("the copy is ready", "copy that later please",
                     "the undo history is long"):
            self.clear()
            self.assertFalse(self.engine.handle_voice_edit_or_dictation(text), text)
            self.assertEqual(self.calls, [], text)


if __name__ == "__main__":
    unittest.main()