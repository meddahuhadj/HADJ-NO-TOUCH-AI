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
        # A fist has to be seen for `fist_debounce` before the hold timer
        # starts, otherwise a single noisy frame could register as a hold.
        self.fist_candidate_since: Optional[float] = None
        self.fist_debounce: float = self.settings.get("gestures.fist_debounce", 0.12)
        # When the pose drops, the hold is kept alive for this long before being
        # discarded, so brief tracking dropouts do not restart the timer.
        self.fist_lost_since: Optional[float] = None
        self.fist_dropout_tolerance: float = self.settings.get(
            "gestures.fist_dropout_tolerance", 0.25
        )

        # Two-finger scroll tracking
        self.prev_scroll_y: Optional[float] = None

        # Swipe tracking
        self.swipe_history = []  # list of (timestamp, norm_x)
        self.last_swipe_trigger_time: float = 0.0

        # Gesture Hysteresis (~300ms hold delay)
        self.gesture_hold_delay: float = float(self.settings.get("gestures.gesture_hold_delay", 0.30))
        self.current_candidate_gesture: HandGesture = HandGesture.NONE
        self.candidate_start_time: float = 0.0
        self.candidate_progress: float = 0.0

        # Arming / Disarming via 1.0s Open Palm
        self.arm_hold_duration: float = 1.0
        self.palm_candidate_start: Optional[float] = None
        self.palm_arm_cooldown_until: float = 0.0
        self.arm_progress: float = 0.0
        self.arm_toggled: bool = False

    def get_arm_progress(self) -> float:
        """Returns 0.0 to 1.0 representing progress towards toggling arming state."""
        return self.arm_progress

    def consume_arm_toggle(self) -> bool:
        """Consumes and returns whether arming state has been toggled by holding palm for 1s."""
        if self.arm_toggled:
            self.arm_toggled = False
            return True
        return False

    def get_gesture_hold_progress(self) -> float:
        """Returns 0.0 to 1.0 representing progress towards committing current candidate gesture."""
        return self.candidate_progress

    def is_gesture_committed(self, gesture: HandGesture) -> bool:
        """Returns True if the gesture has been held for the required hysteresis delay (~300ms)."""
        if gesture in (HandGesture.INDEX_POINT, HandGesture.PINCH_HOLD):
            return True
        if self.current_candidate_gesture == gesture:
            return self.candidate_progress >= 1.0
        return False

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
        Tracks arming gesture (1s open palm) and gesture hold hysteresis (~300ms).
        """
        now = time.time()
        gesture, conf = self._classify_raw(data, now)
        self._update_temporal_progress(gesture, now)
        return gesture, conf

    def _update_temporal_progress(self, gesture: HandGesture, now: float) -> None:
        """Tracks candidate hold progress for hysteresis and arming gesture."""
        # 1. Arming tracking (OPEN_PALM held for 1.0s)
        if gesture == HandGesture.OPEN_PALM:
            if now > self.palm_arm_cooldown_until:
                if self.palm_candidate_start is None:
                    self.palm_candidate_start = now
                hold = now - self.palm_candidate_start
                self.arm_progress = min(1.0, hold / self.arm_hold_duration)
                if hold >= self.arm_hold_duration:
                    self.arm_toggled = True
                    self.palm_arm_cooldown_until = now + 1.2
                    self.palm_candidate_start = None
                    self.arm_progress = 0.0
            else:
                self.arm_progress = 0.0
        else:
            self.palm_candidate_start = None
            self.arm_progress = 0.0

        # 2. Hysteresis tracking for discrete gestures
        if gesture in (
            HandGesture.PINCH,
            HandGesture.DOUBLE_PINCH,
            HandGesture.THUMB_UP,
            HandGesture.TWO_FINGER_SCROLL_UP,
            HandGesture.TWO_FINGER_SCROLL_DOWN,
            HandGesture.SWIPE_LEFT,
            HandGesture.SWIPE_RIGHT
        ):
            if self.current_candidate_gesture == gesture:
                elapsed = now - self.candidate_start_time
                self.candidate_progress = min(1.0, elapsed / max(0.05, self.gesture_hold_delay))
            else:
                self.current_candidate_gesture = gesture
                self.candidate_start_time = now
                self.candidate_progress = 0.0
        else:
            self.current_candidate_gesture = gesture
            self.candidate_start_time = now
            self.candidate_progress = 0.0

    def _classify_raw(self, data: HandLandmarksData, now: float) -> Tuple[HandGesture, float]:
        """
        Evaluates geometric landmarks and returns (HandGesture, confidence).

        Order matters and is deliberate: closed and confirmation poses gate
        everything, pinch owns thumb+index contact before any open-hand pose is
        considered, and the swipe test runs before the two-finger branch so a
        two-finger sweep is not swallowed by the scroll dead band.
        """
        # The scroll reference belongs to the two-finger pose alone.
        two_fingers = (
            data.index_extended and
            data.middle_extended and
            not data.ring_extended and
            not data.pinky_extended
        )
        if not two_fingers:
            self.prev_scroll_y = None

        # 1. Evaluate FIST (Emergency Stop / Cancel)
        all_fingers_folded = (
            not data.index_extended and
            not data.middle_extended and
            not data.ring_extended and
            not data.pinky_extended
        )

        if all_fingers_folded and not data.thumb_extended:
            if self.fist_candidate_since is None:
                self.fist_candidate_since = now
            self.fist_lost_since = None

            if now - self.fist_candidate_since >= self.fist_debounce:
                if self.fist_start_time is None:
                    self.fist_start_time = self.fist_candidate_since
                return HandGesture.FIST, 0.95
        else:
            if self.fist_candidate_since is not None:
                if self.fist_lost_since is None:
                    self.fist_lost_since = now
                elif now - self.fist_lost_since > self.fist_dropout_tolerance:
                    self.fist_start_time = None
                    self.fist_candidate_since = None
                    self.fist_lost_since = None

        # 2. Evaluate THUMB UP (Confirmation)
        thumb_pointing_up = data.thumb_tip[1] < data.thumb_ip[1] < data.wrist[1]
        if all_fingers_folded and data.thumb_extended and thumb_pointing_up:
            return HandGesture.THUMB_UP, 0.94

        # 3. Evaluate PINCH and PINCH HOLD (Click / Double Click / Drag)
        is_pinch_contact = data.pinch_distance < self.pinch_threshold
        if is_pinch_contact:
            if not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_time = now

                # Check if this pinch occurred shortly after previous release -> DOUBLE PINCH
                if (now - self.last_pinch_release_time) < self.double_pinch_window:
                    self.last_pinch_click_time = now
                    return HandGesture.DOUBLE_PINCH, 0.96

                self.last_pinch_click_time = now
                return HandGesture.PINCH, 0.93
            else:
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
        if (
            data.thumb_extended and
            data.index_extended and
            data.middle_extended and
            data.ring_extended and
            data.pinky_extended
        ):
            return HandGesture.OPEN_PALM, 0.95

        # 5. Evaluate SWIPE (Fast horizontal displacement of Index tip)
        swipe = self._detect_swipe(now, data.index_tip[0])
        if swipe is not None:
            return swipe, 0.88

        # 6. Evaluate TWO FINGER SCROLL (Index + Middle extended, Ring + Pinky folded)
        if two_fingers:
            avg_y = (data.index_tip[1] + data.middle_tip[1]) / 2.0
            prev_y = self.prev_scroll_y
            self.prev_scroll_y = avg_y
            if prev_y is not None:
                dy = avg_y - prev_y
                if dy < -self.scroll_dead_band:
                    return HandGesture.TWO_FINGER_SCROLL_UP, 0.92
                if dy > self.scroll_dead_band:
                    return HandGesture.TWO_FINGER_SCROLL_DOWN, 0.92
            return HandGesture.INDEX_POINT, 0.70

        # 7. Evaluate INDEX POINT (Virtual Mouse Movement)
        if data.index_extended and not (data.middle_extended and data.ring_extended and data.pinky_extended):
            return HandGesture.INDEX_POINT, 0.94

        return HandGesture.NONE, 0.50

    def _detect_swipe(self, now: float, norm_x: float) -> Optional[HandGesture]:
        """
        Returns SWIPE_LEFT / SWIPE_RIGHT for a fast horizontal sweep, else None.
        """
        self.swipe_history.append((now, norm_x))
        self.swipe_history = [(t, x) for t, x in self.swipe_history if (now - t) <= 0.3]

        if len(self.swipe_history) < 3:
            return None
        if (now - self.last_swipe_trigger_time) <= 0.7:
            return None

        dx = self.swipe_history[-1][1] - self.swipe_history[0][1]
        dt = self.swipe_history[-1][0] - self.swipe_history[0][0]
        if dt <= 0.05:
            return None

        velocity = dx / dt
        if velocity < -self.swipe_velocity_threshold:
            self.last_swipe_trigger_time = now
            return HandGesture.SWIPE_LEFT
        if velocity > self.swipe_velocity_threshold:
            self.last_swipe_trigger_time = now
            return HandGesture.SWIPE_RIGHT
        return None

    def reset(self) -> None:
        """Clears every temporal filter, e.g. after the hand leaves the frame."""
        self.is_pinching = False
        self.in_drag_mode = False
        self.pinch_start_time = 0.0
        self.last_pinch_release_time = 0.0
        self.last_pinch_click_time = 0.0
        self.fist_start_time = None
        self.fist_candidate_since = None
        self.fist_lost_since = None
        self.prev_scroll_y = None
        self.swipe_history = []
        self.last_swipe_trigger_time = 0.0
        self.palm_candidate_start = None
        self.arm_progress = 0.0
        self.current_candidate_gesture = HandGesture.NONE
        self.candidate_start_time = 0.0
        self.candidate_progress = 0.0

    def get_fist_hold_duration(self) -> float:
        """Returns how long the fist has been continuously held."""
        if self.fist_start_time is None:
            return 0.0
        return time.time() - self.fist_start_time
