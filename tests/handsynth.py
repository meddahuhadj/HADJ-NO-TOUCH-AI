"""توليد نقاط يد اصطناعية (21 نقطة بنفس ترتيب MediaPipe) لاختبار مصنّف الإيماءات.

الرسغ في (0.5, 0.8) والأصابع للأعلى. الإحداثيات بنسب الصورة (y للأسفل).
"""
from __future__ import annotations

import math

import numpy as np

from vision.gestures import Hand

W = (0.5, 0.8)
MCP = {"index": (0.44, 0.60), "middle": (0.50, 0.58), "ring": (0.56, 0.60), "pinky": (0.61, 0.64)}
ORDER = ["index", "middle", "ring", "pinky"]


def _finger(mcp, state):
    x, y = mcp
    if state == "ext":
        return [(x, y), (x, y - 0.07), (x, y - 0.12), (x, y - 0.16)]
    if state == "curl":
        return [(x, y), (x, y - 0.05), (x, y - 0.02), (x, y + 0.03)]
    raise ValueError(state)


def make_hand(pose: str, dx: float = 0.0, dy: float = 0.0, rotate_deg: float = 0.0,
              handedness: str = "Right", noise: float = 0.0, seed: int = 0) -> Hand:
    states = {
        "point": dict(index="ext", middle="curl", ring="curl", pinky="curl", thumb="fold"),
        "open": dict(index="ext", middle="ext", ring="ext", pinky="ext", thumb="ext"),
        "fist": dict(index="curl", middle="curl", ring="curl", pinky="curl", thumb="fist"),
        "two": dict(index="ext", middle="ext", ring="curl", pinky="curl", thumb="fold"),
        "pinch": dict(index="pinch", middle="ext", ring="ext", pinky="ext", thumb="pinch_i"),
        "pinch_closed": dict(index="pinch", middle="curl", ring="curl", pinky="curl", thumb="pinch_i"),
        "middle_pinch": dict(index="ext", middle="pinch", ring="curl", pinky="curl", thumb="pinch_m"),
    }[pose]
    pts = {0: W}
    thumb = {
        "ext": [(0.44, 0.76), (0.40, 0.71), (0.37, 0.66), (0.32, 0.60)],
        "fold": [(0.44, 0.76), (0.42, 0.72), (0.44, 0.68), (0.50, 0.66)],
        "fist": [(0.44, 0.76), (0.42, 0.72), (0.44, 0.67), (0.47, 0.62)],
        "pinch_i": [(0.44, 0.76), (0.40, 0.68), (0.38, 0.58), (0.42, 0.48)],
        "pinch_m": [(0.44, 0.76), (0.42, 0.66), (0.44, 0.54), (0.47, 0.46)],
    }[states["thumb"]]
    for i, p in enumerate(thumb, start=1):
        pts[i] = p
    for fi, name in enumerate(ORDER):
        st = states[name]
        if st == "pinch" and name == "index":
            chain = [MCP[name], (0.43, 0.54), (0.42, 0.50), (0.41, 0.47)]
        elif st == "pinch" and name == "middle":
            chain = [MCP[name], (0.49, 0.52), (0.48, 0.48), (0.47, 0.45)]
        else:
            chain = _finger(MCP[name], st)
        for j, p in enumerate(chain):
            pts[5 + fi * 4 + j] = p
    arr = np.array([[*pts[i], 0.0] for i in range(21)], dtype=np.float32)
    if rotate_deg:
        a = math.radians(rotate_deg)
        c, s = math.cos(a), math.sin(a)
        rel = arr[:, :2] - np.array(W)
        arr[:, :2] = np.stack([rel[:, 0] * c - rel[:, 1] * s, rel[:, 0] * s + rel[:, 1] * c], 1) + np.array(W)
    arr[:, 0] += dx
    arr[:, 1] += dy
    if noise:
        arr[:, :2] += np.random.default_rng(seed).normal(0, noise, (21, 2))
    return Hand(arr, handedness, 0.95)
