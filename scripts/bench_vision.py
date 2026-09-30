"""قياس أداء الرؤية على الجهاز: الكاميرا ← MediaPipe ← محرك الإيماءات، دون تنفيذ أي إجراء.

    python scripts/bench_vision.py [ثوانٍ]

يطبع عدد الإطارات في الثانية، وزمن المعالجة، والوضعيات المكتشفة. لا يُحفظ أي إطار.
"""
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2  # noqa: E402

from config.loader import load_config  # noqa: E402
from core import paths  # noqa: E402
from vision.gestures import GestureEngine  # noqa: E402
from vision.worker import HandTracker, open_camera  # noqa: E402


def main(seconds: float) -> None:
    cfg = load_config().vision
    t = time.monotonic()
    tracker = HandTracker(paths.models_dir() / "mediapipe" / "hand_landmarker.task", cfg)
    print(f"تحميل النموذج: {time.monotonic() - t:.2f}s")
    t = time.monotonic()
    cap = open_camera(cfg)
    ok, frame = cap.read()
    print(f"فتح الكاميرا + أول إطار: {time.monotonic() - t:.2f}s  الدقة: {frame.shape[1]}x{frame.shape[0]}")
    engine = GestureEngine(cfg.tuning, tuple(cfg.control_zone), cfg.hand, frame.shape[1] / frame.shape[0])
    proc, grab, poses, events = [], [], Counter(), Counter()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        t0 = time.monotonic()
        ok, frame = cap.read()
        t1 = time.monotonic()
        if not ok:
            continue
        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        out = engine.update(tracker.detect(rgb, t1), t1)
        proc.append(time.monotonic() - t1)
        grab.append(t1 - t0)
        poses[out.pose] += 1
        events.update(out.events)
    cap.release()
    tracker.close()
    n = len(proc)
    proc.sort()
    print(f"إطارات: {n} ({n / seconds:.1f}/ث)")
    print(f"المعالجة: متوسط {sum(proc) / n * 1000:.0f}ms  p95 {proc[int(n * .95)] * 1000:.0f}ms")
    print(f"انتظار الكاميرا: متوسط {sum(grab) / n * 1000:.0f}ms")
    print("الوضعيات:", dict(poses))
    print("الأحداث:", dict(events))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 10)
