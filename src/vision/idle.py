"""سكون الكاميرا عند غياب اليد (منطق بحت بلا كاميرا لكي يُختبر):

  active  : معالجة كاملة (~30 إطار/ث).
  dozing  : بعد light_s دون يد ← معالجة خفيفة (light_fps). الكاميرا تعمل: ظهور اليد يوقظ فوراً.
  asleep  : بعد deep_s دون يد ← تُحرَّر الكاميرا (يُطفأ ضوؤها، لا معالجة إطلاقاً).
            الإيقاظ من الخارج فقط (كلمة التنبيه، أمر صوتي، القائمة، لمس الفأرة/لوحة المفاتيح).

لا نوم عميق أثناء الإيقاف الطارئ (الكف المفتوح يجب أن يبقى قادراً على الاستئناف)
ولا أي سكون أثناء المعايرة. 0 = تعطيل المستوى.
"""
from __future__ import annotations

ACTIVE, DOZING, ASLEEP = "active", "dozing", "asleep"


class IdleManager:
    def __init__(self, light_s: float, deep_s: float, now: float):
        self.light_s = max(0.0, light_s)
        self.deep_s = max(0.0, deep_s)
        self.state = ACTIVE
        self.last_activity = now

    def wake(self, now: float) -> str | None:
        """إيقاظ خارجي. يرجع الحالة الجديدة إن تغيّرت."""
        self.last_activity = now
        return self._set(ACTIVE)

    def update(self, now: float, hand: bool, paused: bool = False, calibrating: bool = False) -> str | None:
        """يُستدعى لكل إطار مُعالَج. يرجع الحالة الجديدة عند الانتقال فقط."""
        if hand or calibrating:
            self.last_activity = now
            return self._set(ACTIVE)
        idle = now - self.last_activity
        if self.deep_s and idle >= self.deep_s and not paused:
            return self._set(ASLEEP)
        if self.light_s and idle >= self.light_s:
            return self._set(DOZING)
        return None

    def _set(self, state: str) -> str | None:
        if state == self.state:
            return None
        self.state = state
        return state
