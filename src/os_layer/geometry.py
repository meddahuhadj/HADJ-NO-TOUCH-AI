"""هندسة النوافذ (منطق بحت مشترك بين أنظمة التشغيل)."""
from __future__ import annotations


def snap_rect(position: str, work: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    """موضع النافذة داخل `work` (left, top, width, height ← مساحة العمل دون شريط المهام)."""
    left, top, width, height = work
    half_w, half_h = width // 2, height // 2
    third_w = width // 3
    if position == "left":
        return left, top, half_w, height
    if position == "right":
        return left + half_w, top, width - half_w, height
    if position == "top":
        return left, top, width, half_h
    if position == "bottom":
        return left, top + half_h, width, height - half_h
    if position == "topleft":
        return left, top, half_w, half_h
    if position == "topright":
        return left + half_w, top, width - half_w, half_h
    if position == "bottomleft":
        return left, top + half_h, half_w, height - half_h
    if position == "bottomright":
        return left + half_w, top + half_h, width - half_w, height - half_h
    if position == "thirdleft":
        return left, top, third_w, height
    if position == "thirdright":
        return left + width - third_w, top, third_w, height
    if position == "maximize":
        return left, top, width, height
    return None
