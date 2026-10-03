"""Regenerate the PWA icon set from the vector mark, with no third-party deps.

The mark is described with signed distance functions and rasterised with analytic
edge antialiasing, then written as PNG with the stdlib zlib encoder.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "icons"

CANVAS_TOP = (0x09, 0x10, 0x1E)
CANVAS_BOT = (0x04, 0x07, 0x0D)
ACCENT = (0x4C, 0xC9, 0xF0)
ACCENT_DEEP = (0x0E, 0xA5, 0xE9)
VIOLET = (0xA7, 0x8B, 0xFA)
WHITE = (255, 255, 255)

GAP_DEG = 56.0


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    t = clamp(t)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def sd_round_rect(px, py, cx, cy, hw, hh, r):
    qx = abs(px - cx) - (hw - r)
    qy = abs(py - cy) - (hh - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def sd_ring(px, py, cx, cy, radius, thickness):
    return abs(math.hypot(px - cx, py - cy) - radius) - thickness / 2.0


def sd_segment(px, py, ax, ay, bx, by, thickness):
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else clamp(((px - ax) * vx + (py - ay) * vy) / denom)
    return math.hypot(px - (ax + vx * t), py - (ay + vy * t)) - thickness / 2.0


def coverage(d, softness=0.7):
    return clamp(0.5 - d / softness)


def geometry(size, maskable):
    pad = 0.19 if maskable else 0.17
    unit = size * (0.5 - pad)
    cx = cy = size / 2.0
    ring_r = unit * 0.60
    tick = unit * 0.205
    return {
        "cx": cx,
        "cy": cy,
        "unit": unit,
        "ring_r": ring_r,
        "ring_t": unit * 0.115,
        "pupil_r": unit * 0.20,
        "pupil": (cx + unit * 0.19, cy - unit * 0.19),
        "tick_t": unit * 0.085,
        "ticks": (
            (cx, cy - ring_r - tick),
            (cx, cy + ring_r + tick),
            (cx - ring_r - tick, cy),
            (cx + ring_r + tick, cy),
        ),
        "plate_r": size * 0.5 if maskable else size * 0.235,
    }


def render(size, maskable=False):
    g = geometry(size, maskable)
    cx, cy, unit = g["cx"], g["cy"], g["unit"]
    gap = math.radians(GAP_DEG)
    gap_soft = 1.6 / max(unit, 1.0)
    out = bytearray()
    inv = 1.0 / size

    for y in range(size):
        out.append(0)
        py = y + 0.5
        base = mix(CANVAS_TOP, CANVAS_BOT, (py - (cy - size / 2.0)) * inv)
        for x in range(size):
            px = x + 0.5
            a_plate = coverage(sd_round_rect(px, py, cx, cy, size / 2.0, size / 2.0, g["plate_r"]))
            if a_plate <= 0.0:
                out.extend((0, 0, 0, 0))
                continue

            d = math.hypot(px - cx, py - cy) * inv / 0.55
            col = mix(base, ACCENT_DEEP, max(0.0, 1.0 - d) ** 2 * 0.18)

            ang = math.atan2(py - cy, px - cx)
            in_gap = -gap < ang < gap
            ring = sd_ring(px, py, cx, cy, g["ring_r"], g["ring_t"])
            if in_gap:
                fade = min(1.0, (abs(ang) - (gap - gap_soft)) / (2 * gap_soft))
                a = coverage(ring - unit * 0.05) * fade
                col = mix(col, mix(VIOLET, ACCENT, 0.4), a * 0.85)
            elif ring <= g["ring_t"] * 0.75:
                a = coverage(ring)
                col = mix(col, mix(ACCENT_DEEP, ACCENT, clamp(-ring / (unit * 0.06))), a)

            pup = math.hypot(px - g["pupil"][0], py - g["pupil"][1])
            if pup <= g["pupil_r"] + 1.0:
                col = mix(col, mix(ACCENT, WHITE, 0.22), coverage(pup - g["pupil_r"]))

            for tx, ty in g["ticks"]:
                if abs(px - tx) < unit * 0.5 and abs(py - ty) < unit * 0.5:
                    col = mix(col, ACCENT, coverage(sd_segment(px, py, tx, ty, cx, cy, g["tick_t"])) * 0.9)

            out.extend(
                (
                    round(col[0]),
                    round(col[1]),
                    round(col[2]),
                    round(255 * a_plate),
                )
            )
    return bytes(out)


def write_png(path, size, maskable=False):
    raw = render(size, maskable)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return len(png)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-192.png", 192, True),
        ("icon-maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, False),
        ("favicon-64.png", 64, False),
    ]
    for name, size, maskable in jobs:
        kb = write_png(OUT / name, size, maskable) / 1024
        print(f"{name:28} {size:4}px {kb:7.1f} KB  maskable={maskable}", flush=True)


if __name__ == "__main__":
    main()
