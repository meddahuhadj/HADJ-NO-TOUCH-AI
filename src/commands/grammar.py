"""بناء قائمة العبارات للتعرف المقيّد (للنماذج التي تدعمه: Vosk الإنجليزي والفرنسي الصغيران).

العبارات تُرسل بشكلها الأصلي (grammar_form) لا الموحّد: قاموس النموذج الفرنسي يحوي
"dictée" و"l'ordinateur"، والكلمة التي لا تطابق حرفياً تُحذف من القواعد.
"""
from __future__ import annotations

from commands.dictation import COMMANDS as DICTATION_COMMANDS
from commands.grid import GRID_COMMANDS, NUMBER_WORDS
from commands.parser import NO, YES, CommandParser
from commands.text import grammar_form

# كلمات قد تسبق كلمة التنبيه وتُضاف للقواعد ("dis ordinateur", "hey computer")
WAKE_PREFIXES = {"en": ["hey", "ok"], "fr": ["dis"]}


def grid_and_dictation_phrases(lang: str) -> list[str]:
    """أرقام الشبكة وأوامرها وأوامر الإملاء (لكي يتعرف عليها المُعرِّف المقيّد)."""
    out = [w for words in NUMBER_WORDS.get(lang, {}).values() for w in words]
    out += [p for table in GRID_COMMANDS.values() for p in table.get(lang, [])]
    out += [p for table in DICTATION_COMMANDS.values() for p in table.get(lang, [])]
    return out


def build_grammar(parser: CommandParser, lang: str, wake_words: list[str],
                  extra: list[str] | None = None) -> list[str]:
    base = set(parser.phrases(lang))
    # بادئات الأوامر ذات الخانات ("open", "cherche") ليتعرف عليها ثم يُكمل النص الحر
    base |= {t.grammar for t in parser.templates(lang) if t.slot}
    base |= {grammar_form(p) for p in YES.get(lang, []) + NO.get(lang, [])}
    base |= {grammar_form(p) for p in (extra or [])}
    wakes = [grammar_form(w) for w in wake_words if grammar_form(w)]
    wakes += [f"{p} {w}" for w in list(wakes) for p in WAKE_PREFIXES.get(lang, [])]
    phrases = set(base) | set(wakes)
    for w in wakes:
        phrases |= {f"{w} {p}" for p in base}
    return sorted(p for p in phrases if p)
