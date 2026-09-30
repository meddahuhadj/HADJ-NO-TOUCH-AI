"""بوابة كلمة التنبيه.

- "حاسوب افتح المفكرة" ← يُنفَّذ "افتح المفكرة" مباشرة.
- "حاسوب" وحدها ← وضع الانتظار (armed) لمدة wake_timeout_s، والعبارة التالية أمر.
- بعد تنفيذ أمر، تبقى البوابة مفتوحة followup_s ثانية لأوامر متتالية بلا تنبيه.
- في وضع الاستماع المستمر كل عبارة أمر.
"""
from __future__ import annotations

import time
from typing import Callable

from rapidfuzz import fuzz

from commands.parser import split_raw
from commands.text import normalize

# كلمات قد تسبق كلمة التنبيه: "يا حاسوب"، "hey computer"، "dis ordinateur"، "l'ordinateur"
_PREFIXES = {"يا", "hey", "ok", "okay", "hi", "dis", "he", "eh", "l"}


def strip_wake(text: str, wake_words: list[str], threshold: int = 75) -> tuple[bool, str]:
    """إن بدأت العبارة بكلمة التنبيه: يرجع (True, باقي العبارة الأصلية)."""
    raw, norm = split_raw(text)
    starts = (0, 1) if norm and norm[0] in _PREFIXES else (0,)
    for w in wake_words:
        ww = normalize(w).split()
        n = len(ww)
        target = " ".join(ww)
        for start in starts:
            if not ww or len(norm) < start + n:
                continue
            head = " ".join(norm[start:start + n])
            # السماح بأداة التعريف: "الحاسوب" = "حاسوب"
            if head == target or head == "ال" + target or fuzz.ratio(head, target) >= threshold:
                return True, " ".join(raw[start + n:])
    return False, text


class WakeGate:
    def __init__(self, wake_words: list[str], continuous: bool = False,
                 timeout_s: float = 5.0, followup_s: float = 6.0,
                 clock: Callable[[], float] = time.monotonic):
        self.wake_words = wake_words
        self.continuous = continuous
        self.timeout_s = timeout_s
        self.followup_s = followup_s
        self.clock = clock
        self._armed_until = 0.0

    @property
    def armed(self) -> bool:
        return self.continuous or self.clock() < self._armed_until

    def arm(self, seconds: float | None = None) -> None:
        self._armed_until = self.clock() + (self.timeout_s if seconds is None else seconds)

    def disarm(self) -> None:
        self._armed_until = 0.0

    def after_command(self) -> None:
        if self.followup_s > 0:
            self.arm(self.followup_s)

    def process(self, text: str) -> tuple[str | None, bool]:
        """يرجع (نص الأمر أو None، هل نُطقت كلمة التنبيه الآن)."""
        found, rest = strip_wake(text, self.wake_words)
        if found:
            if not rest.strip():
                self.arm()
                return None, True
            return rest, True
        if self.armed:
            return text, False
        return None, False
