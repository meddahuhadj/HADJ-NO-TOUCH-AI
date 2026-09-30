import os
import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
import pyautogui

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ScreenUnderstandingEngine:
    """Analyzes the Windows screen locally to detect interactive UI elements (buttons, inputs, close X, text)."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ScreenUnderstandingEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.screen_width, self.screen_height = pyautogui.size()

    def capture_screen_np(self) -> np.ndarray:
        """Takes full screen snapshot and returns BGR numpy array."""
        pil_img = pyautogui.screenshot()
        rgb = np.array(pil_img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def locate_active_window_close_button(self) -> Optional[Tuple[int, int]]:
        """Calculates precise screen coordinates of the active window's 'X' close button."""
        if not HAS_WIN32:
            # Fallback to top-right corner of screen
            return (self.screen_width - 25, 15)

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (self.screen_width - 25, 15)

        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        win_w = right - left
        win_h = bottom - top

        if win_w <= 0 or win_h <= 0:
            return (self.screen_width - 25, 15)

        # In standard Windows 10/11 windows, the Close 'X' button is located ~25px from right, ~15px from top
        close_x = right - 25
        close_y = top + 15
        return (close_x, close_y)

    def detect_clickable_elements(self, max_elements: int = 20) -> List[Dict[str, Any]]:
        """
        Uses OpenCV contour detection to locate rectangular buttons, input boxes, and cards on screen.
        Returns bounding boxes with center points.
        """
        frame = self.capture_screen_np()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Canny edge detection
        edges = cv2.Canny(gray, 50, 150)
        # Dilate edges to connect boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        found_elements = []
        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                # Filter for typical UI button or input box sizes
                if 40 <= w <= 500 and 20 <= h <= 120:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    found_elements.append({
                        "type": "BUTTON_OR_INPUT",
                        "bbox": (x, y, w, h),
                        "center": (center_x, center_y),
                        "confidence": 0.85
                    })
                    if len(found_elements) >= max_elements:
                        break

        return found_elements

    def find_text_on_screen(self, target_text: str) -> Optional[Tuple[int, int]]:
        """
        Searches screen for a specific text string using local OCR (if Tesseract binary is configured)
        or returns closest UI element match.
        """
        if not HAS_PYTESSERACT:
            return None

        try:
            pil_img = pyautogui.screenshot()
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            n_boxes = len(data['text'])
            target_lower = target_text.strip().lower()

            for i in range(n_boxes):
                text = data['text'][i].strip().lower()
                if target_lower in text:
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    return (x, y)
        except Exception as e:
            print(f"[ScreenUnderstanding] OCR query notice: {e}")

        return None
