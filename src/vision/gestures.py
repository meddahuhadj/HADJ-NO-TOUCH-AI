"""تصنيف الإيماءات من نقاط اليد (21 نقطة من MediaPipe) + آلة حالات زمنية.

منطق بحت بلا كاميرا: المدخل قائمة أيدٍ لكل إطار مع الزمن، والمخرج موضع المؤشر
(بنسب الشاشة 0..1) وأحداث مثل pinch_tap و drag_start و fist_hold.

القواعد مستقلة عن اتجاه اليد لأنها تعتمد على المسافات من الرسغ ونسبتها إلى حجم اليد.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
# (MCP, PIP, DIP, TIP)
FINGERS = {"index": (5, 6, 7, 8), "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}


@dataclass
class Hand:
    landmarks: np.ndarray          # (21, 3) بإحداثيات الصورة المعكوسة (0..1)
    handedness: str = "Right"      # Right | Left (بعد عكس الصورة = اليد الحقيقية)
    score: float = 1.0


@dataclass
class Pose:
    name: str                      # point | pinch | middle_pinch | two | open | fist | other
    extended: dict[str, bool]
    curled: dict[str, bool]
    thumb_extended: bool
    pinch_index: float             # مسافة الإبهام-السبابة / حجم اليد
    pinch_middle: float
    size: float


@dataclass
class GestureOutput:
    pointer: tuple[float, float] | None = None   # موضع المؤشر المطلوب (0..1) أو None = لا تحريك
    locked: bool = False                         # القرص قيد التحديد: ثبّت المؤشر
    events: list[str] = field(default_factory=list)
    pose: str = "none"
    scroll: int = 0                              # نقرات عجلة (موجب = للأعلى)
    zoom: int = 0                                # خطوات تكبير (موجب = تكبير)


def _d(a, b) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def classify(hand: Hand, pinch_enter: float, pinch_exit: float, aspect: float = 4 / 3,
             current_pinch: str | None = None) -> Pose:
    p = np.asarray(hand.landmarks, dtype=float)[:, :2].copy()
    p[:, 0] *= aspect  # مسافات متساوية الاتجاه رغم اختلاف عرض/ارتفاع الصورة
    w = p[WRIST]
    size = max(_d(w, p[9]), 1e-6)
    ext, curl = {}, {}
    for name, (mcp, pip, _dip, tip) in FINGERS.items():
        d_tip, d_pip, d_mcp = _d(p[tip], w), _d(p[pip], w), _d(p[mcp], w)
        if name == "index":
            # مراعاة منظور الكاميرا عند توجيه السبابة للأمام نحو الشاشة
            ext[name] = (d_tip > d_pip * 1.05 and d_pip > d_mcp * 0.98) or (_d(p[tip], p[mcp]) > size * 0.45 and d_tip > d_pip)
        else:
            ext[name] = d_tip > d_pip * 1.15 and d_pip > d_mcp
        curl[name] = d_tip < d_pip
    thumb_ext = _d(p[THUMB_TIP], p[17]) > _d(p[THUMB_IP], p[17]) * 1.05 and \
        _d(p[THUMB_TIP], p[5]) > size * 0.45
    pi = _d(p[THUMB_TIP], p[8]) / size
    pm = _d(p[THUMB_TIP], p[12]) / size

    # القرص بعتبتين (hysteresis): الدخول تحت pinch_enter والخروج فوق pinch_exit.
    # لا يُحتسب القرص إذا كان الإصبع مطوياً (قبضة) لتفادي نقرات عرضية عند إغلاق اليد.
    def pinched(kind: str, dist: float, finger: str) -> bool:
        limit = pinch_exit if current_pinch == kind else pinch_enter
        return dist < limit and not curl[finger]

    pin_i, pin_m = pinched("index", pi, "index"), pinched("middle", pm, "middle")
    if pin_i and pin_m:  # كلاهما قريب: الأقرب يفوز (مع أولوية للحالي)
        if current_pinch == "middle" or (current_pinch is None and pm < pi):
            pin_i = False
        else:
            pin_m = False

    four = ("index", "middle", "ring", "pinky")
    if pin_i:
        name = "pinch"
    elif pin_m:
        name = "middle_pinch"
    elif all(curl[f] for f in four):
        name = "fist"
    elif all(ext[f] for f in four) and thumb_ext:
        name = "open"
    elif ext["index"] and ext["middle"] and not ext["ring"] and not ext["pinky"]:
        name = "two"
    elif ext["index"] and not ext["middle"] and not ext["ring"]:
        name = "point"
    else:
        name = "other"
    return Pose(name, ext, curl, thumb_ext, pi, pm, size)


class GestureEngine:
    """آلة الحالات: قرص/سحب/نقر أيمن/قبضة/كف، مع تتبع يد واحدة."""

    def __init__(self, tuning, zone=(0.2, 0.15, 0.8, 0.75), hand_pref: str = "any",
                 aspect: float = 4 / 3):
        self.t = tuning
        self.zone = zone
        self.hand_pref = hand_pref
        self.aspect = aspect
        self.reset()

    def reset(self) -> None:
        self._pinch: str | None = None       # index | middle
        self._pinch_t0 = 0.0
        self._pinch_start_xy = (0.0, 0.0)
        self._dragging = False
        self._pose_name = "none"
        self._pose_since = 0.0
        self._fired: set[str] = set()
        self._last_seen = None
        self._last_wrist = None
        self._lost_reported = True
        self._scroll_ref: float | None = None
        self._swipe_hist: deque[tuple[float, float, float]] = deque()
        self._swipe_block_until = 0.0
        self._zoom_ref: float | None = None
        self._suppress_pinch = False

    # ------------------------------------------------------------------
    def _select(self, hands: list[Hand]) -> Hand | None:
        cands = hands
        if self.hand_pref in ("right", "left"):
            cands = [h for h in hands if h.handedness.lower() == self.hand_pref]
        if not cands:
            return None
        if self._last_wrist is not None and len(cands) > 1:
            lw = self._last_wrist
            return min(cands, key=lambda h: _d(h.landmarks[WRIST], lw))
        return max(cands, key=lambda h: h.score)

    def map_to_screen(self, x: float, y: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self.zone
        u = (x - x0) / max(x1 - x0, 1e-6)
        v = (y - y0) / max(y1 - y0, 1e-6)
        return min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)

    def update(self, hands: list[Hand], now: float) -> GestureOutput:
        out = GestureOutput()
        # ---- التكبير بيدين: قرص بكلتا اليدين ثم التباعد/التقارب ----
        if len(hands) >= 2:
            cur = "index" if self._zoom_ref is not None else None
            two = sorted(hands, key=lambda h: -h.score)[:2]
            if all(classify(h, self.t.pinch_enter, self.t.pinch_exit, self.aspect, cur).name == "pinch"
                   for h in two):
                return self._zoom(two, now, out)
        if self._zoom_ref is not None:
            self._zoom_ref = None
            self._suppress_pinch = True   # اليد الباقية ما زالت تقرص: لا نقرة عند إفلاتها
            out.events.append("zoom_end")

        hand = self._select(hands)
        if hand is None:
            return self._on_missing(now, out)
        self._last_seen = now
        self._last_wrist = hand.landmarks[WRIST]
        self._lost_reported = False

        pose = classify(hand, self.t.pinch_enter, self.t.pinch_exit, self.aspect, self._pinch)
        out.pose = pose.name
        tip = hand.landmarks[8]
        pointer = self.map_to_screen(float(tip[0]), float(tip[1]))

        # ---- مدة ثبات الوضعية (للقبضة والكف) ----
        if pose.name != self._pose_name:
            self._pose_name = pose.name
            self._pose_since = now
            self._fired.clear()
        held_ms = (now - self._pose_since) * 1000

        # ---- التمرير بإصبعين ----
        self._two_finger_scroll(hand, pose.name, held_ms, out)
        # ---- سحب اليد المفتوحة يميناً/يساراً ----
        self._swipe(hand, pose.name, now, out)

        # ---- القرص بالسبابة: نقرة أو سحب ----
        current = {"pinch": "index", "middle_pinch": "middle"}.get(pose.name)
        if self._suppress_pinch:
            if current is None:
                self._suppress_pinch = False
            current = None
        if self._pinch is None and current:
            self._pinch = current
            self._pinch_t0 = now
            self._pinch_start_xy = (float(tip[0]), float(tip[1]))
            out.events.append("pinch_down" if current == "index" else "middle_down")
        elif self._pinch is not None and current != self._pinch:
            # انتهاء القرص (أو تحوّل إلى نوع آخر)
            released_to_fist = pose.name == "fist"
            if self._pinch == "index":
                if self._dragging:
                    out.events.append("drag_end")
                elif released_to_fist:
                    out.events.append("pinch_cancel")
                else:
                    out.events.append("pinch_tap")
            else:
                dur = (now - self._pinch_t0) * 1000
                ok = not released_to_fist and dur < 1500
                out.events.append("middle_pinch_tap" if ok else "middle_cancel")
            self._pinch = None
            self._dragging = False
            if current:  # قرص من نوع آخر مباشرة
                self._pinch = current
                self._pinch_t0 = now
                self._pinch_start_xy = (float(tip[0]), float(tip[1]))
                out.events.append("pinch_down" if current == "index" else "middle_down")

        if self._pinch == "index" and not self._dragging:
            moved = _d((tip[0], tip[1]), self._pinch_start_xy)
            if (now - self._pinch_t0) * 1000 >= self.t.drag_hold_ms or moved >= self.t.drag_move:
                self._dragging = True
                out.events.append("drag_start")

        # ---- القبضة والكف المفتوح (مرة واحدة لكل ثبات) ----
        if pose.name == "fist" and held_ms >= self.t.fist_ms and "fist" not in self._fired:
            self._fired.add("fist")
            out.events.append("fist_hold")
        if pose.name == "open":
            if held_ms >= self.t.palm_resume_ms and "palm_s" not in self._fired:
                self._fired.add("palm_s")
                out.events.append("palm_hold_short")
            if held_ms >= self.t.palm_long_ms and "palm_l" not in self._fired:
                self._fired.add("palm_l")
                out.events.append("palm_hold_long")

        # ---- المؤشر ----
        if self._pinch is not None and not self._dragging:
            out.locked = True
            out.pointer = None
        elif self._dragging or pose.name in ("point", "other") and pose.extended["index"]:
            out.pointer = pointer
        return out

    # ------------------------------------------------------------------
    def _two_finger_scroll(self, hand: Hand, pose: str, held_ms: float, out: GestureOutput) -> None:
        if pose != "two" or held_ms < self.t.scroll_settle_ms:
            self._scroll_ref = None
            return
        y = (float(hand.landmarks[8][1]) + float(hand.landmarks[12][1])) / 2
        if self._scroll_ref is None:
            self._scroll_ref = y
            return
        step = self.t.scroll_step
        n = int((self._scroll_ref - y) / step)   # اليد للأعلى ← موجب ← تمرير للأعلى
        if n:
            self._scroll_ref -= n * step           # نحتفظ بالباقي لحركة سلسة
            out.scroll += -n if self.t.scroll_invert else n

    def _swipe(self, hand: Hand, pose: str, now: float, out: GestureOutput) -> None:
        if pose != "open":
            self._swipe_hist.clear()
            return
        w = hand.landmarks[WRIST]
        self._swipe_hist.append((now, float(w[0]), float(w[1])))
        window = self.t.swipe_ms / 1000
        while self._swipe_hist and now - self._swipe_hist[0][0] > window:
            self._swipe_hist.popleft()
        if now < self._swipe_block_until or len(self._swipe_hist) < 3:
            return
        _, x0, y0 = self._swipe_hist[0]
        dx, dy = float(w[0]) - x0, float(w[1]) - y0
        if abs(dx) >= self.t.swipe_dist and abs(dy) <= self.t.swipe_max_dy:
            out.events.append("swipe_right" if dx > 0 else "swipe_left")
            self._swipe_block_until = now + self.t.swipe_cooldown_ms / 1000
            self._swipe_hist.clear()
            self._pose_since = now          # السحب لا يُحتسب ضمن "كف مفتوح ثابت"
            self._fired.clear()

    def _zoom(self, hands: list[Hand], now: float, out: GestureOutput) -> GestureOutput:
        self._last_seen = now
        self._lost_reported = False
        out.pose = "zoom"
        out.locked = True

        def pinch_point(h: Hand):
            p = (h.landmarks[4][:2] + h.landmarks[8][:2]) / 2
            return (float(p[0]) * self.aspect, float(p[1]))

        dist = max(_d(pinch_point(hands[0]), pinch_point(hands[1])), 1e-6)
        if self._zoom_ref is None:
            # إلغاء أي قرص/سحب بيد واحدة بدأ قبل وصول اليد الثانية
            if self._dragging:
                out.events.append("drag_end")
            elif self._pinch == "index":
                out.events.append("pinch_cancel")
            elif self._pinch == "middle":
                out.events.append("middle_cancel")
            self._pinch = None
            self._dragging = False
            self._scroll_ref = None
            self._zoom_ref = dist
            out.events.append("zoom_start")
            return out
        ratio = dist / self._zoom_ref
        step = 1 + self.t.zoom_step
        if ratio >= step:
            out.zoom += 1
            out.events.append("zoom_in")
            self._zoom_ref = dist
        elif ratio <= 1 / step:
            out.zoom -= 1
            out.events.append("zoom_out")
            self._zoom_ref = dist
        return out

    def _on_missing(self, now: float, out: GestureOutput) -> GestureOutput:
        out.pose = "none"
        if self._last_seen is None or self._lost_reported:
            return out
        if (now - self._last_seen) * 1000 < self.t.lost_ms:
            # فقدان لحظي (إطار أو اثنان): حافظ على الحالة
            out.locked = self._pinch is not None and not self._dragging
            return out
        if self._dragging:
            out.events.append("drag_end")
        elif self._pinch is not None:
            out.events.append("pinch_cancel" if self._pinch == "index" else "middle_cancel")
        out.events.append("hand_lost")
        self._pinch = None
        self._dragging = False
        self._pose_name = "none"
        self._fired.clear()
        self._lost_reported = True
        return out
