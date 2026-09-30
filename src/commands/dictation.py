"""منطق الإملاء (بلا صوت ولا نظام): تحويل النص المنطوق إلى نص يُكتب.

- علامات الترقيم المنطوقة: "فاصلة" ← "،"، "نقطة" ← "."، "سطر جديد" ← سطر جديد...
- المسافات بين الدفعات المتتالية، ولا مسافة قبل علامات الترقيم.
- "امسح ذلك" يحذف آخر دفعة مكتوبة.
- تصفية هلوسات Whisper المعروفة على الضوضاء ("شكراً للمشاهدة"، "Thank you.").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from commands.text import normalize

# العبارة المنطوقة (بعد التوحيد) ← الرمز. الأطول أولاً عند المطابقة.
PUNCTUATION = {
    "ar": {
        "فاصله": "،", "فاصله منقوطه": "؛", "نقطه": ".", "نقطتان": ":", "نقطتين": ":",
        "علامه استفهام": "؟", "علامه تعجب": "!", "سطر جديد": "\n", "فقره جديده": "\n\n",
        "افتح قوس": " (", "اغلق قوس": ")", "علامه تنصيص": "\"", "شرطه": "-",
    },
    "en": {
        "comma": ",", "semicolon": ";", "period": ".", "full stop": ".", "colon": ":",
        "question mark": "?", "exclamation mark": "!", "exclamation point": "!",
        "new line": "\n", "newline": "\n", "new paragraph": "\n\n",
        "open parenthesis": " (", "close parenthesis": ")", "quote": "\"", "dash": "-",
    },
    "fr": {
        "virgule": ",", "point virgule": ";", "point": ".", "deux points": ":",
        "point d interrogation": "?", "point d exclamation": "!",
        "a la ligne": "\n", "nouvelle ligne": "\n", "nouveau paragraphe": "\n\n",
        "ouvre la parenthese": " (", "ferme la parenthese": ")", "guillemets": "\"", "tiret": "-",
    },
}
NO_SPACE_BEFORE = set(".,;:!?،؛؟)\n")
SENTENCE_END = set(".!?؟\n")

COMMANDS = {
    "stop": {"ar": ["اوقف الاملاء", "انهاء الاملاء", "انه الاملاء", "توقف عن الاملاء", "اخرج من الاملاء"],
             "en": ["stop dictation", "end dictation", "exit dictation"],
             "fr": ["arrête la dictée", "fin de la dictée", "termine la dictée", "stop dictée"]},
    "undo": {"ar": ["امسح ذلك", "امسح هذا", "احذف ذلك", "امسح اخر جمله"],
             "en": ["scratch that", "delete that", "undo that"],
             "fr": ["efface ça", "efface ca", "annule ça", "efface la dernière phrase"]},
}

HALLUCINATIONS = {
    normalize(p) for p in [
        "شكرا للمشاهدة", "شكرا لكم على المشاهدة", "اشتركوا في القناة", "ترجمة نانسي قنقر",
        "شكرا", "thank you", "thanks for watching", "thank you for watching", "you",
        "subtitles by the amara org community", "please subscribe", "bye",
        "merci", "merci d avoir regarde", "sous titres realises par la communaute d amara org",
        "sous titrage st 501", "abonnez vous",
    ]
}
LATIN = {"en", "fr"}   # لغات تُكبَّر فيها أول كلمة في الجملة


def classify_command(text: str, lang: str) -> str | None:
    """هل العبارة أمر إملاء (stop/undo)؟"""
    n = normalize(text)
    for cmd, table in COMMANDS.items():
        if n in {normalize(p) for p in table.get(lang, [])}:
            return cmd
    return None


def is_hallucination(text: str, no_speech_prob: float = 0.0, avg_logprob: float = 0.0) -> bool:
    n = normalize(text)
    if not n:
        return True
    if n in HALLUCINATIONS:
        return True
    return no_speech_prob > 0.6 and avg_logprob < -1.0


def apply_spoken_punctuation(text: str, lang: str) -> str:
    """يستبدل العبارات المنطوقة بالرموز، مع الحفاظ على باقي النص كما هو."""
    table = PUNCTUATION.get(lang, {})
    raw_words: list[str] = []
    for w in text.split():
        parts = [p for p in re.split(r"(?<=['’])", w) if p]
        raw_words.extend(parts)
    words = raw_words
    norm = [normalize(w) for w in words]
    phrases = sorted(((k.split(), v) for k, v in table.items()), key=lambda kv: -len(kv[0]))
    out: list[str] = []
    i = 0
    while i < len(words):
        for ph, sym in phrases:
            n = len(ph)
            if norm[i:i + n] == ph:
                out.append("\x00" + sym)   # علامة: رمز ترقيم
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    # تجميع: الرموز تلتصق بما قبلها
    result = ""
    for tok in out:
        if tok.startswith("\x00"):
            sym = tok[1:]
            result = result.rstrip(" ") + sym
        else:
            if result and not result.endswith(("\n", " ", "(", "\"", "'", "’")) and not tok.startswith(("'", "’")):
                result += " "
            result += tok
    return result


def _capitalize_sentences(text: str, capitalize_first: bool) -> str:
    chars = list(text)
    cap = capitalize_first
    for i, c in enumerate(chars):
        if cap and c.isalpha():
            chars[i] = c.upper()
            cap = False
        elif c in SENTENCE_END:
            cap = True
    return "".join(chars)


@dataclass
class DictationSession:
    lang: str = "ar"
    last_char: str = "\n"                      # بداية الحقل تُعامل كبداية سطر
    history: list[str] = field(default_factory=list)

    def render(self, text: str) -> str:
        """النص الذي يجب كتابته لهذه الدفعة (مع المسافة البادئة المناسبة)."""
        body = apply_spoken_punctuation(text.strip(), self.lang)
        # Whisper يضيف نقطة في نهاية كل مقطع؛ نحذفها ليقرر المستخدم الترقيم بنفسه
        # إلا إذا نطق بها صراحة (عندها تأتي من apply_spoken_punctuation).
        spoken_end = normalize(text).endswith(tuple(PUNCTUATION.get(self.lang, {})))
        if not spoken_end:
            body = re.sub(r"[.。]$", "", body)
        if not body:
            return ""
        if self.lang in LATIN:
            body = _capitalize_sentences(body, self.last_char in SENTENCE_END)
        needs_space = (self.last_char not in (" ", "\n", "(", "\"")
                       and body[0] not in NO_SPACE_BEFORE)
        return (" " if needs_space else "") + body

    def commit(self, typed: str) -> None:
        if typed:
            self.history.append(typed)
            self.last_char = typed[-1]

    def undo(self) -> int:
        """يرجع عدد الأحرف التي يجب حذفها (Backspace) لإلغاء آخر دفعة."""
        if not self.history:
            return 0
        last = self.history.pop()
        self.last_char = self.history[-1][-1] if self.history else "\n"
        return len(last)
