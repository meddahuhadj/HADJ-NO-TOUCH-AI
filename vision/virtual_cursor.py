import time
import math
from typing import Tuple, Optional
import pyautogui


class VirtualCursor:
    """Calculates smooth, jitter-free screen coordinates from raw camera hand coordinates."""

    def __init__(
        self,
        screen_width: Optional[int] = None,
        screen_height: Optional[int] = None,
        smoothing_factor: float = 0.40,
        dead_zone: float = 0.012,
        speed_factor: float = 1.6,
        active_box: Optional[Tuple[float, float, float, float]] = None
    ):
        if screen_width and screen_height:
            self.screen_width = screen_width
            self.screen_height = screen_height
        else:
            self.screen_width, self.screen_height = pyautogui.size()

        self.smoothing = smoothing_factor
        self.dead_zone = dead_zone
        self.speed_factor = speed_factor

        # Normalised (left, top, right, bottom) window of the camera frame the
        # user can comfortably reach, measured by the calibration engine. The
        # defaults span the whole frame, which is the uncalibrated behaviour.
        self.active_box: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
        self.set_active_box(active_box)

        # Filter state
        self.smooth_x: float = self.screen_width / 2.0
        self.smooth_y: float = self.screen_height / 2.0
        self.prev_norm_x: Optional[float] = None
        self.prev_norm_y: Optional[float] = None
        self.last_update_time: float = time.time()

        # Interaction state
        self.is_dragging: bool = False
        self.last_click_time: float = 0.0
        self.pinch_start_time: float = 0.0

    def update_settings(self, smoothing: float, dead_zone: float, speed: float) -> None:
        self.smoothing = max(0.05, min(0.95, smoothing))
        self.dead_zone = max(0.001, min(0.1, dead_zone))
        self.speed_factor = max(0.5, min(4.0, speed))

    def set_active_box(self, active_box: Optional[Tuple[float, float, float, float]]) -> None:
        """
        Sets the reachable region of the camera frame, expressed normalised.

        A malformed or degenerate box is ignored rather than allowed to send the
        cursor to a corner it can never leave, which would look like a frozen
        pointer to the user.
        """
        if not active_box:
            self.active_box = (0.0, 0.0, 1.0, 1.0)
            return
        try:
            left, top, right, bottom = (float(v) for v in active_box)
        except (TypeError, ValueError):
            return
        left = max(0.0, min(1.0, left))
        top = max(0.0, min(1.0, top))
        right = max(0.0, min(1.0, right))
        bottom = max(0.0, min(1.0, bottom))
        if (right - left) < 1e-3 or (bottom - top) < 1e-3:
            return
        self.active_box = (left, top, right, bottom)

    def remap_to_active_box(self, norm_x: float, norm_y: float) -> Tuple[float, float]:
        """
        Stretches the reachable region across the whole screen.

        Without this the user would have to physically stretch towards the edge
        of the webcam frame to reach the edge of the monitor; after calibration
        their comfortable reach is the full screen.
        """
        left, top, right, bottom = self.active_box
        if (left, top, right, bottom) == (0.0, 0.0, 1.0, 1.0):
            return norm_x, norm_y
        return (
            (norm_x - left) / (right - left),
            (norm_y - top) / (bottom - top),
        )

    def map_normalized_to_screen(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """
        Maps normalized camera coordinates (0.0 to 1.0)
        to smoothed screen pixel coordinates with deadzone filtering and acceleration.
        """
        # Frame is already mirrored horizontally by CameraStream
        norm_x, norm_y = self.remap_to_active_box(norm_x, norm_y)
        target_norm_x = norm_x

        if self.prev_norm_x is None:
            self.prev_norm_x = target_norm_x
            self.prev_norm_y = norm_y
            self.smooth_x = target_norm_x * self.screen_width
            self.smooth_y = norm_y * self.screen_height
            # The calibrated reach box maps its own corners to exactly 0.0 and
            # 1.0, so the first frame has to be clamped like every other one.
            return (
                max(0, min(self.screen_width - 1, int(self.smooth_x))),
                max(0, min(self.screen_height - 1, int(self.smooth_y))),
            )

        # Calculate displacement in normalized space
        dx = target_norm_x - self.prev_norm_x
        dy = norm_y - self.prev_norm_y
        dist = math.hypot(dx, dy)

        # Deadzone filter: if displacement is minuscule (tremor/jitter), ignore it
        if dist < self.dead_zone:
            target_norm_x = self.prev_norm_x
            norm_y = self.prev_norm_y
        else:
            # Dynamic acceleration: small movements move slightly slower for fine accuracy,
            # larger intentional sweeps accelerate across screen
            accel = 1.0 + min(1.5, dist * 8.0)
            dx = dx * self.speed_factor * accel
            dy = dy * self.speed_factor * accel
            target_norm_x = self.prev_norm_x + dx
            norm_y = self.prev_norm_y + dy

        # Clamp normalized coords
        target_norm_x = max(0.0, min(1.0, target_norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        # Target screen position
        target_x = target_norm_x * self.screen_width
        target_y = norm_y * self.screen_height

        # Exponential Moving Average (EMA) smoothing
        self.smooth_x = (self.smoothing * self.smooth_x) + ((1.0 - self.smoothing) * target_x)
        self.smooth_y = (self.smoothing * self.smooth_y) + ((1.0 - self.smoothing) * target_y)

        # Screen boundary clamping
        screen_x = max(0, min(self.screen_width - 1, int(self.smooth_x)))
        screen_y = max(0, min(self.screen_height - 1, int(self.smooth_y)))

        self.prev_norm_x = target_norm_x
        self.prev_norm_y = norm_y
        self.last_update_time = time.time()

        return screen_x, screen_y

    def reset(self) -> None:
        self.prev_norm_x = None
        self.prev_norm_y = None
        self.is_dragging = False
