"""عملية الرؤية: كاميرا ← MediaPipe HandLandmarker ← محرك الإيماءات ← المؤشر.

المؤشر والنقرات تُنفَّذ هنا مباشرة (أقل تأخير)، وبقية الإجراءات تُرسل للرئيسية.
الصور تبقى في الذاكرة فقط ولا تُحفظ أبداً.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from core.events import GestureEvent, StatusEvent

log = logging.getLogger(__name__)
BLACK_LEVEL = 3.0      # متوسط سطوع أقل من هذا = إطار أسود
BLIND_AFTER_S = 3.0
SLOW_FPS = 10.0        # أقل من هذا لا يصلح للتحكم بالمؤشر


class HandTracker:
    def __init__(self, model_path: Path, cfg):
        from mediapipe.tasks.python import BaseOptions, vision
        if not model_path.exists():
            raise FileNotFoundError(f"نموذج اليد غير موجود: {model_path}")
        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=cfg.min_detection_confidence,
            min_hand_presence_confidence=cfg.min_tracking_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
        )
        self._lm = vision.HandLandmarker.create_from_options(opts)
        self._last_ts = 0

    def detect(self, rgb: np.ndarray, t: float):
        import mediapipe as mp
        from vision.gestures import Hand
        ts = max(int(t * 1000), self._last_ts + 1)  # يجب أن يتزايد بصرامة
        self._last_ts = ts
        res = self._lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
        hands = []
        for lms, hd in zip(res.hand_landmarks, res.handedness):
            arr = np.array([(p.x, p.y, p.z) for p in lms], dtype=np.float32)
            hands.append(Hand(arr, hd[0].category_name, hd[0].score))
        return hands

    def close(self):
        self._lm.close()


def open_camera(cfg):
    import cv2
    cap = cv2.VideoCapture(cfg.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(cfg.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"تعذر فتح الكاميرا رقم {cfg.camera_index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # أحدث إطار دائماً ← أقل تأخير
    return cap


def calibration_sample(hands, brightness: float, cfg, aspect: float):
    from core.events import CalibrationSample
    from vision.gestures import classify
    if not hands:
        return CalibrationSample(False, brightness=brightness)
    hand = max(hands, key=lambda h: h.score)
    pose = classify(hand, cfg.tuning.pinch_enter, cfg.tuning.pinch_exit, aspect)
    tip = hand.landmarks[8]
    return CalibrationSample(True, pose.pinch_index, float(tip[0]), float(tip[1]), brightness, pose.name)


def draw_preview(frame, hands, out, zone):
    import cv2
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = zone
    cv2.rectangle(frame, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (0, 200, 255), 1)
    for hand in hands:
        for x, y, _ in hand.landmarks:
            cv2.circle(frame, (int(x * w), int(y * h)), 3, (0, 255, 0), -1)
    cv2.putText(frame, f"{out.pose} {' '.join(out.events)}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("HADJ No-Touch - camera preview", frame)
    cv2.waitKey(1)


def run(cfg_dict: dict, models_dir: str, address, authkey: bytes) -> None:
    """نقطة دخول العملية الفرعية: تهيئة النموذج والكاميرا أولاً، ثم الاتصال بالرئيسية
    (انظر core/ipc.py لسبب هذا الترتيب)."""
    import threading

    from core import offline_guard
    from core.ipc import Link
    offline_guard.install()
    logging.basicConfig(level=cfg_dict.pop("log_level", "INFO"),
                        format="%(asctime)s [vision] %(levelname)s %(message)s")
    dry_run = cfg_dict.pop("dry_run", False)   # للاختبار: تتبع دون تحريك المؤشر
    import cv2

    from config.schema import VisionConfig
    from os_layer.factory import create_backend
    from vision.gestures import GestureEngine
    from vision.pointer import PointerController

    cfg = VisionConfig.model_validate(cfg_dict)
    backend = create_backend()
    backend.prepare_process()
    error = None
    tracker = cap = None
    try:
        tracker = HandTracker(Path(models_dir) / "mediapipe" / "hand_landmarker.task", cfg)
        cap = open_camera(cfg)
    except Exception as e:  # noqa: BLE001
        log.exception("فشل تشغيل الرؤية")
        error = str(e)

    link = Link(address, authkey, "vision")
    emit = link.send
    if error:
        emit(StatusEvent("vision", "error", error))
        link.close()
        return

    def forward(gesture: str, action: str) -> None:
        emit(GestureEvent(gesture, {"action": action}))

    paused = threading.Event()  # نسخة محلية تُزامَن برسائل "paused" من الرئيسية
    aspect = (cap.get(cv2.CAP_PROP_FRAME_WIDTH) or cfg.width) / (cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or cfg.height)
    engine = GestureEngine(cfg.tuning, tuple(cfg.control_zone), cfg.hand, aspect)
    pointer = PointerController(backend, cfg, forward, paused)
    if dry_run:
        pointer.apply = lambda out, t: None
    emit(StatusEvent("vision", "ready", f"{int(aspect * 100)}"))

    frames, busy, last_report = 0, 0.0, time.monotonic()
    hand_visible = False
    last_image = time.monotonic()   # آخر إطار فيه صورة فعلية (غير سوداء)
    blind = slow = calibrating = False
    try:
        while True:
            stop = False
            for msg in link.poll_control():   # EOFError إذا أُغلقت الرئيسية
                if msg.kind == "shutdown":
                    stop = True
                elif msg.kind == "paused":
                    if msg.payload.get("value"):
                        pointer.pause_now()
                    else:
                        paused.clear()
                elif msg.kind == "calibrate":
                    calibrating = bool(msg.payload.get("on"))
                    pointer.release()
                    engine.reset()
            if stop:
                break
            ok, frame = cap.read()
            now = time.monotonic()
            brightness = float(frame.mean()) if ok else 0.0
            # صورة سوداء أو لا صورة: غطاء الكاميرا مغلق، أو مفتاح تعطيلها، أو تطبيق آخر يستخدمها
            if ok and brightness > BLACK_LEVEL:
                last_image = now
                if blind:
                    blind = False
                    emit(StatusEvent("vision", "ready"))
            elif now - last_image > BLIND_AFTER_S:
                if not blind:
                    blind = True
                    hand_visible = False
                    engine.update([], now + 10)   # إنهاء أي قرص/سحب
                    pointer.release()
                    emit(StatusEvent("vision", "no_image"))
                time.sleep(0.2)
                continue
            if not ok:
                time.sleep(0.05)
                continue
            t0 = now
            frame = cv2.flip(frame, 1)  # صورة مرآة: يمين اليد = يمين الشاشة
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands = tracker.detect(rgb, t0)
            if calibrating:   # المعايرة: أرقام فقط للواجهة، ولا تحكم بالمؤشر
                emit(calibration_sample(hands, brightness, cfg, aspect))
                continue
            out = engine.update(hands, t0)
            pointer.apply(out, t0)
            if bool(hands) != hand_visible:
                hand_visible = bool(hands)
                emit(StatusEvent("vision", "tracking" if hand_visible else "ready"))
            if cfg.preview:
                draw_preview(frame, hands, out, cfg.control_zone)
            frames += 1
            busy += time.monotonic() - t0
            if t0 - last_report > 5:
                fps = frames / (t0 - last_report)
                log.info("الرؤية: %.1f إطار/ث، معالجة %.0f ms/إطار", fps, busy / max(frames, 1) * 1000)
                # كاميرا بطيئة: غالباً تطبيق آخر يستخدمها (متصفح، اجتماع فيديو) أو إضاءة ضعيفة جداً
                if fps < SLOW_FPS and not slow:
                    slow = True
                    emit(StatusEvent("vision", "slow", f"{fps:.0f}"))
                elif fps >= SLOW_FPS and slow:
                    slow = False
                    emit(StatusEvent("vision", "tracking" if hand_visible else "ready"))
                frames, busy, last_report = 0, 0.0, t0
    except (EOFError, OSError):
        log.info("انقطع الاتصال بالعملية الرئيسية؛ خروج")
    finally:
        pointer.release()   # لا يبقى زر فأرة مضغوطاً أبداً
        cap.release()
        tracker.close()
        if cfg.preview:
            cv2.destroyAllWindows()
        try:
            emit(StatusEvent("vision", "stopped"))
        except (EOFError, OSError):
            pass
        link.close()
