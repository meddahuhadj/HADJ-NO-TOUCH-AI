import re
import pyautogui
from automation.windows_control import WindowsControlEngine


class DictationEngine:
    """Manages touchless voice typing, dictation mode, and voice text editing commands."""

    def __init__(self):
        self.win = WindowsControlEngine()
        self.is_dictating = False

        # Editing trigger patterns in Arabic, French, and English
        self.edit_commands = {
            # Delete last word
            "احذف اخر كلمة": self._delete_word,
            "احذف آخر كلمة": self._delete_word,
            "delete last word": self._delete_word,
            "supprime le dernier mot": self._delete_word,

            # Delete sentence
            "احذف الجملة": self._delete_sentence,
            "delete sentence": self._delete_sentence,
            "supprime la phrase": self._delete_sentence,

            # Next line / Enter
            "انتقل الى السطر التالي": self._next_line,
            "انتقل إلى السطر التالي": self._next_line,
            "سطر جديد": self._next_line,
            "next line": self._next_line,
            "nouvelle ligne": self._next_line,
            "à la ligne": self._next_line,

            # Comma
            "ضع فاصلة": lambda: self.win.type_text("، "),
            "فاصلة": lambda: self.win.type_text("، "),
            "comma": lambda: self.win.type_text(", "),
            "virgule": lambda: self.win.type_text(", "),

            # Period
            "ضع نقطة": lambda: self.win.type_text(". "),
            "نقطة": lambda: self.win.type_text(". "),
            "period": lambda: self.win.type_text(". "),
            "point": lambda: self.win.type_text(". "),

            # Copy text
            "انسخ النص": self.win.copy,
            "انسخ": self.win.copy,
            "copy text": self.win.copy,
            "copier": self.win.copy,

            # Paste text
            "الصق": self.win.paste,
            "paste": self.win.paste,
            "coller": self.win.paste,

            # Select paragraph
            "حدد الفقرة": self._select_paragraph,
            "select paragraph": self._select_paragraph,
            "sélectionne le paragraphe": self._select_paragraph,

            # Select all
            "حدد الكل": self.win.select_all,
            "select all": self.win.select_all,
            "tout sélectionner": self.win.select_all,

            # Undo
            "تراجع": self.win.undo,
            "undo": self.win.undo,
            "annuler": self.win.undo,
        }

    def _delete_word(self):
        pyautogui.hotkey("ctrl", "backspace")

    def _delete_sentence(self):
        pyautogui.hotkey("shift", "home")
        pyautogui.press("backspace")

    def _next_line(self):
        pyautogui.press("enter")

    def _select_paragraph(self):
        pyautogui.hotkey("ctrl", "shift", "down")

    def handle_voice_edit_or_dictation(self, text: str) -> bool:
        """
        Checks if text matches an editing shortcut.
        If it matches, executes the edit and returns True.
        Otherwise types the dictated text.
        """
        clean_text = text.strip().lower()

        # Check direct match or editing phrase
        for cmd_phrase, action_fn in self.edit_commands.items():
            if clean_text == cmd_phrase or clean_text.endswith(cmd_phrase):
                action_fn()
                return True

        # Check if user said "اكتب ..." / "type ..." / "écris ..."
        dictation_match = re.match(r'^(اكتب|أكتب|اكتبي|type|write|écris|ecris)\s+(.*)', clean_text, re.IGNORECASE)
        if dictation_match:
            content_to_type = dictation_match.group(2)
            self.type_dictated_text(content_to_type)
            return True

        return False

    def type_dictated_text(self, text: str):
        """Injects dictated text directly into currently focused input target."""
        if not text:
            return
        # Use clipboard paste for instant, Unicode-safe typing (supports Arabic characters properly)
        import pyperclip
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass

        try:
            pyperclip.copy(text + " ")
            self.win.paste()
            # slight delay before restoring
            pyautogui.sleep(0.05)
            if old_clip:
                pyperclip.copy(old_clip)
        except Exception:
            self.win.type_text(text + " ")
