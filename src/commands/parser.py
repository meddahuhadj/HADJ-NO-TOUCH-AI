"""محلل الأوامر: يطابق العبارة المنطوقة مع قوالب الأوامر (مطابقة تامة ثم تقريبية).

القالب = كلمات ثابتة + خانة اختيارية واحدة في النهاية مثل {app} أو {text}.
قيمة الخانة تؤخذ من النص الأصلي (بهمزاته) وليس من النص الموحّد، لأنها قد تُكتب.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from commands.text import grammar_form, normalize

log = logging.getLogger(__name__)

_SLOT = re.compile(r"^\{(\w+)\}$")
_SPLIT = re.compile(r"\s+")

# كلمات مجاملة تُحذف من بداية العبارة ونهايتها
FILLERS = {
    "ar": ["من فضلك", "لو سمحت", "رجاء", "رجاءا", "يا"],
    "en": ["please", "hey", "could you", "can you"],
    "fr": ["s il te plait", "s il vous plait", "stp", "svp", "peux tu", "pourrais tu"],
}

YES = {"ar": ["نعم", "اجل", "تاكيد", "اكد", "موافق", "ايوه"], "en": ["yes", "confirm", "okay", "ok", "sure"],
       "fr": ["oui", "confirme", "d'accord", "ok", "vas-y"]}
NO = {"ar": ["لا", "الغاء", "الغ", "كلا"], "en": ["no", "cancel", "abort"],
      "fr": ["non", "annule", "annuler", "laisse tomber"]}

# القوالب الأقصر من هذا (بالأحرف) تتطلب تطابقاً تاماً لتفادي الإيجابيات الكاذبة
MIN_FUZZY_LEN = 4


@dataclass
class CommandSpec:
    id: str
    phrases: dict[str, list[str]]
    steps: list[dict[str, Any]]
    dangerous: bool = False
    always: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "CommandSpec":
        if "steps" in d:
            steps = [dict(s) for s in d["steps"]]
        elif "action" in d:
            steps = [{"action": d["action"], **(d.get("args") or {})}]
        else:
            raise ValueError(f"الأمر {d.get('id')!r} بلا action ولا steps")
        phrases = d.get("phrases") or {}
        if isinstance(phrases, list):  # عبارات بدون تحديد لغة ← لكل اللغات
            phrases = {"*": phrases}
        return cls(
            id=str(d.get("id") or phrases),
            phrases={k: list(v) for k, v in phrases.items()},
            steps=steps,
            dangerous=bool(d.get("dangerous", False)),
            always=bool(d.get("always", False)),
        )


@dataclass
class _Template:
    spec: CommandSpec
    words: list[str]            # الكلمات الثابتة (موحّدة)
    slot: str | None            # اسم الخانة إن وجدت (دائماً في النهاية)
    grammar: str = ""           # الشكل الأصلي بلكناته (لقاموس Vosk المقيّد)
    joined: str = field(init=False)

    def __post_init__(self):
        self.joined = " ".join(self.words)


@dataclass
class Match:
    spec: CommandSpec
    slots: dict[str, str]
    score: float
    phrase: str

    @property
    def id(self) -> str:
        return self.spec.id


def split_raw(text: str) -> tuple[list[str], list[str]]:
    """يرجع (الكلمات الأصلية، الكلمات الموحّدة) بنفس الطول."""
    raw, norm = [], []
    for tok in _SPLIT.split((text or "").strip()):
        parts = [p for p in re.split(r"(?<=['’])", tok) if p]
        for p in parts:
            n = normalize(p)
            if n:
                raw.append(p)
                norm.append(n)
    return raw, norm


def strip_fillers(raw: list[str], norm: list[str], lang: str) -> tuple[list[str], list[str]]:
    fillers = [f.split() for f in FILLERS.get(lang, [])]
    changed = True
    while changed and norm:
        changed = False
        for f in fillers:
            n = len(f)
            if len(norm) > n and norm[:n] == f:
                raw, norm, changed = raw[n:], norm[n:], True
            elif len(norm) > n and norm[-n:] == f:
                raw, norm, changed = raw[:-n], norm[:-n], True
    return raw, norm


class CommandParser:
    def __init__(self, specs: list[dict] | list[CommandSpec], threshold: int = 80):
        self.threshold = threshold
        self.specs: list[CommandSpec] = []
        self._templates: dict[str, list[_Template]] = {}
        for s in specs:
            try:
                self.add(s if isinstance(s, CommandSpec) else CommandSpec.from_dict(s))
            except (ValueError, TypeError) as e:
                log.error("تم تجاهل أمر غير صالح: %s", e)

    def add(self, spec: CommandSpec) -> None:
        self.specs.append(spec)
        for lang, phrases in spec.phrases.items():
            for p in phrases:
                words = normalize(p).split()
                slot = None
                if words and (m := _SLOT.match(words[-1])):
                    slot, words = m.group(1), words[:-1]
                if any(_SLOT.match(w) for w in words):
                    log.error("الأمر %s: الخانة يجب أن تكون في نهاية العبارة: %r", spec.id, p)
                    continue
                if not words:
                    continue
                self._templates.setdefault(lang, []).append(
                    _Template(spec, words, slot, grammar_form(p) or " ".join(words)))

    def templates(self, lang: str) -> list[_Template]:
        return self._templates.get(lang, []) + self._templates.get("*", [])

    def phrases(self, lang: str, with_slots: bool = False) -> list[str]:
        """العبارات الثابتة بشكلها الأصلي (للتعرف المقيّد بالقواعد)."""
        return sorted({t.grammar for t in self.templates(lang) if with_slots or not t.slot})

    # ------------------------------------------------------------------
    def parse(self, text: str, lang: str, only_always: bool = False) -> Match | None:
        raw, norm = strip_fillers(*split_raw(text), lang)
        if not norm:
            return None
        utter = " ".join(norm)
        best: Match | None = None
        for t in self.templates(lang):
            if only_always and not t.spec.always:
                continue
            m = self._score(t, raw, norm, utter)
            if m and (best is None or m.score > best.score):
                best = m
        return best

    def _score(self, t: _Template, raw, norm, utter) -> Match | None:
        k = len(t.words)
        if t.slot is None:
            if norm == t.words:
                return Match(t.spec, {}, 200.0, t.joined)
            if len(t.joined) < MIN_FUZZY_LEN:
                return None
            score = fuzz.ratio(utter, t.joined)
            if score >= self.threshold:
                return Match(t.spec, {}, float(score), t.joined)
            return None
        # قالب بخانة: الكلمات الثابتة يجب أن تتبعها كلمة واحدة على الأقل
        if len(norm) <= k:
            return None
        head = " ".join(norm[:k])
        value = " ".join(raw[k:])
        if norm[:k] == t.words:
            return Match(t.spec, {t.slot: value}, 150.0 + k, t.joined)
        if len(t.joined) < MIN_FUZZY_LEN:
            return None
        score = fuzz.ratio(head, t.joined)
        if score >= self.threshold:
            return Match(t.spec, {t.slot: value}, float(score) - 1, t.joined)
        return None


def is_phrase(text: str, lang: str, table: dict[str, list[str]], threshold: int = 85) -> bool:
    raw, norm = strip_fillers(*split_raw(text), lang)
    utter = " ".join(norm)
    if not utter:
        return False
    for p in table.get(lang, []):
        p = normalize(p)
        if utter == p or (len(p) >= MIN_FUZZY_LEN and fuzz.ratio(utter, p) >= threshold):
            return True
    return False


def is_yes(text: str, lang: str) -> bool:
    return is_phrase(text, lang, YES)


def is_no(text: str, lang: str) -> bool:
    return is_phrase(text, lang, NO)
