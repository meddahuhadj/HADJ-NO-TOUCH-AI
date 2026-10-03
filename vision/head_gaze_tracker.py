import time
import math
from typing import Optional, Tuple, Dict, Any
import numpy as np
import cv2
import mediapipe as mp


class HeadGazeTracker:
    """Detects head poses (tilt, nod, shake) and gaze dwell points using MediaPipe Face Mesh."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = None

        if self.enabled:
            self._init_mesh()

        # Calibration & thresholds
        self.nod_threshold: float = 0.025
        self.shake_threshold: float = 0.035
        self.dwell_time_threshold: float = 1.0

        # State tracking
        self.prev_nose_y: Optional[float] = None
        self.prev_nose_x: Optional[float] = None
        self.dwell_start_time: float = 0.0
        self.last_dwell_pos: Optional[Tuple[int, int]] = None
        self.blink_counter: int = 0

    def _init_mesh(self):
        try:
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except Exception as e:
            print(f"[HeadGazeTracker] Face mesh init notice: {e}")
            self.face_mesh = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled and self.face_mesh is None:
            self._init_mesh()

    def process_frame(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        """Analyzes face landmarks to estimate head pose, nod, shake, and dwell state."""
        if not self.enabled or self.face_mesh is None:
            return {"active": False}

        h, w, _ = frame_bgr.shape
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        res = self.face_mesh.process(rgb)

        if not res.multi_face_landmarks:
            return {"active": False}

        face = res.multi_face_landmarks[0]
        # Nose tip landmark index is 1
        nose_lm = face.landmark[1]
        nx, ny = nose_lm.x, nose_lm.y

        action = "NONE"
        now = time.time()

        if self.prev_nose_y is not None and self.prev_nose_x is not None:
            dy = ny - self.prev_nose_y
            dx = nx - self.prev_nose_x

            # Nod: rapid downward then upward motion in Y
            if abs(dy) > self.nod_threshold:
                action = "HEAD_NOD"
            elif abs(dx) > self.shake_threshold:
                action = "HEAD_SHAKE"

        self.prev_nose_y = ny
        self.prev_nose_x = nx

        # Eye Iris landmarks (MediaPipe Face Mesh refine_landmarks=True has iris 468, 473)
        iris_center = (int(nx * w), int(ny * h))

        # Check dwell trigger
        dwell_triggered = False
        if self.last_dwell_pos:
            dist = math.hypot(iris_center[0] - self.last_dwell_pos[0], iris_center[1] - self.last_dwell_pos[1])
            if dist < 20:  # Stayed within 20px radius
                if (now - self.dwell_start_time) >= self.dwell_time_threshold:
                    dwell_triggered = True
                    self.dwell_start_time = now + 1.0  # Reset
            else:
                self.last_dwell_pos = iris_center
                self.dwell_start_time = now
        else:
            self.last_dwell_pos = iris_center
            self.dwell_start_time = now

        return {
            "active": True,
            "nose_norm": (nx, ny),
            "action": action,
            "dwell_triggered": dwell_triggered,
            "dwell_progress": min(1.0, (now - self.dwell_start_time) / self.dwell_time_threshold) if self.last_dwell_pos else 0.0
        }
