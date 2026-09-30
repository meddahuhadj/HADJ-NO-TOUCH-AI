import math
from typing import List, Dict, Any, Optional, Tuple
import cv2
import mediapipe as mp
import numpy as np


class HandLandmarksData:
    """Encapsulates geometric state of detected hand landmarks."""

    def __init__(self, raw_landmarks, image_width: int, image_height: int):
        self.raw_landmarks = raw_landmarks
        self.width = image_width
        self.height = image_height

        # List of 21 (norm_x, norm_y, norm_z)
        self.normalized_points: List[Tuple[float, float, float]] = [
            (lm.x, lm.y, lm.z) for lm in raw_landmarks.landmark
        ]

        # List of 21 pixel coordinates (px_x, px_y)
        self.pixel_points: List[Tuple[int, int]] = [
            (int(lm.x * image_width), int(lm.y * image_height)) for lm in raw_landmarks.landmark
        ]

        # Finger tip positions
        self.thumb_tip = self.normalized_points[4]
        self.index_tip = self.normalized_points[8]
        self.middle_tip = self.normalized_points[12]
        self.ring_tip = self.normalized_points[16]
        self.pinky_tip = self.normalized_points[20]

        # Finger MCP/pip joints
        self.thumb_ip = self.normalized_points[3]
        self.index_pip = self.normalized_points[6]
        self.middle_pip = self.normalized_points[10]
        self.ring_pip = self.normalized_points[14]
        self.pinky_pip = self.normalized_points[18]
        self.wrist = self.normalized_points[0]

        # Finger extended flags
        self.index_extended = self._is_finger_extended(8, 6, 0)
        self.middle_extended = self._is_finger_extended(12, 10, 0)
        self.ring_extended = self._is_finger_extended(16, 14, 0)
        self.pinky_extended = self._is_finger_extended(20, 18, 0)
        self.thumb_extended = self._is_thumb_extended()

        # Distances
        self.pinch_distance = math.hypot(
            self.thumb_tip[0] - self.index_tip[0],
            self.thumb_tip[1] - self.index_tip[1]
        )
        self.thumb_middle_distance = math.hypot(
            self.thumb_tip[0] - self.middle_tip[0],
            self.thumb_tip[1] - self.middle_tip[1]
        )

    def _is_finger_extended(self, tip_idx: int, pip_idx: int, wrist_idx: int = 0) -> bool:
        """A finger is extended if distance from wrist to tip is greater than wrist to pip."""
        tip = self.normalized_points[tip_idx]
        pip = self.normalized_points[pip_idx]
        wrist = self.normalized_points[wrist_idx]

        d_tip = math.hypot(tip[0] - wrist[0], tip[1] - wrist[1])
        d_pip = math.hypot(pip[0] - wrist[0], pip[1] - wrist[1])
        return d_tip > (d_pip * 1.15)

    def _is_thumb_extended(self) -> bool:
        """Determines if thumb is extended relative to CMC/MCP joints."""
        tip = self.thumb_tip
        ip = self.thumb_ip
        wrist = self.wrist
        d_tip = math.hypot(tip[0] - wrist[0], tip[1] - wrist[1])
        d_ip = math.hypot(ip[0] - wrist[0], ip[1] - wrist[1])
        return d_tip > (d_ip * 1.10)


class GestureDetector:
    """Initializes and runs MediaPipe Hands to extract robust hand landmark data."""

    def __init__(
        self,
        static_image_mode: bool = False,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.65,
        min_tracking_confidence: float = 0.60
    ):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def process_frame(self, frame_bgr: np.ndarray) -> Optional[HandLandmarksData]:
        """Processes BGR frame from webcam and returns HandLandmarksData if detected."""
        h, w, _ = frame_bgr.shape
        # MediaPipe expects RGB
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        results = self.hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            first_hand = results.multi_hand_landmarks[0]
            return HandLandmarksData(first_hand, w, h)
        return None

    def draw_skeleton(
        self,
        frame_bgr: np.ndarray,
        landmarks_data: HandLandmarksData,
        gesture_name: str = "",
        confidence: float = 1.0
    ) -> np.ndarray:
        """Draws aesthetic futuristic skeleton, joints, and HUD overlay on the frame."""
        h, w, _ = frame_bgr.shape

        # Draw native MediaPipe connections with custom neon colors
        self.mp_draw.draw_landmarks(
            frame_bgr,
            landmarks_data.raw_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_draw.DrawingSpec(color=(0, 255, 230), thickness=2, circle_radius=3),
            self.mp_draw.DrawingSpec(color=(30, 200, 255), thickness=2, circle_radius=2),
        )

        # Draw glowing pointer circle on index fingertip
        idx_px = landmarks_data.pixel_points[8]
        cv2.circle(frame_bgr, idx_px, 10, (0, 255, 255), 2)
        cv2.circle(frame_bgr, idx_px, 4, (0, 255, 120), -1)

        # Draw HUD badge top-left
        if gesture_name:
            label = f"GESTURE: {gesture_name} ({int(confidence * 100)}%)"
            # Semi-transparent HUD pill
            cv2.rectangle(frame_bgr, (15, 15), (320, 52), (18, 22, 28), -1)
            cv2.rectangle(frame_bgr, (15, 15), (320, 52), (0, 220, 180), 1)
            cv2.putText(
                frame_bgr,
                label,
                (25, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (230, 255, 250),
                1,
                cv2.LINE_AA
            )

        return frame_bgr
