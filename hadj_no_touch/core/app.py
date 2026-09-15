"""Application core: wires camera, vision, gestures, voice, AI intent,
Windows control, privacy, profiles, calibration and the UI together.

All heavy work runs on background threads; the Qt UI only consumes status
snapshots and rendered frames via thread-safe signals.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import time
import threading
import re
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..config import SETTINGS
from ..logging_setup import get_logger, setup_logging
from ..database.database import Database
from ..camera.camera_manager import CameraManager, CameraError
from ..vision.hand_tracking import HandTracker, HandData
from ..vision.face_tracking import FaceTracker
from ..vision.gaze_tracking import GazeTracker
from ..gestures import gesture_engine as ge
from ..gestures.gesture_classifier import (
    POINT, PINCH, RIGHT_PINCH, OPEN_PALM, FIST, TWO_FINGER,
)
from ..gestures.custom_gestures import (
    CustomGesture, CustomGestureRematcher, hand_feature,
)
from ..interaction.calibration import CalibrationManager, SCREEN_ANCHORS
from ..interaction.interaction_plane import InteractionPlane
from ..interaction.air_mouse import AirMouse
from ..windows import mouse_control, keyboard_control, window_control, media_control
from ..voice import speech_recognition as sr
from ..voice import voice_commands as vc
from ..ai.context_engine import ContextEngine
from ..ai.intent_engine import IntentEngine, Intent
from ..ai.multimodal_engine import MultimodalEngine
from ..profiles.manager import ProfileManager
from ..privacy.privacy_manager import PrivacyManager
from ..windows.mouse_control import HoldingClick
from ..safety import SafetyEngine, ActionRegistry
from ..demo import DemoMode, DEMO_EXEMPT_ACTIONS
from ..history import ActionHistory, STATUS_OK, STATUS_SIMULATED, STATUS_FAILED
from ..performance import PerformanceMonitor, EnvironmentQuality
from ..macros import MacroRunner, Macro
from ..planner import ActionPlanner
from ..custom_commands import CustomCommandRegistry, CustomCommand
from ..head_tracking import HeadController, head_action_for
from ..test_lab import TestLab
from .status import StatusSnapshot

log = get_logger("core")

# outcomes of routing an Intent, returned by _route_intent so callers can
# decide whether to continue (e.g. macro steps halt on a pending prompt).
OUT_EXECUTED = "executed"
OUT_PENDING = "pending"
OUT_SIMULATED = "simulated"
OUT_BLOCKED = "blocked"
OUT_FAILED = "failed"

try:
    import psutil
    HAVE_PSUTIL = True
except Exception:
    HAVE_PSUTIL = False

try:
    from PIL import ImageGrab  # local screenshot capture
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

# CTRL+ALT+H emergency hotkey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002


class AppCore(QObject):
    status_updated = Signal(object)
    frame_rendered = Signal(object)
    event_logged = Signal(str, str)          # level, message
    voice_heard = Signal(str)                # recognized raw text
    profile_changed = Signal(str)
    intent_raised = Signal(object)           # Intent
    request_confirmation = Signal(object)    # Intent needing confirmation
    toasts = Signal(str)
    emergency_changed = Signal()
    demo_changed = Signal(bool)              # demo mode toggled
    plan_preview = Signal(object)            # ActionPlanner Plan suggestion

    def __init__(self, parent=None):
        super().__init__(parent)
        setup_logging()
        self._ready = threading.Event()

        try:
            from PySide6.QtGui import QImage  # loaded lazily per platform
            self.QImage = QImage
        except Exception:
            self.QImage = None

        self.db = Database()
        self.settings = SETTINGS
        SETTINGS.load()

        self.privacy = PrivacyManager(self.db)
        self.profiles = ProfileManager(self.db)
        self.context_engine = ContextEngine()
        self.intent_engine = IntentEngine()
        self.multimodal = MultimodalEngine()

        # ---- v2.0 engines ---------------------------------------------------
        self.safety = SafetyEngine(ActionRegistry(),
                                   confirmation_level=SETTINGS.safety.confirmation_level)
        self.demo = DemoMode(SETTINGS.demo.start_in_demo)
        self.history = ActionHistory()
        self.perf = PerformanceMonitor()
        self.env_quality = EnvironmentQuality()
        self.env_report = None
        self.head = HeadController(sensitivity=SETTINGS.head.sensitivity,
                                   hold_ms=SETTINGS.head.hold_ms,
                                   cooldown_ms=SETTINGS.head.cooldown_ms)
        self.macros = MacroRunner(executor=self._macro_execute)
        self.custom_commands = CustomCommandRegistry()
        self.planner = ActionPlanner(self.safety.registry)
        self.test_lab = TestLab(self)
        self._load_macros()
        self._load_custom_commands()
        self._last_plan_time = 0.0

        self.calibration = CalibrationManager()
        self._load_calibration()

        self.plane = InteractionPlane(self.calibration, self.settings.cursor)
        try:
            w, h = mouse_control.screen_size()
            self.plane.set_screen_size(w, h)
        except Exception:
            pass
        self.air_mouse = AirMouse(self.plane, self.settings.cursor)

        self.camera = CameraManager(self.settings.camera)
        self.hand_tracker = HandTracker(self.settings.tracking)
        self.face_tracker = FaceTracker()
        self.gaze = GazeTracker()
        # Preload the MediaPipe models eagerly on background threads:
        # the first frame never pays the load cost, and a slow/frozen
        # model init can never stall startup (the window shows instantly).
        def _preload_hands() -> None:
            try:
                self.hand_tracker._ensure_model()
            except Exception as e:
                log.warning("eager hand model preload failed: %s", e)

        threading.Thread(target=_preload_hands, name="hadj-model-preload",
                         daemon=True).start()

        if self.settings.tracking.gaze_enabled or self.settings.head.enabled:
            def _preload_face() -> None:
                try:
                    self.face_tracker._ensure_model()
                except Exception as e:
                    log.warning("eager face model preload failed: %s", e)

            threading.Thread(target=_preload_face, name="hadj-face-preload",
                             daemon=True).start()

        self.engine = ge.GestureEngine(self.settings.gestures, on_event=self._engine_event_tap)

        self.voice = sr.SpeechManager(self.settings.voice, on_text=self._on_voice_text)
        self._dictating = False

        self.holder = HoldingClick()

        self._custom = []
        self._rematcher = CustomGestureRematcher([])
        self._load_custom_gestures()

        self._thread: Optional[threading.Thread] = None
        self._hotkey_thread: Optional[threading.Thread] = None
        self._running = threading.Event()

        self._pending_confirm: Optional[Intent] = None
        self._pending_confirm_at = 0.0

        self._last_context_time = 0.0
        self._last_preview_time = 0.0
        self._last_status_time = 0.0
        self._frame_index = 0
        self._processing_fps = 0.0
        self._status = StatusSnapshot()
        self._context_cache = self.context_engine.snapshot()
        self.camera_error_hint = ""

        self.calibration_active = False  # flipped by the calibration wizard

        ctypes.windll.user32.SetProcessDPIAware()

    # =====================================================================
    # lifecycle
    # =====================================================================
    def start(self) -> bool:
        self._running.set()
        cam_ok = self.camera.start()
        if not cam_ok:
            self.camera_error_hint = self.camera.error or "camera unavailable"
            self._event("WARN", f"Camera unavailable: {self.camera_error_hint}")
        self._thread = threading.Thread(target=self._processing_loop, name="hadj-processing",
                                        daemon=True)
        self._thread.start()
        self._start_hotkey_listener()
        self._start_voice()
        self._ready.set()
        self._event("INFO", f"Started. Profile: {self.profiles.active.name}")
        return True

    def stop(self) -> None:
        self._running.clear()
        self.voice.stop()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._stop_hotkey_listener()
        self.camera.stop()
        self.hand_tracker.close()
        self.face_tracker.close()
        self._event("INFO", "Stopped")

    # =====================================================================
    # main processing loop
    # =====================================================================
    def _processing_loop(self) -> None:
        target_interval = 1.0 / max(1, self.settings.tracking.processing_fps)
        self._last_tick_time = time.monotonic()
        _last_err = 0.0
        while self._running.is_set():
            t0 = time.monotonic()
            try:
                self._process_tick()
            except Exception:
                # A single bad frame must never kill the loop silently: the UI
                # would freeze on its last state (gray dots, stuck FPS). Log the
                # traceback (throttled) and keep going.
                if time.monotonic() - _last_err > 5.0:
                    _last_err = time.monotonic()
                    log.exception("processing tick failed")
                time.sleep(0.05)
            now = time.monotonic()
            dt = now - self._last_tick_time
            self._last_tick_time = now
            if dt > 0:
                self._processing_fps = 0.9 * self._processing_fps + 0.1 * (1.0 / dt)
            elapsed = now - t0
            sleep = target_interval - elapsed
            if sleep > 0:
                time.sleep(min(sleep, 0.05))

    def _process_tick(self) -> None:
        tick0 = time.monotonic()
        frame_obj = None
        try:
            frame_obj = self.camera.read()
        except Exception:
            frame_obj = None
        now = time.monotonic()

        self._sd_emit(now)  # keep the dashboard live even with no camera frame
        if frame_obj is None:
            self.perf.note_frame((time.monotonic() - tick0) * 1000.0)
            time.sleep(0.01)
            return

        if hasattr(self, "_last_processed_frame_index") and self._last_processed_frame_index == frame_obj.index:
            time.sleep(0.005)
            return
        self._last_processed_frame_index = frame_obj.index

        frame = frame_obj.bgr
        w = h = 0
        if frame is not None:
            h, w = frame.shape[:2]
        now = time.monotonic()
        fps = self.camera.fps if hasattr(self.camera, "fps") else self._processing_fps

        hand: Optional[HandData] = None
        hands: list = []
        pointer_norm = None
        pointer = None

        if frame is not None and not self.privacy.privacy_mode:
            hands = self.hand_tracker.detect(frame, w, h)
            if hands:
                hand = self._choose_hand(hands)
        self._last_hand_detected = hand is not None

        # fingertip → virtual interaction plane
        if hand is not None and self.settings.cursor.enabled:
            fingertip = (float(hand.landmarks_norm[8][0]), float(hand.landmarks_norm[8][1]))
            pointer = self.air_mouse.compute(fingertip)
            pointer_norm = fingertip

        privacy_ok = self.privacy.can_act()
        events = []
        if frame is not None:
            events = self.engine.update(hands if privacy_ok else [],
                                        pointer if privacy_ok else None, w, h)

        for ev in events:
            self._dispatch_gesture_event(ev)

        # custom gesture matching
        if hand is not None and privacy_ok and self._rematcher.gestures:
            self._rematcher.push(hand_feature(hand.landmarks_norm))
            match, _dist, conf = self._rematcher.match()
            if match and conf >= 0.55:
                self._fire_custom_gesture(match)
                self._rematcher.clear()
        elif self._rematcher.gestures:
            self._rematcher.clear()

        # optional gaze + head control (share one FaceMesh detection)
        gaze_active = self.settings.tracking.gaze_enabled
        head_enabled = self.settings.head.enabled
        face_needed = gaze_active or head_enabled
        if not face_needed and self.multimodal.state.gaze_active:
            self.gaze.active = False
            self.multimodal.set_gaze(0.0, 0.0, False)
        if face_needed and frame is not None and \
                (self._frame_index % self.settings.tracking.gaze_every_n_frames == 0):
            face = self.face_tracker.detect(frame, w, h)
            if face.present:
                if gaze_active:
                    self.gaze.update(face)
                    gx, gy = self.gaze.direction()
                    self.multimodal.set_gaze(gx, gy, True)
                if head_enabled:
                    hev = self.head.update(face.landmarks_norm)
                    if hev is not None:
                        action = head_action_for(self._context_cache.category,
                                                 hev.direction)
                        if action:
                            intent = Intent(action=action, source="head",
                                            params={"head": hev.direction,
                                                    "confidence": hev.confidence},
                                            description=hev.describe())
                            self._route_intent(intent)
            else:
                if gaze_active:
                    self.gaze.active = False
                    self.multimodal.set_gaze(0.0, 0.0, False)
                if head_enabled and hasattr(self, "head"):
                    self.head.update(None)
        self.multimodal.set_pointer(pointer_norm[0] if pointer_norm else 0.5,
                                    pointer_norm[1] if pointer_norm else 0.5,
                                    pointer_norm is not None)

        # context throttling (1 Hz)
        if now - self._last_context_time > 1.0:
            self._last_context_time = now
            self._refresh_context()

        # preview + status throttled to ~20 Hz
        if now - self._last_preview_time > 0.05:
            self._last_preview_time = now
            if frame is not None and self.QImage is not None and not self.privacy.privacy_mode:
                import cv2
                overlay = self._overlay(frame, hand, w, h)
                rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
                qimg = self.QImage(rgb.data, w, h, 3 * w, self.QImage.Format.Format_RGB888).copy()
                self.frame_rendered.emit(qimg)

        self._sd_emit(now)

        # latent memory of confirm requests expiring
        if self._pending_confirm and now - self._pending_confirm_at > 20:
            self._pending_confirm = None

        # lighting / environment estimate (every ~90 frames ≈ 3 s)
        if frame is not None and self._frame_index % 90 == 0:
            self.env_report = self.env_quality.estimate(frame)

        self.perf.note_frame((time.monotonic() - tick0) * 1000.0)
        self._frame_index += 1
        _ = fps

    # =====================================================================
    # hand selection / overlay
    # =====================================================================
    def _choose_hand(self, hands: list[HandData]) -> Optional[HandData]:
        if len(hands) == 1:
            return hands[0]
        left = [h for h in hands if h.handedness == "Left"]
        right = [h for h in hands if h.handedness != "Left"]
        prefer_left = self.settings.cursor.left_handed
        group = left if prefer_left else right
        return (group or left or right)[0]

    def _overlay(self, frame, hand, w, h):
        try:
            import cv2
            view = frame.copy()
            if hand is not None:
                pts = hand.landmarks_px.astype(int)
                for i, j in ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7),
                             (7, 8), (5, 9), (9, 10), (10, 11), (11, 12), (9, 13),
                             (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
                             (18, 19), (19, 20)):
                    cv2.line(view, tuple(pts[i]), tuple(pts[j]), (0, 200, 255), 1)
                idx = tuple(pts[8])
                cv2.circle(view, idx, 6, (0, 230, 120), -1)
            g = self.engine.confirmed_gesture
            if self.engine.locked:
                g = "LOCKED"
            cv2.putText(view, f"{g} {self.engine.raw_confidence:.0%}",
                        (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 120), 2)
            if self.engine.paused:
                cv2.putText(view, "PAUSED", (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 120, 255), 2)
            if self.privacy.privacy_mode:
                view = cv2.GaussianBlur(view, (25, 25), 12)
            return view
        except Exception:
            return frame

    # =====================================================================
    # gesture / intent dispatch
    # =====================================================================
    def _dispatch_gesture_event(self, ev: ge.GestureEvent) -> None:
        self.multimodal.on_gesture(ev)
        if not self.privacy.can_act():
            return
        mouse_events = {ge.MOVE, ge.DRAG_UPDATE, ge.LEFT_CLICK, ge.DOUBLE_CLICK,
                        ge.RIGHT_CLICK, ge.DRAG_START, ge.DRAG_END, ge.SCROLL_V,
                        ge.SCROLL_H}
        if ev.kind in mouse_events:
            self._execute_mouse_event(ev)
            return
        # a gesture can trigger a user-defined macro before normal handling
        macro = self.macros.find_gesture(ev.kind)
        if macro is not None:
            self.perf.note_command()
            self.history.record(source="macro",
                                action=f"Gesture macro '{macro.name}'",
                                status=STATUS_OK)
            self.toasts.emit(self.demo.simulate(f"macro '{macro.name}'") if self.demo.enabled
                             else f"Running macro '{macro.name}'")
            self._event("MACRO", f"Gesture trigger '{ev.kind}' → {macro.name}")
            self.macros.run(macro)
            return
        # symbolic gesture → intentional, context-aware action
        intent = self.intent_engine.from_gesture(ev, self._context_cache)
        if intent is not None:
            intent = self.intent_engine.remap_for_profile(intent,
                                                          self.profiles.active.gesture_map)
            if intent.action == "NOOP":
                return
            self._route_intent(intent)

    def _execute_mouse_event(self, ev: ge.GestureEvent) -> None:
        if self.demo.enabled:
            label = ev.kind
            if ev.x or ev.y:
                label += f" @{int(ev.x)},{int(ev.y)}"
            if ev.kind in (ge.MOVE, ge.DRAG_UPDATE) and self._frame_index % 30 != 0:
                return
            self.history.record(source="gesture", action=label,
                                status=STATUS_SIMULATED, simulated=True)
            self.toasts.emit(self.demo.simulate(label))
            self._event("DEMO", f"Simulated gesture: {label}")
            return
        x, y = int(ev.x), int(ev.y)
        if ev.kind == ge.MOVE:
            self.air_mouse.apply()
            return
        if ev.kind == ge.DRAG_UPDATE:
            if self.holder.active:
                self.air_mouse.apply()
            return
        if ev.kind == ge.DRAG_START:
            mouse_control.move_to(x, y)
            self.holder.start()
            self._log_mouse("DRAG START", ev.kind)
            return
        if ev.kind == ge.DRAG_END:
            self.holder.stop()
            self._log_mouse("DRAG END", ev.kind)
            return
        if ev.kind == ge.LEFT_CLICK:
            if not self._gaze_gate_ok():
                return
            mouse_control.click_left(x, y)
            self.holder.stop()
            self._log_mouse(f"LEFT CLICK @{x},{y}", ev.kind)
            return
        if ev.kind == ge.DOUBLE_CLICK:
            if not self._gaze_gate_ok():
                return
            mouse_control.double_click(x, y)
            self.holder.stop()
            self._log_mouse("DOUBLE CLICK", ev.kind)
            return
        if ev.kind == ge.RIGHT_CLICK:
            mouse_control.click_right(x, y)
            self._log_mouse("RIGHT CLICK", ev.kind)
            return
        if ev.kind == ge.SCROLL_V:
            mouse_control.scroll(ev.amount)
            self._log_mouse(f"SCROLL V {ev.amount:+d}", ev.kind)
            return
        if ev.kind == ge.SCROLL_H:
            mouse_control.scroll(ev.amount, horizontal=True)
            self._log_mouse(f"SCROLL H {ev.amount:+d}", ev.kind)

    def _log_mouse(self, label: str, kind: str) -> None:
        self.history.record(source="gesture", action=label, status=STATUS_OK)
        self.perf.note_command()
        self._action_note(label)

    def _gaze_gate_ok(self) -> bool:
        if not (self.settings.cursor.gaze_gate_clicks and self.multimodal.state.gaze_active):
            return True
        return self.multimodal.state.gaze_pointer_match >= 0.55

    # ---- intent routing ------------------------------------------------
    def _route_intent(self, intent: Intent) -> str:
        if self.demo.enabled and intent.action not in DEMO_EXEMPT_ACTIONS:
            label = intent.describe() or intent.action
            self.history.record(source=intent.source, action=label,
                                params=intent.params,
                                status=STATUS_SIMULATED, simulated=True)
            self.toasts.emit(self.demo.simulate(label))
            self._event("DEMO", f"Simulated action: {intent.action}")
            self.intent_raised.emit(intent)
            return OUT_SIMULATED
        if not self._can_execute():
            self.safety.audit(intent.action, "BLOCKED", "control disabled")
            return OUT_BLOCKED
        decision = self.safety.decide(intent.action, intent.needs_confirmation)
        if decision.requires_confirmation:
            self.safety.audit(intent.action, "CONFIRMING", decision.reason)
            self._pending_confirm = intent
            self._pending_confirm_at = time.monotonic()
            self.request_confirmation.emit(intent)
            return OUT_PENDING
        return self._execute_routed(intent)

    def _execute_routed(self, intent: Intent) -> str:
        if intent.action == "COPILOT":
            self.intent_raised.emit(intent)
            self._event("COPILOT", intent.params.get("hint", "copilot suggestion"))
            return OUT_EXECUTED
        ok = self._execute_intent(intent)
        self.safety.audit(intent.action, "OK" if ok else "FAILED", intent.describe())
        if ok:
            self.history.record(source=intent.source,
                                action=intent.describe() or intent.action,
                                params=intent.params, status=STATUS_OK)
            self.intent_raised.emit(intent)
            self._event("ACTION", intent.describe())
            self.perf.note_command()
            self._action_note(intent.describe())
            return OUT_EXECUTED
        self.history.record(source=intent.source, action=intent.action,
                            params=intent.params, status=STATUS_FAILED)
        return OUT_FAILED

    def _macro_execute(self, intent: Intent) -> bool:
        """Run one macro step through the normal gates.

        Returns False (halting the macro) when the step needs a user prompt,
        is blocked, or failed -- so a confirmation never races ahead of the
        rest of the macro sequence.
        """
        outcome = self._route_intent(intent)
        return outcome in (OUT_EXECUTED, OUT_SIMULATED)

    def confirm_pending(self) -> None:
        if self._pending_confirm:
            intent = self._pending_confirm
            self._pending_confirm = None
            self.safety.audit(intent.action, "CONFIRMED", "user accepted prompt")
            self._execute_routed(intent)

    def reject_pending(self) -> None:
        if self._pending_confirm:
            self.safety.audit(self._pending_confirm.action, "REJECTED",
                              "user declined prompt")
        self._pending_confirm = None
        self._pending_confirm_at = 0.0

    def _execute_intent(self, intent: Intent) -> bool:
        a = intent.action
        p = intent.params
        try:
            if a == "SCROLL":
                amount = 3 * p.get("direction", 1)
                mouse_control.scroll(int(amount))
            elif a in ("NEXT_SLIDE", "NEXT_PAGE", "NEXT_IMAGE", "NEXT_DIAGNOSTIC"):
                keyboard_control.tap("PGDN")
            elif a in ("PREV_SLIDE", "PREV_PAGE", "PREV_IMAGE", "PREV_DIAGNOSTIC"):
                keyboard_control.tap("PGUP")
            elif a == "START_PRESENTATION":
                keyboard_control.tap("F5")
            elif a == "END_PRESENTATION":
                keyboard_control.tap("ESC")
            elif a == "BLACK_SCREEN":
                keyboard_control.tap("B")
            elif a == "PAUSE_PRESENTATION":
                keyboard_control.tap("B")
            elif a == "GO_BACK":
                keyboard_control.tap("LEFT", ["ALT"])
            elif a == "GO_FORWARD":
                keyboard_control.tap("RIGHT", ["ALT"])
            elif a == "NEXT_TAB":
                keyboard_control.tap("TAB", ["CTRL"])
            elif a == "PREV_TAB":
                keyboard_control.tap("TAB", ["CTRL", "SHIFT"])
            elif a == "CLOSE_TAB":
                keyboard_control.tap("W", ["CTRL"])
            elif a == "NEW_TAB":
                keyboard_control.tap("T", ["CTRL"])
            elif a == "REFRESH":
                keyboard_control.tap("F5")
            elif a == "FIND":
                keyboard_control.tap("F", ["CTRL"])
            elif a == "ZOOM_IN":
                keyboard_control.tap("=", ["CTRL"])
            elif a == "ZOOM_OUT":
                keyboard_control.tap("-", ["CTRL"])
            elif a == "ROTATE_3D":
                key = "E" if p.get("direction") in (None, 1) else "Q"
                keyboard_control.tap(key)
            elif a == "VOLUME_UP":
                media_control.volume_up(p.get("steps", 1))
                self.toasts.emit(media_control.volume_status())
            elif a == "VOLUME_DOWN":
                media_control.volume_down(p.get("steps", 1))
                self.toasts.emit(media_control.volume_status())
            elif a == "VOLUME_SET":
                media_control.set_volume_percent(p.get("percent", 50))
                self.toasts.emit(media_control.volume_status())
            elif a == "MUTE":
                media_control.mute()
            elif a == "UNMUTE":
                media_control.mute()
            elif a == "PLAY_PAUSE":
                media_control.play_pause()
            elif a == "NEXT_TRACK":
                media_control.next_track()
            elif a == "PREV_TRACK":
                media_control.prev_track()
            elif a == "STOP_MEDIA":
                media_control.stop_media()
            elif a == "COPY":
                keyboard_control.tap("C", ["CTRL"])
            elif a == "PASTE":
                keyboard_control.tap("V", ["CTRL"])
            elif a == "CUT":
                keyboard_control.tap("X", ["CTRL"])
            elif a == "UNDO":
                keyboard_control.tap("Z", ["CTRL"])
            elif a == "SELECT_ALL":
                keyboard_control.tap("A", ["CTRL"])
            elif a == "PRESS_ENTER":
                keyboard_control.tap("ENTER")
            elif a == "TAB_KEY":
                keyboard_control.tap("TAB")
            elif a == "TYPE_TEXT":
                keyboard_control.type_text(str(p.get("text", "")))
            elif a == "SCREENSHOT":
                return self._screenshot()
            elif a == "OPEN_APP":
                return self._open_app(str(p.get("app", "")))
            elif a == "OPEN_SETTINGS":
                window_control.launch_app("settings")
            elif a == "CLOSE_WINDOW":
                window_control.close_active_window()
            elif a == "MINIMIZE":
                window_control.minimize_active()
            elif a == "MAXIMIZE":
                window_control.maximize_active()
            elif a == "SWITCH_WINDOW":
                window_control.switch_window()
            elif a == "SHOW_DESKTOP":
                keyboard_control.tap("D", ["WIN"])
            elif a == "PAUSE_CONTROL":
                self.pause_tracking(True)
            elif a == "RESUME_CONTROL":
                self.pause_tracking(False)
            elif a == "EMERGENCY_STOP":
                self.emergency_stop()
            elif a == "HANDS_BUSY_ON":
                self.profiles.set_active("hands_busy")
                self.profile_changed.emit("hands_busy")
                self._safety_note("Hands Busy mode ON")
            elif a == "HANDS_BUSY_OFF":
                self.profiles.set_active("personal")
                self.profile_changed.emit("personal")
                self._safety_note("Hands Busy mode OFF")
            elif a == "CALIBRATE":
                self.toasts.emit("Open Calibration from the dashboard")
            elif a == "TOGGLE_KEYBOARD":
                self.toasts.emit("Virtual keyboard — use the dashboard button")
            elif a == "SHOW_UI":
                self.toasts.emit("Main interface is already visible")
            elif a == "HIDE_UI":
                self.toasts.emit("Use the tray to show the interface again")
            elif a == "HELP":
                self.toasts.emit("Say 'open chrome', 'volume 50 percent', 'close this window'…")
            elif a == "PROFILE_SWITCH":
                pid = p.get("profile", "personal")
                self.profiles.set_active(pid)
                self.profile_changed.emit(pid)
            elif a == "PAUSE_INTERACTION":
                self.engine.pause()
                threading.Timer(1.5, self.engine.resume).start()
            elif a == "FIST_LOCK":
                self._safety_note("Interaction lock toggled")
            else:
                return False
            return True
        except Exception as e:
            log.error("execute intent %s failed: %s", a, e)
            self._event("ERROR", f"Failed: {a} ({e})")
            return False

    # private helpers -----------------------------------------------------
    def _open_app(self, app: str) -> bool:
        normalized = app.lower().strip()
        aliases = {
            "chrome browser": "chrome", "browser": "chrome", "google chrome": "chrome",
            "microsoft edge": "edge", "edge browser": "edge",
            "text editor": "notepad", "notepad plus plus": "notepad",
            "excel": "excel", "word": "word", "powerpoint": "powerpoint",
            "file explorer": "explorer", "explorer": "explorer", "files": "explorer",
            "my computer": "explorer", "this pc": "explorer",
            "photo viewer": "paint",
        }
        app = aliases.get(normalized, normalized)
        if app in ("settings", "windows settings"):
            self._execute_intent(Intent(action="OPEN_SETTINGS"))
            return True
        ok = window_control.launch_app(app)
        if not ok:
            self._event("WARN", f"Could not find application '{app}'")
        return ok

    def _screenshot(self) -> bool:
        if not HAVE_PIL:
            self._event("WARN", "screenshot requires Pillow (not installed)")
            return False
        try:
            from PIL import Image
            shots = ImageGrab.grab()
            import os
            folder = os.path.join(os.environ.get("USERPROFILE", "."),
                                  "Pictures", "HADJNoTouchAI")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, time.strftime("shot_%Y%m%d_%H%M%S.png"))
            shots.save(path)
            shots.close()
            self._event("ACTION", f"Screenshot saved: {path}")
            self.toasts.emit("Screenshot saved locally")
            return True
        except Exception as e:
            self._event("ERROR", f"screenshot failed: {e}")
            return False

    def _fire_custom_gesture(self, gesture: CustomGesture) -> None:
        if not self._can_execute():
            return
        action = gesture.action or ""
        name, _, value = action.partition(":")
        name = name.strip().lower()
        self._event("GESTURE", f"Custom gesture '{gesture.name}' → {action or 'assigned action'}")
        if name == "launch_app":
            self._open_app(value)
        elif name == "type_text":
            keyboard_control.type_text(value)
        elif name == "open_profile":
            self.profiles.set_active(value.strip())
            self.profile_changed.emit(value.strip())
        elif name == "open_document":
            self._open_documents(value)
        elif name == "screenshot":
            self._screenshot()
        elif name:
            intent = Intent(action=name.upper(), params={}, source="custom")
            self._execute_intent(intent)

    def _open_documents(self, kind: str = "") -> None:
        import os
        folder = os.path.join(os.environ.get("USERPROFILE", "."), "Documents")
        subprocess = __import__("subprocess")
        subprocess.Popen(["explorer.exe", folder])

    # =====================================================================
    # voice
    # =====================================================================
    def start_listening(self) -> bool:
        return bool(self.voice and self.voice.start())

    def stop_listening(self) -> None:
        if self.voice:
            self.voice.stop()

    def _on_voice_text(self, text: str) -> None:
        self.voice_heard.emit(text)
        if self._dictating:
            keyboard_control.type_text(text + " ")
            self.toasts.emit(f"Dictated: {text}")
            return
        vi = vc.parse(text, self.settings.voice.language)
        if vi.intent == vc.NONE_INTENT:
            self._voice_fallback(text, vi.language)
            return
        self.multimodal.on_voice(vi)
        intent = self.intent_engine.from_voice(vi, self._context_cache)
        if intent is None:
            self._event("VOICE", f"Heard (unmapped): {text}")
            return
        # allow the active profile to override voice intent routing
        vm = self.profiles.active.voice_map
        if vm and vi.intent in vm:
            intent = Intent(action=vm[vi.intent], params=dict(intent.params),
                            confidence=intent.confidence, source="voice",
                            description=vm[vi.intent])
        if intent.action in ("EMERGENCY_STOP", "PAUSE_CONTROL", "RESUME_CONTROL",
                             "HANDS_BUSY_ON", "HANDS_BUSY_OFF"):
            intent.needs_confirmation = False
        if intent.action in ("CLOSE_WINDOW", "CLOSE_TAB"):
            intent = self.multimodal.copilot_assess(vi, self._context_cache, intent)
        elif intent.action == "COPILOT":
            intent = self.multimodal.copilot_assess(vi, self._context_cache, None)
        self._route_intent(intent)

    def set_dictation(self, on: bool) -> None:
        self._dictating = on
        self._event("INFO", f"dictation {'on' if on else 'off'}")

    def _voice_fallback(self, text: str, language: str) -> None:
        """Phrase wasn't a built-in command: try custom commands, macros,
        then surface an AI plan suggestion (no execution)."""
        cc = self.custom_commands.match(text, language)
        if cc is not None:
            intent = Intent(action=cc.action, params=dict(cc.params), source="custom",
                            description=f"Custom command '{cc.phrase}' → {cc.action}")
            self._event("VOICE", f"Custom command: {text} → {cc.action}")
            self._route_intent(intent)
            return
        macro = self.macros.find_voice(text)
        if macro is not None:
            self.perf.note_command()
            self.history.record(source="macro",
                                action=f"Voice macro '{macro.name}'",
                                status=STATUS_OK)
            self._event("VOICE", f"Macro triggered: {text} → {macro.name}")
            self.toasts.emit(self.demo.simulate(f"macro '{macro.name}'") if self.demo.enabled
                             else f"Running macro '{macro.name}'")
            self.macros.run(macro)
            return
        now = time.monotonic()
        if now - self._last_plan_time > 5.0:
            self._last_plan_time = now
            plan = self.planner.plan(text)
            if not plan.is_empty():
                self.plan_preview.emit(plan)
                self._event("INFO", f"AI plan suggested: {plan.description}")
        self._event("VOICE", f"Heard (no command): {text}")

    # =====================================================================
    # controls / privacy
    # =====================================================================
    def _can_execute(self) -> bool:
        return self.privacy.can_act()

    def toggle_camera(self) -> None:
        next_state = not self.privacy.camera_enabled
        self.privacy.set_camera(next_state)
        if not next_state:
            self.camera.stop()
        else:
            self.camera.start()
        self._status_changed("camera")

    def toggle_mic(self) -> None:
        next_state = not self.privacy.mic_enabled
        self.privacy.set_mic(next_state)
        if next_state:
            self.start_listening()
        else:
            self.stop_listening()
        self._status_changed("mic")

    def pause_tracking(self, paused: bool) -> None:
        self.privacy.set_paused(paused)
        if paused:
            self.engine.pause()
        else:
            self.engine.resume()
        self._status_changed("pause")

    def toggle_privacy_mode(self) -> None:
        self.privacy.set_privacy_mode(not self.privacy.privacy_mode)
        self._status_changed("privacy")

    def emergency_stop(self) -> None:
        self.privacy.emergency_stop()
        self.engine.pause()
        self.engine.locked = True
        self.holder.stop()
        self.air_mouse.reset()
        self.emergency_changed.emit()
        self._event("WARN", "EMERGENCY STOP — control disabled (CTRL+ALT+H)")

    def resume_from_emergency(self) -> None:
        self.privacy.resume_control()
        self.engine.resume()
        self.engine.locked = False
        self.emergency_changed.emit()
        self._event("INFO", "Control re-enabled")

    def clear_user_data(self) -> None:
        self.privacy.clear_all_user_data()
        try:
            self.settings.save()
        except Exception:
            pass
        self.toasts.emit("Local data cleared")

    # hotkey ---------------------------------------------------------------
    def _start_hotkey_listener(self) -> None:
        self._hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True,
                                               name="hotkey")
        self._hotkey_thread.start()

    def _hotkey_loop(self) -> None:
        try:
            user32 = ctypes.windll.user32
            hwnd = ctypes.windll.kernel32.GetModuleHandleW(None)
            if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT, 0x48):
                log.warning("RegisterHotKey failed; CTRL+ALT+H unavailable")
                return
        except Exception as e:
            log.warning("hotkey register error: %s", e)
            return
        msg = ctypes.wintypes.MSG()
        WM_HOTKEY = 0x0312
        while self._running.is_set():
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == 1:
                self.emergency_stop()
        ctypes.windll.user32.UnregisterHotKey(None, 1)

    def _stop_hotkey_listener(self) -> None:
        pass  # thread exits when loop stops

    def _start_voice(self) -> None:
        if not self.settings.voice.enabled:
            self._event("INFO", "Voice recognition disabled in settings")
            return
        try:
            ok = self.voice.start()
            if ok:
                self._event("INFO", "Voice recognition ready")
            else:
                eng = self.voice.engine
                detail = eng.error if eng and eng.error else "engine unavailable"
                log.warning("start voice: %s", detail)
                self._event("WARN", f"Voice recognition unavailable: {detail}")
        except Exception as e:
            log.warning("start voice error: %s", e)
            self._event("WARN", f"Voice recognition start failed: {e}")

    # =====================================================================
    # calibration (used by the wizard)
    # =====================================================================
    def start_calibration(self) -> None:
        self.calibration.reset()
        self.calibration_active = True
        self._event("INFO", "Calibration started")

    def calibration_tick(self) -> int:
        """Feed the current fingertip into the calibration manager.
        Returns the current stage (0..5)."""
        if not self.calibration_active:
            return self.calibration.stage
        hand = None
        if hasattr(self, "_last_hand"):
            hand = self._last_hand
        # recompute hand from latest frame for accuracy
        frame_obj = self.camera.read()
        fingertip = None
        pinch = False
        if frame_obj is not None:
            h, w = frame_obj.bgr.shape[:2]
            if not self.privacy.privacy_mode:
                hands = self.hand_tracker.detect(frame_obj.bgr, w, h)
                if hands:
                    hand = self._choose_hand(hands)
                    self._last_hand = hand
        if hand is not None:
            fingertip = (float(hand.landmarks_norm[8][0]), float(hand.landmarks_norm[8][1]))
            res = self.engine.classifier.classify(hand)
            pinch = res.name == PINCH and res.confidence > 0.6
        if fingertip:
            self.calibration.collect(fingertip, pinch)
        return self.calibration.stage

    def confirm_calibration_point(self) -> None:
        hand = getattr(self, "_last_hand", None)
        if hand is not None:
            ft = (float(hand.landmarks_norm[8][0]), float(hand.landmarks_norm[8][1]))
            self.calibration.confirm_point(ft)
        elif not self.calibration.points_camera:
            self.calibration.confirm_point((0.5, 0.5))
        if self.calibration.done:
            self._finish_calibration()

    def cancel_calibration(self) -> None:
        self.calibration.reset()
        self.calibration_active = False

    def _finish_calibration(self) -> None:
        self.calibration_active = False
        self._save_calibration()
        # verify: current fingertip should map near center marker position
        self._event("INFO", "Calibration complete — test your cursor")
        self.toasts.emit("Calibration saved. Move your finger to test.")

    def _save_calibration(self) -> None:
        if not self.calibration.points_camera:
            return
        h = self.calibration.homography
        h_list = h.reshape(-1).tolist() if h is not None else None
        self.db.save_calibration(self.calibration.points_camera, h_list)

    def _load_calibration(self) -> None:
        rec = self.db.latest_calibration()
        if rec and rec.get("points") and len(rec["points"]) >= 4:
            self.calibration.points_camera = [tuple(p) for p in rec["points"]]
            self.calibration.stage = 5
            self.calibration.calibrated = True
            if rec.get("homography"):
                try:
                    arr = np.array(rec["homography"], dtype=np.float32).reshape(3, 3)
                    self.calibration.homography = arr
                except Exception:
                    self.calibration._try_build(silent=True)

    def clear_calibration(self) -> None:
        self.db.clear_calibrations()
        self.calibration.reset()
        self._event("INFO", "Calibration cleared — using fallback mapping")

    # custom gestures -----------------------------------------------------
    def record_custom_gesture_sample(self, name: str) -> list:
        """Record a sample over ~1.2s using the live hand path."""
        path: list[np.ndarray] = []
        start = time.monotonic()
        frame_obj = self.camera.read()
        while time.monotonic() - start < 1.2:
            fobj = self.camera.read()
            if fobj is not None:
                h, w = fobj.bgr.shape[:2]
                hands = self.hand_tracker.detect(fobj.bgr, w, h)
                if hands:
                    path.append(hand_feature(hands[0].landmarks_norm))
            time.sleep(0.03)
        if len(path) < 6:
            return []
        return [path]

    def save_custom_gesture(self, name: str, action: str,
                            samples: list[list[np.ndarray]]) -> None:
        from ..gestures.custom_gestures import resample_path
        gesture = CustomGesture(name=name, action=action, action_label=action)
        for path in samples:
            gesture.add_sample(path)
        self.db.save_custom_gesture(name, action, action,
                                    gesture.to_db()["templates"])
        self._load_custom_gestures()
        self._event("INFO", f"Custom gesture '{name}' saved → {action}")

    def _load_custom_gestures(self) -> None:
        rows = self.db.load_custom_gestures()
        gestures = []
        for r in rows:
            try:
                g = CustomGesture.from_db(r)
                valid = all(isinstance(t, np.ndarray) and t.shape == (24, 42)
                            for t in g.templates)
                if not valid:
                    log.warning("custom gesture %s template size mismatch", r["name"])
                gestures.append(g)
            except Exception as e:
                log.warning("custom gesture load failed: %s", e)
        self._custom = gestures
        self._rematcher = CustomGestureRematcher(gestures)

    def delete_custom_gesture(self, name: str) -> None:
        self.db.delete_custom_gesture(name)
        self._load_custom_gestures()

    def list_custom_gestures(self) -> list[dict]:
        return [{"name": g.name, "action": g.action_label} for g in self._custom]

    # =====================================================================
    # status / metrics
    # =====================================================================
    def _event(self, level: str, message: str) -> None:
        self.db.log_activity(level, message)
        self.event_logged.emit(level, message)

    def _action_note(self, text: str) -> None:
        self._status.action = text
        self.toasts.emit(text)

    def _safety_note(self, text: str) -> None:
        self._status.action = text

    def _status_changed(self, _why: str = "") -> None:
        pass  # emission happens via _emit_status

    def refresh_context_now(self) -> None:
        self._refresh_context()

    def _refresh_context(self) -> None:
        ctx = self.context_engine.snapshot()
        self._context_cache = ctx
        self.multimodal.set_context(ctx)
        if SETTINGS.auto_switch_profile:
            if self.profiles.maybe_auto_switch(ctx.exe):
                self.profile_changed.emit(self.profiles.active.id)

    def _sd_emit(self, now: float) -> None:
        """Emit a status snapshot at ~6 Hz so the dashboard never stays stuck
        on its initial (gray) state, even while the camera delivers no frames."""
        if now - getattr(self, "_last_status_time", 0.0) < 0.16:
            return
        self._last_status_time = now
        self._emit_status(snapshot_time=now, cpu_baseline_ok=True)

    def _emit_status(self, snapshot_time: float, cpu_baseline_ok: bool = True) -> None:
        s = self._status
        s.camera_active = self.camera.is_healthy
        s.hand_tracking_active = self.hand_tracker.available
        s.gaze_ready = (self.settings.tracking.gaze_enabled
                        and self.face_tracker.available)
        s.tracking_paused = self.privacy.tracking_paused
        s.voice_ready = bool(self.voice.engine and self.voice.engine.status in ("listening", "recognizing"))
        s.gaze_active = self.multimodal.state.gaze_active
        ind = self.privacy.indicators()
        s.control_enabled = ind["control"]
        s.emergency = ind["emergency"]
        s.privacy_mode = ind["privacy"]
        s.hand_present = getattr(self, "_last_hand_detected", False) or self._last_hand_seen()
        s.hand_confidence = self.engine.raw_confidence if s.hand_present else 0.0
        s.gesture = "LOCKED" if self.engine.locked else self.engine.confirmed_gesture
        s.gesture_confidence = self.engine.raw_confidence
        s.fps = self.camera.fps
        s.tracking_fps = self._processing_fps
        s.latency_ms = 1000.0 * (0.02 if cpu_baseline_ok else 0.05)
        s.cpu = self._cpu()
        s.memory_mb = self._mem()
        s.active_profile = self.profiles.active.name
        s.active_app = self._context_cache.exe
        s.active_context = self._context_cache.description
        s.voice_status = self.voice.engine.status if self.voice.engine else "idle"
        s.last_voice = self.voice.last_text
        s.recognized_text = self.voice.last_text
        s.last_intent = self.intent_engine.last.describe() if self.intent_engine.last else ""
        s.calibration = "ready" if self.calibration.calibrated else "none"
        mm = self.multimodal.state
        s.multimodal_hint = mm.copilot_hint
        s.demo_mode = self.demo.enabled
        s.safety_level = self.safety.confirmation_level
        s.head_enabled = self.settings.head.enabled
        env = self.env_report
        s.lighting = env.lighting if env else "unknown"
        s.brightness = env.brightness if env else 0.0
        s.contrast = env.contrast if env else 0.0
        perf = self.perf.snapshot()
        s.perf = perf
        s.cmd_per_minute = perf["commands_per_minute"]
        s.gesture_latency_ms = perf["gesture_latency_ms"]
        s.voice_latency_ms = perf["voice_latency_ms"]
        s.history_count = len(self.history)
        if self.air_mouse.current_screen:
            s.cursor_x, s.cursor_y = self.air_mouse.current_screen
        s.diag = {
            "hand": s.hand_confidence, "gesture_conf": s.gesture_confidence,
            "fingerprint": getattr(getattr(self, "camera", None), "_frame_counter", 0),
            "gaze_xy": list(mm.gaze_xy), "gaze_match": mm.gaze_pointer_match,
            "profile": self.profiles.active.id, "context": s.active_context,
            "voice_status": s.voice_status, "pinch_hold": self.holder.active,
            "custom_gestures": len(self._rematcher.gestures),
            "demo": self.demo.enabled,
            "safety": self.safety.confirmation_level,
            "lighting": s.lighting,
            "camera_state": (self.camera.error if self.camera.error
                             else ("ok" if self.camera.is_running else "off")),
            "hand_model": self.hand_tracker.error,
            "face_model": self.face_tracker.error,
        }
        self.status_updated.emit(s.filled())

    def _last_hand_seen(self) -> bool:
        # cheap heuristic from engine activity
        return self.engine.raw_gesture not in ("",) or bool(self.engine.confirmed_gesture != ge.REST)

    def _cpu(self) -> float:
        if HAVE_PSUTIL:
            try:
                return psutil.cpu_percent(interval=None)
            except Exception:
                pass
        return 0.0

    def _mem(self) -> float:
        if HAVE_PSUTIL:
            try:
                return psutil.Process().memory_info().rss / (1024 * 1024)
            except Exception:
                pass
        return 0.0

    def set_gaze_enabled(self, on: bool) -> None:
        self.settings.tracking.gaze_enabled = on
        self.settings.save()
        self._event("INFO", f"gaze tracking {'enabled' if on else 'disabled'}")

    def set_voice_language(self, lang: str) -> None:
        """Update the voice-recognition language and apply it live."""
        self.settings.voice.language = lang
        try:
            self.settings.save()
        except Exception:
            pass
        if self.voice:
            self.voice.restart()
        self._event("INFO", f"Voice language set to {lang}")

    def set_profile(self, pid: str) -> None:
        self.profiles.set_active(pid)
        self.profile_changed.emit(pid)

    # =====================================================================
    # v2.0 demo mode
    # =====================================================================
    def set_demo_mode(self, on: bool) -> bool:
        self.demo.set_enabled(bool(on))
        self.settings.demo.start_in_demo = self.demo.enabled
        try:
            self.settings.save()
        except Exception:
            pass
        self.demo_changed.emit(self.demo.enabled)
        self._event("INFO", f"DEMO MODE {'ON' if self.demo.enabled else 'OFF'}")
        return self.demo.enabled

    def toggle_demo(self) -> bool:
        return self.set_demo_mode(not self.demo.enabled)

    def is_demo(self) -> bool:
        return self.demo.enabled

    # =====================================================================
    # v2.0 history / analytics / perf
    # =====================================================================
    def get_history(self, n: int = 30) -> list:
        return self.history.recent(n)

    def get_analytics(self) -> dict:
        return self.history.analytics()

    def clear_history(self) -> None:
        self.history.clear()

    def get_perf(self) -> dict:
        return self.perf.snapshot()

    def get_env(self) -> dict | None:
        return self.env_report.as_dict() if self.env_report else None

    def run_test_lab(self) -> list:
        results = self.test_lab.run_all()
        return [{"name": r.name, "ok": r.ok, "detail": r.detail,
                 "duration_ms": round(r.duration_ms, 1)} for r in results]

    # =====================================================================
    # v2.0 macros (persisted)
    # =====================================================================
    def list_macros(self) -> list:
        return self.macros.to_list()

    def add_macro(self, data: dict) -> str | None:
        err = self.macros.add(Macro.from_dict(data))
        if err is None:
            self._save_macros()
        return err

    def update_macro(self, data: dict) -> str | None:
        m = Macro.from_dict(data)
        ok = self.macros.update(m)
        if ok:
            self._save_macros()
        return None if ok else "macro not found"

    def delete_macro(self, name: str) -> bool:
        ok = self.macros.remove(name)
        if ok:
            self._save_macros()
        return ok

    def run_macro(self, name: str) -> bool:
        m = self.macros.get(name)
        if m is not None:
            self.history.record(source="macro", action=f"Run macro '{name}'",
                                status=STATUS_OK)
            self._event("INFO", f"Running macro '{name}'")
        return self.macros.run_by_name(name)

    def _load_macros(self) -> None:
        try:
            self.macros.load_list(self.db.get_kv("macros_v1", []) or [])
        except Exception as e:
            log.warning("macros load failed: %s", e)

    def _save_macros(self) -> None:
        try:
            self.db.set_kv("macros_v1", self.macros.to_list())
        except Exception as e:
            log.warning("macros save failed: %s", e)

    # =====================================================================
    # v2.0 custom commands (persisted)
    # =====================================================================
    def list_custom_commands(self) -> list:
        return self.custom_commands.to_list()

    def add_custom_command(self, data: dict) -> str | None:
        err = self.custom_commands.add(CustomCommand.from_dict(data))
        if err is None:
            self._save_custom_commands()
        return err

    def delete_custom_command(self, phrase: str) -> bool:
        ok = self.custom_commands.remove(phrase)
        if ok:
            self._save_custom_commands()
        return ok

    def _load_custom_commands(self) -> None:
        try:
            self.custom_commands.load_list(self.db.get_kv("custom_commands_v1", []) or [])
        except Exception as e:
            log.warning("custom commands load failed: %s", e)

    def _save_custom_commands(self) -> None:
        try:
            self.db.set_kv("custom_commands_v1", self.custom_commands.to_list())
        except Exception as e:
            log.warning("custom commands save failed: %s", e)

    # =====================================================================
    # v2.0 AI planner
    # =====================================================================
    def plan_request(self, text: str):
        plan = self.planner.plan(text)
        if not plan.is_empty():
            self.plan_preview.emit(plan)
        return plan

    def execute_plan(self, plan) -> bool:
        """Run a confirmed plan: each step still passes Safety + demo gates."""
        if plan is None or plan.is_empty():
            return False
        steps = [{"action": s.action, "params": dict(s.params)}
                 for s in plan.steps]
        self.history.record(source="ai", action=f"Plan: {plan.description}",
                            status=STATUS_OK)
        self.perf.note_command()
        return self.macros.run_steps(steps, source="ai")

    def reject_plan(self) -> None:
        self._event("INFO", "AI plan declined by user")

    # =====================================================================
    # v2.0 safety + head settings
    # =====================================================================
    def set_confirmation_level(self, level: str) -> None:
        self.safety.set_confirmation_level(level)
        self.settings.safety.confirmation_level = level
        try:
            self.settings.save()
        except Exception:
            pass
        self._event("INFO", f"Confirmation level: {level}")

    def set_head_enabled(self, on: bool) -> None:
        self.settings.head.enabled = bool(on)
        try:
            self.settings.save()
        except Exception:
            pass
        self._event("INFO", f"Head control {'enabled' if on else 'disabled'}")

    def _engine_event_tap(self, ev: ge.GestureEvent) -> None:
        pass