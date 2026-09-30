"""تحويل مخرجات محرك الإيماءات إلى حركة مؤشر ونقرات فعلية.

- تنعيم One Euro بوحدة البكسل.
- "إرجاع" موضع النقرة: القرص يحرّك طرف السبابة قليلاً، فنثبّت المؤشر حيث كان قبل
  rewind_ms لتقع النقرة على الهدف المقصود.
- السحب يكمل من موضع التثبيت (إزاحة ثابتة) ثم تتلاشى الإزاحة بعد الإفلات.
- الإجراءات غير المتعلقة بالفأرة تُرسل إلى العملية الرئيسية عبر forward().
"""
from __future__ import annotations

from collections import deque
import math
from typing import Callable

from os_layer.base import OSBackend
from vision.filters import OneEuro2D
from vision.gestures import GestureOutput

# تُنفَّذ هنا مباشرة (أقل تأخير)؛ غيرها يُرسل للعملية الرئيسية
LOCAL_ACTIONS = {"click", "double_click", "right_click", "middle_click", "scroll",
                 "zoom_in", "zoom_out", "none", ""}


class PointerController:
    DEADBAND_PX = 2.5  # منطقة ميتة ضد الارتعاش الفيزيولوجي بالبكسل

    def __init__(self, os: OSBackend, vision_cfg, forward: Callable[[str, str], None],
                 paused, screen_rect: tuple[int, int, int, int] | None = None):
        """forward(gesture, action): لتنفيذ إجراء في العملية الرئيسية.
        paused: كائن فيه is_set/set/clear (multiprocessing.Event)."""
        self.os = os
        self.cfg = vision_cfg
        self.forward = forward
        self.paused = paused
        self.rect = screen_rect or os.screen_rect()
        self.filter = OneEuro2D(vision_cfg.min_cutoff, vision_cfg.beta)
        self.history: deque[tuple[float, float, float]] = deque(maxlen=60)
        self.locked_at: tuple[int, int] | None = None
        self.dragging = False
        self.offset = (0.0, 0.0)
        self.last_move: tuple[int, int] | None = None
        self.performed: list[str] = []   # للاختبارات والتشخيص
        self._stable_pos: tuple[float, float] | None = None

    # ------------------------------------------------------------------
    def _to_px(self, u: float, v: float) -> tuple[float, float]:
        left, top, w, h = self.rect
        return left + u * (w - 1), top + v * (h - 1)

    def _pos_before(self, t: float) -> tuple[float, float] | None:
        target = t - self.cfg.tuning.rewind_ms / 1000
        best = None
        for ht, x, y in self.history:
            if ht <= target:
                best = (x, y)
            else:
                break
        if best is None and self.history:
            best = self.history[0][1:]
        return best

    def _move(self, x: float, y: float) -> None:
        p = (int(round(x)), int(round(y)))
        if p != self.last_move:
            self.os.mouse_move(*p)
            self.last_move = p

    def release(self) -> None:
        if self.dragging:
            self.os.mouse_button("left", "up")
            self.dragging = False
        self.locked_at = None
        self._stable_pos = None

    def _run_binding(self, gesture: str, amount: int = 1) -> None:
        action = self.cfg.bindings.get(gesture, "none")
        if action in ("none", ""):
            return
        if action == "scroll":
            self.os.scroll(amount)
            return   # متكرر جداً: بلا إشعار للواجهة
        if action in ("zoom_in", "zoom_out"):
            # Ctrl + عجلة الفأرة: تكبير عام في المتصفحات وOffice والمستكشف
            self.os.scroll(abs(amount) if action == "zoom_in" else -abs(amount), ctrl=True)
        elif action == "click":
            self.os.mouse_button("left", "click", 1)
        elif action == "double_click":
            self.os.mouse_button("left", "click", 2)
        elif action == "right_click":
            self.os.mouse_button("right", "click", 1)
        elif action == "middle_click":
            self.os.mouse_button("middle", "click", 1)
        else:
            if action == "app.pause":  # فوري محلياً للأمان، ثم إبلاغ الرئيسية
                self.pause_now()
            self.forward(gesture, action)
            self.performed.append(f"{gesture}:{action}")
            return
        self.performed.append(f"{gesture}:{action}")
        self.forward(gesture, "")  # إشعار فقط (الإجراء نُفّذ هنا)

    def pause_now(self) -> None:
        self.paused.set()
        self.release()

    # ------------------------------------------------------------------
    def apply(self, out: GestureOutput, t: float) -> None:
        paused = self.paused.is_set()
        if paused:
            self.release()
            if "palm_hold_short" in out.events:
                self.paused.clear()
                self.forward("palm_hold_short", "app.resume")
                self.performed.append("palm_hold_short:app.resume")
            self.filter.reset()
            return

        # الموضع المنعّم الحالي
        fx = fy = None
        if out.pointer is not None:
            raw_x, raw_y = self._to_px(*out.pointer)
            fx, fy = self.filter(raw_x, raw_y, t)
            # استقرار ضد الارتعاش الفيزيولوجي لضمان الدقة أثناء تحديد الأهداف
            if self._stable_pos is not None:
                dist = math.hypot(fx - self._stable_pos[0], fy - self._stable_pos[1])
                if dist < self.DEADBAND_PX:
                    fx, fy = self._stable_pos
                else:
                    self._stable_pos = (fx, fy)
            else:
                self._stable_pos = (fx, fy)
            self.history.append((t, fx, fy))
        else:
            self._stable_pos = None

        for ev in out.events:
            if ev in ("pinch_down", "middle_down"):
                pos = self._pos_before(t) or (self.last_move or self.os.mouse_position())
                self.locked_at = (int(round(pos[0])), int(round(pos[1])))
                self._move(*self.locked_at)
            elif ev == "pinch_tap":
                self.locked_at = None
                self._run_binding("pinch_tap")
            elif ev == "middle_pinch_tap":
                self.locked_at = None
                self._run_binding("middle_pinch_tap")
            elif ev in ("pinch_cancel", "middle_cancel"):
                self.locked_at = None
            elif ev == "drag_start":
                anchor = self.locked_at or self.last_move or self.os.mouse_position()
                self._move(*anchor)
                self.os.mouse_button("left", "down")
                self.dragging = True
                self.performed.append("drag_start")
                self.locked_at = None
                self.offset = (0.0, 0.0) if fx is None else (anchor[0] - fx, anchor[1] - fy)
            elif ev == "drag_end":
                if self.dragging:
                    self.os.mouse_button("left", "up")
                    self.performed.append("drag_end")
                self.dragging = False
            elif ev == "fist_hold":
                self._run_binding("fist_hold")
                if self.paused.is_set():
                    return
            elif ev == "palm_hold_long":
                self._run_binding("palm_hold_long")
            elif ev in ("swipe_left", "swipe_right"):
                self._run_binding(ev)
            elif ev == "zoom_start":
                self.locked_at = None
            elif ev == "hand_lost":
                self.filter.reset()
                self.history.clear()
                self.offset = (0.0, 0.0)
                self._stable_pos = None

        if out.scroll:
            self._run_binding("two_scroll", out.scroll)
        if out.zoom:
            self._run_binding("zoom_in" if out.zoom > 0 else "zoom_out", out.zoom)

        if out.locked or self.locked_at is not None:
            return
        if fx is not None:
            if not self.dragging and self.offset != (0.0, 0.0):
                # تلاشي تدريجي للإزاحة بعد الإفلات
                ox, oy = self.offset
                self.offset = (ox * 0.8, oy * 0.8) if abs(ox) + abs(oy) > 1 else (0.0, 0.0)
            self._move(fx + self.offset[0], fy + self.offset[1])
