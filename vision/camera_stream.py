import time
import threading
from typing import Optional, Callable
import cv2
import numpy as np
import pyautogui

from vision.gesture_detector import GestureDetector, HandLandmarksData
from vision.gesture_recognizer import GestureRecognizer, HandGesture
from vision.virtual_cursor import VirtualCursor
from automation.windows_control import WindowsControlEngine
from core.auto_calibration import (
    AdaptiveTuner, CalibrationReport, CalibrationSession, HandSample,
)
from core.event_bus import EventBus, EventType
from core.profile_manager import ProfileManager
from core.app_profile_manager import AppProfileManager, AppProfile
from core.security_engine import SecurityEngine
from core.qt_bridge import QtBridge
from config.settings_manager import SettingsManager


class CameraStream(threading.Thread):
    """
    High-performance, threaded camera capture and gesture vision pipeline.
    Runs asynchronously and dispatches processed frames and cursor motions safely via QtBridge signals.
    """

    def __init__(self, camera_index: int = 0):
        super(CameraStream, self).__init__(daemon=True)
        self.camera_index = camera_index
        self.running = False
        self.cap: Optional[cv2.VideoCapture] = None

        self.settings = SettingsManager()
        self.event_bus = EventBus()
        self.profile_mgr = ProfileManager()
        self.security = SecurityEngine()
        self.app_profile_mgr = AppProfileManager()
        self.win_control = WindowsControlEngine()
        self.qt_bridge = QtBridge()

        # Vision subcomponents
        self.detector = GestureDetector()
        self.recognizer = GestureRecognizer()
        self.cursor = VirtualCursor(
            smoothing_factor=self.settings.get("gestures.smoothing_factor", 0.45),
            dead_zone=self.settings.get("gestures.dead_zone_radius", 0.015),
            speed_factor=self.settings.get("gestures.cursor_speed", 1.6),
            active_box=self._read_active_box(),
        )

        # Continuous re-tuning of the pinch threshold and tremor filters. The
        # guided wizard measures once; this keeps the values honest afterwards,
        # as lighting, distance and posture drift over a session.
        self.adaptive_tuner: Optional[AdaptiveTuner] = None
        if self.settings.get("calibration.adaptive_tuning", True):
            self.adaptive_tuner = AdaptiveTuner(
                self.settings,
                window=int(self.settings.get("calibration.adaptive_sample_window", 240)),
                min_samples=int(self.settings.get("calibration.adaptive_min_samples", 45)),
                write_threshold=float(self.settings.get("calibration.adaptive_write_threshold", 0.08)),
            )
        self._adaptation_tick = 0

        # Active calibration session driven by the wizard, if one is attached.
        self.calibration_session: Optional[CalibrationSession] = None
        self.calibration_report: Optional[CalibrationReport] = None

        self.latest_frame: Optional[np.ndarray] = None
        self.latest_gesture: HandGesture = HandGesture.NONE
        self.gesture_confidence: float = 0.0
        self.pointer_screen_pos: tuple = (0, 0)
        self._pinch_clicked: bool = False
        self._double_pinch_clicked: bool = False
        self._last_hand_time: float = 0.0
        self._hand_lost_grace_s: float = 0.40  # Eliminates flickering 'hand not visible'

        # GUI throttle: cap visual-only updates at ~15 FPS so the Qt event
        # queue never backs up with stale frames while the cursor/click
        # actions remain at full camera frame rate.
        self._gui_interval: float = 1.0 / 15.0
        self._last_gui_emit: float = 0.0
        self._last_emitted_gesture: str = "NONE"

        # Safety / Privacy / Arming
        self.camera_enabled = self.settings.get("privacy.camera_enabled", True)
        self.cursor_control_active = True
        self.is_armed: bool = False
        self.diagnostic_reason: str = "diag.no_hand"
        self.hold_progress: float = 0.0

        # Eco mode & frame cache
        self._eco_frame_counter: int = 0
        self._last_landmarks_data: Optional[HandLandmarksData] = None

        # Gesture callbacks or hooks
        self.on_frame_callbacks = []

    def set_armed(self, armed: bool) -> None:
        """Sets the gesture arming state and notifies listeners."""
        if self.is_armed != armed:
            self.is_armed = armed
            self.event_bus.publish(EventType.GESTURE_ARM_TOGGLED, {"armed": armed})
            self.qt_bridge.arm_state_changed.emit(armed)
            self._play_arm_sound(armed)

    def toggle_armed(self) -> None:
        """Toggles gesture arming between active and standby."""
        self.set_armed(not self.is_armed)

    def _play_arm_sound(self, armed: bool) -> None:
        """Plays a gentle audible tone to confirm arming / disarming."""
        try:
            import winsound
            if armed:
                winsound.Beep(988, 80)
            else:
                winsound.Beep(494, 100)
        except Exception:
            pass

    def set_camera_enabled(self, enabled: bool) -> None:
        self.camera_enabled = enabled
        if not enabled:
            self.latest_frame = None

    def add_frame_callback(self, callback: Callable[[np.ndarray, str, float], None]) -> None:
        self.on_frame_callbacks.append(callback)

    def _read_active_box(self):
        """Reads the calibrated reach box, tolerating a malformed config value."""
        box = self.settings.get("gestures.active_box", [0.0, 0.0, 1.0, 1.0])
        if isinstance(box, (list, tuple)) and len(box) == 4:
            try:
                return tuple(float(v) for v in box)
            except (TypeError, ValueError):
                pass
        return (0.0, 0.0, 1.0, 1.0)

    # ------------------------------------------------------------------ #
    # Calibration
    # ------------------------------------------------------------------ #

    def apply_calibration(self, report: CalibrationReport) -> None:
        """
        Installs a freshly measured report across the whole vision stack.

        The values are pushed into the recogniser, the cursor filters and the
        settings in one go so the next frame is already consistent; a partial
        application would briefly pair a new pinch threshold with an old swipe
        velocity and misfire.
        """
        patch = report.to_settings_patch()
        for key, value in patch.items():
            try:
                self.settings.set(key, value)
            except Exception:
                # A locked config file must not abort the calibration; the live
                # components are still updated below.
                pass

        self.recognizer.apply_report(report)
        self.cursor.update_settings(
            report.smoothing_factor, report.dead_zone_radius, report.cursor_speed
        )
        self.cursor.set_active_box(report.active_box)
        self.cursor.reset()

        if self.adaptive_tuner is not None:
            # Start from the freshly measured values rather than letting the
            # rolling window drag the threshold back towards the old one.
            self.adaptive_tuner.reset()

        # Temporal filters were tuned against the old thresholds.
        self.recognizer.reset()

        self.calibration_report = report
        self.event_bus.publish(
            EventType.CALIBRATION_APPLIED, {"report": report}
        )

    def attach_calibration_session(self, session: Optional[CalibrationSession]) -> None:
        """Routes hand samples into a wizard-driven measurement session."""
        self.calibration_session = session

    def _feed_calibration(self, landmarks: Optional[HandLandmarksData]) -> None:
        """Converts landmarks into a calibration sample and feeds both consumers."""
        if landmarks is None:
            if self.calibration_session is not None:
                self.calibration_session.notify_hand_lost()
            if self.adaptive_tuner is not None:
                self.adaptive_tuner.notify_hand_lost()
            return

        if self.calibration_session is not None:
            self.calibration_session.feed(
                HandSample(
                    index_tip=(landmarks.index_tip[0], landmarks.index_tip[1]),
                    pinch_distance=landmarks.pinch_distance,
                    timestamp=time.time(),
                )
            )

        if self.adaptive_tuner is not None:
            self.adaptive_tuner.feed(
                (landmarks.index_tip[0], landmarks.index_tip[1]),
                landmarks.pinch_distance,
                time.time(),
            )
            # Evaluating every frame would be wasted work: the rolling window
            # only changes meaningfully over tens of frames.
            self._adaptation_tick += 1
            if self._adaptation_tick >= 15:
                self._adaptation_tick = 0
                event = self.adaptive_tuner.evaluate()
                if event is not None:
                    self._apply_adaptation(event)

    def _apply_adaptation(self, event) -> None:
        """Pushes a runtime adaptation into the live components and the log."""
        if event.key == AdaptiveTuner.PINCH_KEY:
            self.recognizer.update_calibration(pinch_threshold=event.new_value)
        elif event.key == AdaptiveTuner.DEAD_ZONE_KEY:
            self.cursor.update_settings(
                self.cursor.smoothing, event.new_value, self.cursor.speed_factor
            )
        elif event.key == AdaptiveTuner.SMOOTHING_KEY:
            self.cursor.update_settings(
                event.new_value, self.cursor.dead_zone, self.cursor.speed_factor
            )
        self.event_bus.publish(EventType.CALIBRATION_ADAPTED, {"event": event})

    def calibration_status(self) -> dict:
        """Live calibration read-out for the HUD and the main window."""
        status = {
            "calibrated": bool(self.settings.get("gestures.calibrated", False)),
            "adaptive": self.adaptive_tuner is not None,
            "active": self.calibration_session is not None,
            "pinch_threshold": round(self.recognizer.pinch_threshold, 5),
            "dead_zone_radius": round(self.cursor.dead_zone, 5),
            "smoothing_factor": round(self.cursor.smoothing, 4),
            "cursor_speed": round(self.cursor.speed_factor, 3),
            "active_box": [round(v, 4) for v in self.cursor.active_box],
        }
        if self.adaptive_tuner is not None:
            status.update(self.adaptive_tuner.snapshot())
        return status

    def _act_on_gesture(self, gesture: HandGesture, landmarks_data: HandLandmarksData) -> None:
        """
        Translates one classified gesture into cursor and keyboard actions.

        Every pyautogui call is wrapped: FAILSAFE is enabled, so a pointer driven
        into a screen corner raises FailSafeException. That exception is the
        user's last-resort kill switch, so it halts automation instead of
        killing the camera thread and leaving the pointer wherever it was.
        """
        try:
            self._dispatch_gesture(gesture, landmarks_data)
        except pyautogui.FailSafeException:
            self.cursor.is_dragging = False
            self.security.trigger_emergency_stop("PYAUTOGUI_FAILSAFE")
        except Exception as e:
            # A failing automation call must not take the vision loop down with
            # it; the next frame simply tries again.
            print(f"[CameraStream] Gesture action failed: {e}")

    def _dispatch_gesture(self, gesture: HandGesture, landmarks_data: HandLandmarksData) -> None:
        """The actual gesture-to-action mapping, free of error handling."""
        if (
            self.security.is_emergency_stopped
            or not self.cursor_control_active
            or self.calibration_session is not None
        ):
            return

        # Move Cursor on Index Point or while dragging
        if gesture in (HandGesture.INDEX_POINT, HandGesture.PINCH_HOLD, HandGesture.PINCH):
            sx, sy = self.cursor.map_normalized_to_screen(
                landmarks_data.index_tip[0],
                landmarks_data.index_tip[1]
            )
            self.pointer_screen_pos = (sx, sy)

            if gesture == HandGesture.INDEX_POINT:
                self.win_control.move_mouse(sx, sy)
                self.qt_bridge.cursor_moved.emit(sx, sy)

        # Pinch -> Left Click (debounced: exactly one click per pinch)
        if gesture == HandGesture.PINCH:
            if not self._pinch_clicked:
                self._pinch_clicked = True
                self.win_control.click(self.pointer_screen_pos[0], self.pointer_screen_pos[1])
        else:
            self._pinch_clicked = False

        # Double Pinch -> Double Click (debounced)
        if gesture == HandGesture.DOUBLE_PINCH:
            if not self._double_pinch_clicked:
                self._double_pinch_clicked = True
                self.win_control.double_click(self.pointer_screen_pos[0], self.pointer_screen_pos[1])
        else:
            self._double_pinch_clicked = False

        # Pinch Hold -> Drag
        if gesture == HandGesture.PINCH_HOLD:
            if not self.cursor.is_dragging:
                self.cursor.is_dragging = True
                self.win_control.mouse_down()
            self.win_control.move_mouse(self.pointer_screen_pos[0], self.pointer_screen_pos[1])

        # Two Finger Scroll Up / Down
        elif gesture == HandGesture.TWO_FINGER_SCROLL_UP:
            self.win_control.scroll(self.settings.get("gestures.scroll_speed", 40))
        elif gesture == HandGesture.TWO_FINGER_SCROLL_DOWN:
            self.win_control.scroll(-self.settings.get("gestures.scroll_speed", 40))

        # Swipes
        elif gesture == HandGesture.SWIPE_LEFT:
            self.win_control.go_back()
        elif gesture == HandGesture.SWIPE_RIGHT:
            self.win_control.go_forward()

        # Release drag if pinch released
        if self.cursor.is_dragging and not self.recognizer.in_drag_mode:
            self._release_drag_if_needed()

    def _release_drag_if_needed(self) -> None:
        """Releases the OS left mouse button if drag state was active."""
        if getattr(self, "cursor", None) is not None and self.cursor.is_dragging:
            self.cursor.is_dragging = False
            try:
                self.win_control.mouse_up()
            except Exception as e:
                print(f"[CameraStream] Error releasing mouse drag: {e}")

    def _act_on_gesture(self, gesture: HandGesture, landmarks_data: HandLandmarksData) -> None:
        """
        Translates one classified gesture into cursor and keyboard actions.

        Every pyautogui call is wrapped: FAILSAFE is enabled, so a pointer driven
        into a screen corner raises FailSafeException. That exception is the
        user's last-resort kill switch, so it halts automation instead of
        killing the camera thread and leaving the pointer wherever it was.
        """
        try:
            self._dispatch_gesture(gesture, landmarks_data)
        except pyautogui.FailSafeException:
            self._release_drag_if_needed()
            self.security.trigger_emergency_stop("PYAUTOGUI_FAILSAFE")
        except Exception as e:
            # A failing automation call must not take the vision loop down with
            # it; the next frame simply tries again.
            self._release_drag_if_needed()
            print(f"[CameraStream] Gesture action failed: {e}")

    def _dispatch_gesture(self, gesture: HandGesture, landmarks_data: HandLandmarksData) -> None:
        """The actual gesture-to-action mapping, gated by arming state and hysteresis."""
        if (
            self.security.is_emergency_stopped
            or not self.cursor_control_active
            or self.calibration_session is not None
            or not self.is_armed
        ):
            self._release_drag_if_needed()
            return

        # Move Cursor on Index Point or while dragging
        if gesture in (HandGesture.INDEX_POINT, HandGesture.PINCH_HOLD, HandGesture.PINCH):
            sx, sy = self.cursor.map_normalized_to_screen(
                landmarks_data.index_tip[0],
                landmarks_data.index_tip[1]
            )
            self.pointer_screen_pos = (sx, sy)

            if gesture == HandGesture.INDEX_POINT:
                self.win_control.move_mouse(sx, sy)
                self.qt_bridge.cursor_moved.emit(sx, sy)

        # Pinch -> Left Click (or Media Play/Pause if in MEDIA profile)
        if gesture == HandGesture.PINCH:
            if not self._pinch_clicked and self.recognizer.is_gesture_committed(gesture):
                self._pinch_clicked = True
                active_profile = self.app_profile_mgr.get_active_profile()
                if active_profile == AppProfile.MEDIA:
                    self.win_control.media_play_pause()
                else:
                    self.win_control.click(self.pointer_screen_pos[0], self.pointer_screen_pos[1])
        else:
            self._pinch_clicked = False

        # Double Pinch -> Double Click (debounced & hysteresis committed)
        if gesture == HandGesture.DOUBLE_PINCH:
            if not self._double_pinch_clicked and self.recognizer.is_gesture_committed(gesture):
                self._double_pinch_clicked = True
                self.win_control.double_click(self.pointer_screen_pos[0], self.pointer_screen_pos[1])
        else:
            self._double_pinch_clicked = False

        # Pinch Hold -> Drag
        if gesture == HandGesture.PINCH_HOLD:
            if not self.cursor.is_dragging:
                self.cursor.is_dragging = True
                self.win_control.mouse_down()
            self.win_control.move_mouse(self.pointer_screen_pos[0], self.pointer_screen_pos[1])

        # Two Finger Scroll Up / Down (gated by hysteresis)
        elif gesture == HandGesture.TWO_FINGER_SCROLL_UP:
            if self.recognizer.is_gesture_committed(gesture):
                self.win_control.scroll(self.settings.get("gestures.scroll_speed", 40))
        elif gesture == HandGesture.TWO_FINGER_SCROLL_DOWN:
            if self.recognizer.is_gesture_committed(gesture):
                self.win_control.scroll(-self.settings.get("gestures.scroll_speed", 40))

        # Swipes (context-aware & gated by hysteresis)
        elif gesture == HandGesture.SWIPE_LEFT:
            if self.recognizer.is_gesture_committed(gesture):
                active_profile = self.app_profile_mgr.get_active_profile()
                if active_profile == AppProfile.MEDIA:
                    self.win_control.press_key("left")  # Seek back 10s
                elif active_profile == AppProfile.DOCUMENT:
                    self.win_control.press_key("pageup")  # Previous page
                else:
                    self.win_control.go_back()  # Browser / Desktop back
        elif gesture == HandGesture.SWIPE_RIGHT:
            if self.recognizer.is_gesture_committed(gesture):
                active_profile = self.app_profile_mgr.get_active_profile()
                if active_profile == AppProfile.MEDIA:
                    self.win_control.press_key("right")  # Seek forward 10s
                elif active_profile == AppProfile.DOCUMENT:
                    self.win_control.press_key("pagedown")  # Next page
                else:
                    self.win_control.go_forward()  # Browser / Desktop forward

        # Release drag if pinch released
        if self.cursor.is_dragging and not self.recognizer.in_drag_mode:
            self._release_drag_if_needed()

    def run(self):
        self.running = True

        # Open camera with default high-performance backend (Windows Media Foundation)
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        except Exception:
            self.cap = cv2.VideoCapture(self.camera_index)

        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

        print("[CameraStream] Camera stream pipeline started.")

        while self.running:
            start_t = time.time()

            if not self.camera_enabled or self.cap is None or not self.cap.isOpened():
                self._release_drag_if_needed()
                time.sleep(0.05)
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            # Mirror frame horizontally so webcam preview acts naturally like a mirror
            if self.settings.get("performance.mirror_camera", True):
                frame = cv2.flip(frame, 1)

            # Performance & Eco mode throttling
            is_eco = (self.profile_mgr.current_profile == PerformanceProfile.ECO)
            self._eco_frame_counter += 1

            if is_eco and (self._eco_frame_counter % 2 != 0) and self._last_landmarks_data is not None:
                landmarks_data: Optional[HandLandmarksData] = self._last_landmarks_data
            else:
                detect_frame = cv2.resize(frame, (320, 240)) if (is_eco and frame.shape[1] > 320) else frame
                landmarks_data: Optional[HandLandmarksData] = self.detector.process_frame(detect_frame)
                if landmarks_data:
                    self._last_landmarks_data = landmarks_data

            gesture = HandGesture.NONE
            conf = 0.0

            if landmarks_data:
                # Calibration runs before any gesture is acted on
                self._feed_calibration(landmarks_data)

                gesture, conf = self.recognizer.classify(landmarks_data)
                self.latest_gesture = gesture
                self.gesture_confidence = conf

                # Check Arming toggle via 1s Open Palm
                if self.recognizer.consume_arm_toggle():
                    self.set_armed(not self.is_armed)

                # 1. Emergency Stop Check: Closed Fist held >= 2.0s
                if gesture == HandGesture.FIST:
                    fist_dur = self.recognizer.get_fist_hold_duration()
                    if fist_dur >= 2.0 and not self.security.is_emergency_stopped:
                        self.security.trigger_emergency_stop("CLOSED_FIST_GESTURE")

                # 2. Security Prompt Confirmation via THUMB_UP
                elif gesture == HandGesture.THUMB_UP:
                    if self.security.is_waiting_confirmation():
                        self.security.confirm_pending(source="GESTURE")

                # 3. Virtual Mouse Actions (Gated by is_armed)
                self._act_on_gesture(gesture, landmarks_data)

                self._last_hand_time = time.time()

            else:
                # Apply temporal grace period before declaring hand lost to avoid flickering
                if (time.time() - self._last_hand_time) >= self._hand_lost_grace_s:
                    self.latest_gesture = HandGesture.NONE
                    self._release_drag_if_needed()
                    self.cursor.reset()
                    self.recognizer.reset()
                    self._feed_calibration(None)

            # Diagnostic & progress evaluation
            arm_p = self.recognizer.get_arm_progress()
            gest_p = self.recognizer.get_gesture_hold_progress()
            progress = max(arm_p, gest_p)
            self.hold_progress = progress

            if landmarks_data:
                if landmarks_data.is_partially_out_of_frame:
                    diag_reason = "diag.out_of_frame"
                elif landmarks_data.hand_span < 0.14:
                    diag_reason = "diag.too_far"
                elif landmarks_data.hand_span > 0.65:
                    diag_reason = "diag.too_close"
                elif not self.is_armed:
                    if arm_p > 0.0:
                        diag_reason = "diag.arming"
                    else:
                        diag_reason = "diag.disarmed"
                else:
                    if arm_p > 0.0:
                        diag_reason = "diag.disarming"
                    elif gesture != HandGesture.NONE:
                        diag_reason = gesture.value
                    else:
                        diag_reason = "diag.armed_ready"
            else:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    brightness = float(np.mean(gray))
                except Exception:
                    brightness = 100.0

                if brightness < 45.0:
                    diag_reason = "diag.low_light"
                else:
                    diag_reason = "diag.no_hand"

            self.diagnostic_reason = diag_reason

            # Draw skeleton HUD overlay
            if landmarks_data and self.settings.get("gestures.show_hand_skeleton", True):
                frame = self.detector.draw_skeleton(
                    frame, landmarks_data, gesture.value, conf,
                    is_armed=self.is_armed, progress=progress, diagnostic_text=diag_reason
                )

            self.latest_frame = frame

            # Throttled GUI emission: only push frames and updates at ~15 FPS to Qt
            now_gui = time.time()
            if (now_gui - self._last_gui_emit) >= self._gui_interval:
                self._last_gui_emit = now_gui
                self.qt_bridge.frame_ready.emit(frame, gesture.value, conf)
                self.qt_bridge.gesture_diagnostics.emit(gesture.value, diag_reason, conf, self.is_armed, progress)
                if gesture.value != self._last_emitted_gesture:
                    self._last_emitted_gesture = gesture.value
                    self.qt_bridge.gesture_detected.emit(gesture.value, conf)

            # Calculate FPS and throttle according to Profile
            elapsed_ms = (time.time() - start_t) * 1000.0
            self.profile_mgr.record_frame(elapsed_ms)

            target_interval = self.profile_mgr.frame_interval
            sleep_time = target_interval - (time.time() - start_t)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._release_drag_if_needed()
        if self.cap:
            self.cap.release()
            print("[CameraStream] Camera stream closed.")

    def stop(self):
        self.running = False
        self._release_drag_if_needed()
