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
        # Allow natural foreshortening for index finger when pointing towards camera
        ratio = 1.04 if tip_idx == 8 else 1.15
        return d_tip > (d_pip * ratio)

    def _is_thumb_extended(self) -> bool:
        """Determines if thumb is extended relative to CMC/MCP joints."""
        tip = self.thumb_tip
        ip = self.thumb_ip
        wrist = self.wrist
        d_tip = math.hypot(tip[0] - wrist[0], tip[1] - wrist[1])
        d_ip = math.hypot(ip[0] - wrist[0], ip[1] - wrist[1])
        return d_tip > (d_ip * 1.10)


from vision.filters import HandLandmarksSmoother


class HandLandmarksData:
    """Encapsulates geometric state of detected hand landmarks with smoothing and diagnostics."""

    def __init__(
        self,
        raw_landmarks,
        image_width: int,
        image_height: int,
        smoothed_points: Optional[List[Tuple[float, float, float]]] = None,
        handedness: str = "Right"
    ):
        self.raw_landmarks = raw_landmarks
        self.width = image_width
        self.height = image_height
        self.handedness = handedness

        # Raw points
        self.raw_points: List[Tuple[float, float, float]] = [
            (lm.x, lm.y, lm.z) for lm in raw_landmarks.landmark
        ]

        # Normalized points (smoothed if available, else raw)
        if smoothed_points and len(smoothed_points) == 21:
            self.normalized_points = smoothed_points
        else:
            self.normalized_points = self.raw_points

        # List of 21 pixel coordinates (px_x, px_y) from smoothed points
        self.pixel_points: List[Tuple[int, int]] = [
            (int(pt[0] * image_width), int(pt[1] * image_height)) for pt in self.normalized_points
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

        # Bounding box calculation in normalized coords (0.0 to 1.0)
        xs = [pt[0] for pt in self.normalized_points]
        ys = [pt[1] for pt in self.normalized_points]
        self.bbox_norm = (min(xs), min(ys), max(xs), max(ys))
        self.is_partially_out_of_frame = (
            self.bbox_norm[0] < 0.03 or self.bbox_norm[2] > 0.97 or
            self.bbox_norm[1] < 0.03 or self.bbox_norm[3] > 0.97
        )

        # Hand span (wrist to middle finger tip distance)
        self.hand_span = math.hypot(
            self.wrist[0] - self.middle_tip[0],
            self.wrist[1] - self.middle_tip[1]
        )

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
        # Allow natural foreshortening for index finger when pointing towards camera
        ratio = 1.04 if tip_idx == 8 else 1.15
        return d_tip > (d_pip * ratio)

    def _is_thumb_extended(self) -> bool:
        """Determines if thumb is extended relative to CMC/MCP joints."""
        tip = self.thumb_tip
        ip = self.thumb_ip
        wrist = self.wrist
        d_tip = math.hypot(tip[0] - wrist[0], tip[1] - wrist[1])
        d_ip = math.hypot(ip[0] - wrist[0], ip[1] - wrist[1])
        return d_tip > (d_ip * 1.10)


class GestureDetector:
    """Initializes and runs MediaPipe Hands to extract robust hand landmark data with One-Euro smoothing."""

    def __init__(
        self,
        static_image_mode: bool = False,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.45,
        min_tracking_confidence: float = 0.40,
        enable_smoothing: bool = True,
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
        self.enable_smoothing = enable_smoothing
        self.smoother = HandLandmarksSmoother(min_cutoff=1.1, beta=0.007)

    def reset_smoother(self) -> None:
        self.smoother.reset()

    def process_frame(self, frame_bgr: np.ndarray) -> Optional[HandLandmarksData]:
        """Processes BGR frame from webcam and returns HandLandmarksData if detected."""
        h, w, _ = frame_bgr.shape
        # MediaPipe expects RGB
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        results = self.hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            first_hand = results.multi_hand_landmarks[0]
            handedness = "Right"
            if results.multi_handedness:
                try:
                    handedness = results.multi_handedness[0].classification[0].label
                except Exception:
                    pass

            raw_pts = [(lm.x, lm.y, lm.z) for lm in first_hand.landmark]
            if self.enable_smoothing:
                smoothed_pts = self.smoother.smooth(raw_pts)
            else:
                smoothed_pts = raw_pts

            return HandLandmarksData(first_hand, w, h, smoothed_pts, handedness)

        self.smoother.reset()
        return None

    def draw_skeleton(
        self,
        frame_bgr: np.ndarray,
        landmarks_data: HandLandmarksData,
        gesture_name: str = "",
        confidence: float = 1.0,
        is_armed: bool = True,
        progress: float = 0.0,
        diagnostic_text: str = "",
    ) -> np.ndarray:
        """Draws aesthetic futuristic skeleton, joints, arming status, and HUD overlay on the frame."""
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

        # If a gesture hold or arming hold is in progress, draw a ring around fingertip
        if 0.0 < progress < 1.0:
            radius = 16
            axes = (radius, radius)
            angle = 0
            startAngle = -90
            endAngle = -90 + int(progress * 360)
            cv2.ellipse(frame_bgr, idx_px, axes, angle, startAngle, endAngle, (0, 240, 255), 3)

        # HUD Overlay Box Top-Left
        badge_w = 340
        badge_h = 60
        cv2.rectangle(frame_bgr, (14, 14), (14 + badge_w, 14 + badge_h), (16, 20, 26), -1)
        border_color = (0, 220, 160) if is_armed else (0, 140, 255)
        cv2.rectangle(frame_bgr, (14, 14), (14 + badge_w, 14 + badge_h), border_color, 1)

        # Arming status tag
        arm_tag = "[ARMED]" if is_armed else "[STANDBY / UNARMED]"
        arm_color = (80, 255, 150) if is_armed else (70, 160, 255)
        cv2.putText(
            frame_bgr,
            arm_tag,
            (24, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            arm_color,
            1,
            cv2.LINE_AA
        )

        # Gesture label & confidence
        if gesture_name and gesture_name != "NONE":
            g_label = f"{gesture_name} ({int(confidence * 100)}%)"
        elif diagnostic_text:
            g_label = diagnostic_text
        else:
            g_label = "Ready" if is_armed else "Palm 1s to arm"

        cv2.putText(
            frame_bgr,
            g_label,
            (24, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (240, 245, 250),
            1,
            cv2.LINE_AA
        )

        # Progress bar at bottom of badge
        if progress > 0.0:
            bar_y = 14 + badge_h - 4
            fill_w = int(badge_w * min(1.0, progress))
            cv2.rectangle(frame_bgr, (14, bar_y), (14 + fill_w, bar_y + 3), (0, 230, 255), -1)

        return frame_bgr
