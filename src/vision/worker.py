"""عملية الرؤية: كاميرا ← MediaPipe HandLandmarker ← محرك الإيماءات ← المؤشر.

المؤشر والنقرات تُنفَّذ هنا مباشرة (أقل تأخير)، وبقية الإجراءات تُرسل للرئيسية.
الصور تبقى في الذاكرة فقط ولا تُحفظ أبداً.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from core.events import GestureEvent, HandPreviewEvent, StatusEvent

log = logging.getLogger(__name__)
BLACK_LEVEL = 3.0      # متوسط سطوع أقل من هذا = إطار أسود
BLIND_AFTER_S = 3.0
SLOW_FPS = 10.0        # أقل من هذا لا يصلح للتحكم بالمؤشر
PREVIEW_INTERVAL_S = 1 / 12   # هيكل اليد لمؤشر الحالة: 12 مرة/ث كحد أقصى


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


def camera_api(platform: str | None = None) -> str:
    """واجهة الكاميرا الأصلية لكل نظام (اسم ثابت في cv2)."""
    import sys
    p = platform or sys.platform
    return "CAP_DSHOW" if p == "win32" else "CAP_AVFOUNDATION" if p == "darwin" else "CAP_V4L2"


def open_camera(cfg):
    import cv2
    cap = cv2.VideoCapture(cfg.camera_index, getattr(cv2, camera_api(), cv2.CAP_ANY))
    if not cap.isOpened():
        cap = cv2.VideoCapture(cfg.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"تعذر فتح الكاميرا رقم {cfg.camera_index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # أحدث إطار دائماً ← أقل تأخير
    return cap


def scene_stats(frame, landmarks, aspect: float) -> tuple[float, float, float]:
    """(نسبة الاحتراق، سطوع منطقة اليد، حجم اليد) من صورة مصغّرة. أثناء المعايرة فقط."""
    import cv2
    gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 120),
                      interpolation=cv2.INTER_AREA)
    over = float((gray >= 240).mean())
    if landmarks is None:
        return over, 0.0, 0.0
    xs, ys = landmarks[:, 0], landmarks[:, 1]
    x0, x1 = max(0.0, float(xs.min())), min(1.0, float(xs.max()))
    y0, y1 = max(0.0, float(ys.min())), min(1.0, float(ys.max()))
    size = max((x1 - x0) * aspect, y1 - y0)
    patch = gray[int(y0 * 120):max(int(y1 * 120), int(y0 * 120) + 1),
                 int(x0 * 160):max(int(x1 * 160), int(x0 * 160) + 1)]
    return over, float(patch.mean()) if patch.size else 0.0, float(size)


def calibration_sample(hands, brightness: float, cfg, aspect: float, frame=None):
    from core.events import CalibrationSample
    from vision.gestures import classify
    hand = max(hands, key=lambda h: h.score) if hands else None
    over, hand_b, size = (scene_stats(frame, hand.landmarks if hand else None, aspect)
                          if frame is not None else (0.0, 0.0, 0.0))
    if hand is None:
        return CalibrationSample(False, brightness=brightness, overexposed=over)
    pose = classify(hand, cfg.tuning.pinch_enter, cfg.tuning.pinch_exit, aspect)
    tip = hand.landmarks[8]
    return CalibrationSample(True, pose.pinch_index, float(tip[0]), float(tip[1]), brightness, pose.name,
                             hand_size=size, overexposed=over, hand_brightness=hand_b)


def hand_preview(hands, pose: str) -> HandPreviewEvent:
    """أوضح يد كنقاط (x, y) مقرّبة: حمولة صغيرة لا تحتوي أي صورة."""
    hand = max(hands, key=lambda h: h.score)
    pts = [(round(float(x), 3), round(float(y), 3)) for x, y, _ in hand.landmarks]
    return HandPreviewEvent(pts, pose)


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
    send_preview = cfg_dict.pop("hand_preview", False)   # مؤشر الحالة يرسم اليد
    import cv2

    from config.schema import VisionConfig
    from os_layer.factory import create_backend
    from vision.gestures import GestureEngine
    from vision.idle import ACTIVE, ASLEEP, DOZING, IdleManager
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
    last_hand_seen = 0.0
    last_preview = 0.0
    LOST_GRACE_S = 0.40  # 400ms grace period to eliminate flickering 'hand not visible'
    last_image = time.monotonic()   # آخر إطار فيه صورة فعلية (غير سوداء)
    blind = slow = calibrating = False
    idle = IdleManager(cfg.idle_light_s, cfg.idle_deep_s, time.monotonic())

    def wake_up() -> None:
        """إيقاظ من النوم العميق: إعادة فتح الكاميرا (قد تكون أُخذت من تطبيق آخر أثناء النوم)."""
        nonlocal cap, last_image, frames, busy, last_report
        if cap is None:
            try:
                cap = open_camera(cfg)
            except Exception as e:  # noqa: BLE001
                log.warning("تعذر إعادة فتح الكاميرا بعد النوم: %s", e)
                emit(StatusEvent("vision", "error", str(e)))
                return
        now = time.monotonic()
        last_image, frames, busy, last_report = now, 0, 0.0, now
        if idle.wake(now):
            log.info("الرؤية: استيقاظ")
            emit(StatusEvent("vision", "ready"))

    try:
        while True:
            stop = False
            for msg in link.poll_control():   # EOFError إذا أُغلقت الرئيسية
                if msg.kind == "shutdown":
                    stop = True
                elif msg.kind == "paused":
                    if msg.payload.get("value"):
                        pointer.pause_now()
                        if idle.state == ASLEEP:   # الكف المفتوح يجب أن يستطيع الاستئناف
                            wake_up()
                    else:
                        paused.clear()
                elif msg.kind == "bindings":   # تبديل الملف الشخصي: دون إعادة تشغيل الكاميرا
                    cfg.bindings = dict(msg.payload.get("bindings") or cfg.bindings)
                    cfg.bindings["fist_hold"] = "app.pause"   # القبضة = الإيقاف الطارئ دائماً
                elif msg.kind == "calibrate":
                    calibrating = bool(msg.payload.get("on"))
                    pointer.release()
                    engine.reset()
                    if calibrating:
                        wake_up()
                elif msg.kind == "wake":
                    wake_up()
            if stop:
                break
            if idle.state == ASLEEP:   # الكاميرا محرَّرة: لا قراءة ولا معالجة، فقط رسائل التحكم
                time.sleep(0.2)
                continue
            frame_t = time.monotonic()
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
                emit(calibration_sample(hands, brightness, cfg, aspect, frame))
                continue
            out = engine.update(hands, t0)
            pointer.apply(out, t0)

            change = idle.update(t0, bool(hands), paused.is_set(), calibrating)
            if change == DOZING:
                log.info("الرؤية: سكون خفيف (%.0f إطار/ث)", cfg.light_fps)
                emit(StatusEvent("vision", "dozing"))
            elif change == ASLEEP:
                log.info("الرؤية: نوم عميق، تحرير الكاميرا")
                pointer.release()
                engine.reset()
                hand_visible = False
                cap.release()
                cap = None
                emit(StatusEvent("vision", "asleep"))
                continue
            elif change == ACTIVE:
                frames, busy, last_report = 0, 0.0, t0   # لا "كاميرا بطيئة" بسبب فترة السكون
                emit(StatusEvent("vision", "tracking" if hands else "ready"))

            # حالة رؤية اليد مع فترة سماح لمنع الوميض المزعج
            now_has_hand = bool(hands)
            if now_has_hand:
                last_hand_seen = t0
                if send_preview and t0 - last_preview >= PREVIEW_INTERVAL_S:
                    last_preview = t0
                    emit(hand_preview(hands, out.pose))
                if not hand_visible:
                    hand_visible = True
                    if change != ACTIVE:   # الاستيقاظ أرسل "tracking" مسبقاً
                        emit(StatusEvent("vision", "tracking"))
            else:
                if hand_visible and (t0 - last_hand_seen) >= LOST_GRACE_S:
                    hand_visible = False
                    emit(StatusEvent("vision", "ready"))

            if cfg.preview:
                draw_preview(frame, hands, out, cfg.control_zone)
            if idle.state == DOZING:   # إطارات قليلة: توفير المعالج والبطارية
                time.sleep(max(0.0, 1.0 / cfg.light_fps - (time.monotonic() - frame_t)))
                frames, busy, last_report = 0, 0.0, time.monotonic()
                continue
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
        if cap is not None:
            cap.release()
        tracker.close()
        if cfg.preview:
            cv2.destroyAllWindows()
        try:
            emit(StatusEvent("vision", "stopped"))
        except (EOFError, OSError):
            pass
        link.close()
