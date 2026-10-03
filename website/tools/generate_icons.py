#!/usr/bin/env python3
"""Rasterise the HADJ NO-TOUCH mark into the PNG set required by the PWA manifest.

Pure standard library: shapes are described with signed distance functions and
rendered with analytic antialiasing, then written as 8-bit RGBA PNG via zlib.
Run with ``python web/tools/generate_icons.py`` from the repository root.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

# --------------------------------------------------------------------------- #
# Mark geometry, expressed on a 512x512 grid centred on (256, 256)
# --------------------------------------------------------------------------- #

CANVAS = (0x06, 0x0A, 0x12)
CANVAS_DEEP = (0x04, 0x07, 0x0D)
CYAN = (0x4C, 0xC9, 0xF0)
CYAN_DEEP = (0x0E, 0xA5, 0xE9)

EYE_TOP = ((84, 256), (256, 112), (428, 256))
EYE_BOTTOM = ((428, 256), (256, 400), (84, 256))
EYE_HALF_WIDTH = 13.0
IRIS_CENTRE = (256.0, 256.0)
IRIS_RADIUS = 56.0
IRIS_HALF_WIDTH = 11.0
PUPIL_RADIUS = 17.0
PINCH_LEFT = ((140, 192), (176, 256), (140, 320))
PINCH_RIGHT = ((372, 192), (336, 256), (372, 320))
PINCH_HALF_WIDTH = 11.0

GRID = 512.0
CENTRE = (GRID / 2.0, GRID / 2.0)


# --------------------------------------------------------------------------- #
# Canvas
# --------------------------------------------------------------------------- #


class Raster:
    def __init__(self, width: int, height: int, top: tuple, bottom: tuple) -> None:
        self.w = width
        self.h = height
        self.px = bytearray(width * height * 3)
        span = max(1, height - 1)
        for y in range(height):
            t = y / span
            row = (
                round(top[0] + (bottom[0] - top[0]) * t),
                round(top[1] + (bottom[1] - top[1]) * t),
                round(top[2] + (bottom[2] - top[2]) * t),
            )
            base = y * width * 3
            for x in range(width):
                i = base + x * 3
                self.px[i] = row[0]
                self.px[i + 1] = row[1]
                self.px[i + 2] = row[2]

    def _blend(self, x: int, y: int, rgb: tuple, alpha: float) -> None:
        if alpha <= 0.0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        if alpha > 1.0:
            alpha = 1.0
        i = (y * self.w + x) * 3
        inv = 1.0 - alpha
        self.px[i] = round(self.px[i] * inv + rgb[0] * alpha)
        self.px[i + 1] = round(self.px[i + 1] * inv + rgb[1] * alpha)
        self.px[i + 2] = round(self.px[i + 2] * inv + rgb[2] * alpha)

    def paint_box(self, x0: int, y0: int, x1: int, y1: int, sdf, rgb, alpha) -> None:
        x0 = max(0, int(math.floor(x0)))
        y0 = max(0, int(math.floor(y0)))
        x1 = min(self.w - 1, int(math.ceil(x1)))
        y1 = min(self.h - 1, int(math.ceil(y1)))
        for y in range(y0, y1 + 1):
            fy = y + 0.5
            for x in range(x0, x1 + 1):
                d = sdf(x + 0.5, fy)
                if d >= 0.5:
                    continue
                cov = 0.5 - d
                if cov > 1.0:
                    cov = 1.0
                self._blend(x, y, rgb, cov * alpha)

    def to_png(self) -> bytes:
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)
            start = y * stride
            raw += self.px[start:start + stride]
        comp = zlib.compress(bytes(raw), 9)

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        header = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")


# --------------------------------------------------------------------------- #
# Signed distance helpers
# --------------------------------------------------------------------------- #


def sd_segment(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0.0 else (wx * vx + wy * vy) / denom
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    dx, dy = wx - t * vx, wy - t * vy
    return math.hypot(dx, dy)


def sd_polyline(segments):
    def sdf(px, py):
        best = 1e9
        for (ax, ay), (bx, by) in segments:
            d = sd_segment(px, py, ax, ay, bx, by)
            if d < best:
                best = d
        return best

    return sdf


def tessellate_quad(p0, p1, p2, steps=72):
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append(
            (
                u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
            )
        )
    return out


def scaled(points, factor):
    return [
        (CENTRE[0] + (p[0] - CENTRE[0]) * factor, CENTRE[1] + (p[1] - CENTRE[1]) * factor)
        for p in points
    ]


def bounds(points, pad):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render(size: int, mark_scale: float, glow: bool, flat: bool) -> Raster:
    k = size / GRID
    raster = Raster(size, size, CANVAS, CANVAS_DEEP if not flat else CANVAS)

    if glow:
        glow_r = 236.0 * mark_scale * k
        gcx, gcy = IRIS_CENTRE[0] * k, IRIS_CENTRE[1] * k

        def glow_sdf(px, py):
            return math.hypot(px - gcx, py - gcy) - glow_r

        raster.paint_box(
            gcx - glow_r - 2,
            gcy - glow_r - 2,
            gcx + glow_r + 2,
            gcy + glow_r + 2,
            glow_sdf,
            CYAN_DEEP,
            0.16,
        )

    def stroke(pts, half_width, rgb, alpha=1.0):
        world = scaled(pts, mark_scale)
        hw = half_width * mark_scale * k
        segments = list(zip(world, world[1:]))
        sdf = sd_polyline(segments)
        x0, y0, x1, y1 = bounds(world, hw + 2.0)
        raster.paint_box(
            x0 * k, y0 * k, x1 * k, y1 * k,
            lambda px, py: sdf(px / k, py / k) * k - hw,
            rgb, alpha,
        )

    def disc(cx, cy, radius, rgb, alpha=1.0, filled=True):
        wx = CENTRE[0] + (cx - CENTRE[0]) * mark_scale
        wy = CENTRE[1] + (cy - CENTRE[1]) * mark_scale
        r = radius * mark_scale * k
        sx, sy = wx * k, wy * k
        if filled:
            sdf = lambda px, py: math.hypot(px - sx, py - sy) - r  # noqa: E731
        else:
            sdf = lambda px, py: abs(math.hypot(px - sx, py - sy) - r)  # noqa: E731
        raster.paint_box(sx - r - 2, sy - r - 2, sx + r + 2, sy + r + 2, sdf, rgb, alpha)

    eye = tessellate_quad(*EYE_TOP)[:-1] + tessellate_quad(*EYE_BOTTOM)[:-1] + [EYE_TOP[0]]
    stroke(eye, EYE_HALF_WIDTH, CYAN)
    stroke(PINCH_LEFT, PINCH_HALF_WIDTH, CYAN)
    stroke(PINCH_RIGHT, PINCH_HALF_WIDTH, CYAN)
    disc(IRIS_CENTRE[0], IRIS_CENTRE[1], IRIS_RADIUS, CYAN, filled=False)
    disc(IRIS_CENTRE[0], IRIS_CENTRE[1], PUPIL_RADIUS, CYAN)
    return raster


def main() -> None:
    here = Path(__file__).resolve().parent
    out = here.parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("icon-192.png", 192, 1.10, True, False),
        ("icon-512.png", 512, 1.10, True, False),
        ("icon-maskable-512.png", 512, 0.82, False, True),
        ("apple-touch-icon.png", 180, 0.95, True, True),
    ]
    for name, size, mark_scale, glow, flat in jobs:
        data = render(size, mark_scale, glow, flat).to_png()
        (out / name).write_bytes(data)
        print(f"{name:26s} {size}x{size}  {len(data):>7d} bytes")


if __name__ == "__main__":
    main()
