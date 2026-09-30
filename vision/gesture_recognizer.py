import time
from enum import Enum, auto
from typing import Optional, Tuple
from vision.gesture_detector import HandLandmarksData
from config.settings_manager import SettingsManager


class HandGesture(Enum):
    NONE = "NONE"
    INDEX_POINT = "INDEX_POINT"
    PINCH = "PINCH"
    DOUBLE_PINCH = "DOUBLE_PINCH"
    PINCH_HOLD = "PINCH_HOLD"
    OPEN_PALM = "OPEN_PALM"
    TWO_FINGER_SCROLL_UP = "TWO_FINGER_SCROLL_UP"
    TWO_FINGER_SCROLL_DOWN = "TWO_FINGER_SCROLL_DOWN"
    SWIPE_LEFT = "SWIPE_LEFT"
    SWIPE_RIGHT = "SWIPE_RIGHT"
    THUMB_UP = "THUMB_UP"
    FIST = "FIST"


class GestureRecognizer:
    """Classifies discrete and continuous hand gestures from hand landmarks with temporal filtering."""

    def __init__(self):
        self.settings = SettingsManager()

        # Calibration parameters
        self.pinch_threshold: float = self.settings.get("gestures.pinch_click_threshold", 0.045)
        self.drag_hold_delay: float = self.settings.get("gestures.pinch_hold_drag_delay", 0.35)
        self.double_pinch_window: float = self.settings.get("gestures.double_pinch_window", 0.40)
        self.swipe_velocity_threshold: float = self.settings.get("gestures.swipe_velocity_threshold", 1.8)
        self.scroll_dead_band: float = self.settings.get("gestures.scroll_dead_band", 0.015)

        # State tracking
        self.is_pinching: bool = False
        self.pinch_start_time: float = 0.0
        self.last_pinch_release_time: float = 0.0
        self.last_pinch_click_time: float = 0.0
        self.in_drag_mode: bool = False

        # Fist tracking (for Emergency Stop detection)
        self.fist_start_time: Optional[float] = None

        # Two-finger scroll tracking
        self.prev_scroll_y: Optional[float] = None

        # Swipe tracking
        self.swipe_history = []  # list of (timestamp, norm_x)
        self.last_swipe_trigger_time: float = 0.0

    def update_calibration(
        self,
        pinch_threshold: Optional[float] = None,
        drag_delay: Optional[float] = None,
        double_pinch_window: Optional[float] = None,
        swipe_velocity: Optional[float] = None,
        scroll_dead_band: Optional[float] = None,
    ) -> None:
        if pinch_threshold is not None:
            self.pinch_threshold = pinch_threshold
        if drag_delay is not None:
            self.drag_hold_delay = drag_delay
        if double_pinch_window is not None:
            self.double_pinch_window = double_pinch_window
        if swipe_velocity is not None:
            self.swipe_velocity_threshold = swipe_velocity
        if scroll_dead_band is not None:
            self.scroll_dead_band = scroll_dead_band

    def apply_report(self, report) -> None:
        """
        Applies every value in a :class:`~core.auto_calibration.CalibrationReport`.

        Taking the whole report at once keeps the recogniser internally
        consistent: a new pinch threshold is never paired with a stale dead zone
        or a stale swipe velocity.
        """
        self.pinch_threshold = report.pinch_threshold
        self.drag_hold_delay = report.drag_hold_delay
        self.double_pinch_window = report.double_pinch_window
        self.swipe_velocity_threshold = report.swipe_velocity_threshold
        self.scroll_dead_band = report.scroll_dead_band

    def classify(self, data: HandLandmarksData) -> Tuple[HandGesture, float]:
        """
        Evaluates geometric landmarks and returns (HandGesture, confidence).
        """
        now = time.time()

        # 1. Evaluate FIST (Emergency Stop / Cancel)
        # All 4 fingers folded, thumb folded across fingers
        all_fingers_folded = (
            not data.index_extended and
            not data.middle_extended and
            not data.ring_extended and
            not data.pinky_extended
        )

        if all_fingers_folded and not data.thumb_extended:
            if self.fist_start_time is None:
                self.fist_start_time = now
            return HandGesture.FIST, 0.95
        else:
            self.fist_start_time = None

        # 2. Evaluate THUMB UP (Confirmation)
        # Thumb extended upwards (thumb tip above thumb IP and wrist), other 4 fingers folded
        thumb_pointing_up = data.thumb_tip[1] < data.thumb_ip[1] < data.wrist[1]
        if all_fingers_folded and data.thumb_extended and thumb_pointing_up:
            return HandGesture.THUMB_UP, 0.94

        # 3. Evaluate PINCH and PINCH HOLD (Click / Double Click / Drag)
        is_pinch_contact = data.pinch_distance < self.pinch_threshold
        if is_pinch_contact:
            if not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_time = now

                # Check if this pinch occurred shortly after the previous release -> DOUBLE PINCH
                if (now - self.last_pinch_release_time) < self.double_pinch_window:
                    self.last_pinch_click_time = now
                    return HandGesture.DOUBLE_PINCH, 0.96

                self.last_pinch_click_time = now
                return HandGesture.PINCH, 0.93
            else:
                # Still holding pinch
                hold_duration = now - self.pinch_start_time
                if hold_duration >= self.drag_hold_delay:
                    self.in_drag_mode = True
                    return HandGesture.PINCH_HOLD, 0.95
                return HandGesture.PINCH, 0.90
        else:
            if self.is_pinching:
                self.is_pinching = False
                self.last_pinch_release_time = now
                self.in_drag_mode = False

        # 4. Evaluate OPEN PALM (Pause Cursor Movement / Standby)
        # All 5 fingers extended
        if (
            data.thumb_extended and
            data.index_extended and
            data.middle_extended and
            data.ring_extended and
            data.pinky_extended
        ):
            return HandGesture.OPEN_PALM, 0.95

        # 5. Evaluate TWO FINGER SCROLL (Index + Middle extended, Ring + Pinky folded)
        two_fingers = (
            data.index_extended and
            data.middle_extended and
            not data.ring_extended and
            not data.pinky_extended
        )
        if two_fingers:
            avg_y = (data.index_tip[1] + data.middle_tip[1]) / 2.0
            gesture = HandGesture.NONE
            if self.prev_scroll_y is not None:
                dy = avg_y - self.prev_scroll_y
                # dy > 0 means hand moved down on screen -> scroll down
                # dy < 0 means hand moved up on screen -> scroll up
            if dy < -self.scroll_dead_band:
                gesture = HandGesture.TWO_FINGER_SCROLL_UP
            elif dy > self.scroll_dead_band:
                gesture = HandGesture.TWO_FINGER_SCROLL_DOWN

            self.prev_scroll_y = avg_y
            if gesture != HandGesture.NONE:
                return gesture, 0.92
            return HandGesture.INDEX_POINT, 0.70  # Still pointing if stationary
        else:
            self.prev_scroll_y = None

        # 6. Evaluate SWIPE (Fast horizontal displacement of Index tip)
        self.swipe_history.append((now, data.index_tip[0]))
        # Keep last 0.3 seconds of history
        self.swipe_history = [(t, x) for t, x in self.swipe_history if (now - t) <= 0.3]
        if len(self.swipe_history) >= 3 and (now - self.last_swipe_trigger_time) > 0.7:
            dx = self.swipe_history[-1][1] - self.swipe_history[0][1]
            dt = self.swipe_history[-1][0] - self.swipe_history[0][0]
            if dt > 0.05:
                velocity = dx / dt
                if velocity < -self.swipe_velocity_threshold:  # Fast move to left
                    self.last_swipe_trigger_time = now
                    return HandGesture.SWIPE_LEFT, 0.88
                elif velocity > self.swipe_velocity_threshold:  # Fast move to right
                    self.last_swipe_trigger_time = now
                    return HandGesture.SWIPE_RIGHT, 0.88

        # 7. Evaluate INDEX POINT (Virtual Mouse Movement)
        # Index finger extended, while avoiding open palm (all fingers extended)
        if data.index_extended and not (data.middle_extended and data.ring_extended and data.pinky_extended):
            return HandGesture.INDEX_POINT, 0.94

        return HandGesture.NONE, 0.50

    def get_fist_hold_duration(self) -> float:
        """Returns how long the fist has been continuously held."""
        if self.fist_start_time is None:
            return 0.0
        return time.time() - self.fist_start_time
