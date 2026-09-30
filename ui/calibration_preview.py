"""
Live camera preview used by the calibration wizard.

The wizard has to open a camera of its own: the main vision pipeline may be
using a different index, may not be running at all yet, and the guided routine
must be able to pick a device the user has just selected. Capturing and running
MediaPipe happens on a worker thread, and only immutable snapshots cross back to
the GUI thread, so the dialog never blocks and never touches a capture object
from the wrong thread.

The preview doubles as the measurement surface: it draws the calibrated reach
window, the live pinch distance against the current threshold, and a per-frame
hand trace, which is what makes an abstract threshold feel concrete.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui import theme

PREVIEW_SIZE = (420, 315)


class CalibrationPreviewWorker(QObject):
    """
    Captures frames and runs hand detection on a background thread.

    Emits :attr:`frame_ready` with a rendered BGR frame and :attr:`landmarks`
    with a plain snapshot of the geometry the calibration maths needs. Nothing
    else is shared, so there is no lock to get wrong.
    """

    frame_ready = Signal(object)          # ndarray BGR, already annotated
    landmarks = Signal(object)            # HandSnapshot or None
    failed = Signal(str)
    finished = Signal()

    def __init__(self, camera_index: int, width: int = 640, height: int = 480):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self._running = False
        self._detector = None

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        capture = None
        try:
            try:
                from vision.gesture_detector import GestureDetector
                self._detector = GestureDetector()
            except Exception as error:
                self.failed.emit(str(error))
                return

            try:
                capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                if not capture.isOpened():
                    capture.release()
                    capture = cv2.VideoCapture(self.camera_index)
            except Exception:
                capture = None

            if capture is None or not capture.isOpened():
                self.failed.emit("camera")
                return

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            while self._running:
                grabbed, frame = capture.read()
                if not grabbed or frame is None:
                    time.sleep(0.03)
                    continue

                # Mirrored so moving right moves the cursor right.
                frame = cv2.flip(frame, 1)
                snapshot = None
                try:
                    data = self._detector.process_frame(frame)
                except Exception:
                    data = None

                if data is not None:
                    snapshot = HandSnapshot(
                        index_tip=(float(data.index_tip[0]), float(data.index_tip[1])),
                        pinch_distance=float(data.pinch_distance),
                        landmarks=data.pixel_points,
                    )
                    frame = self._detector.draw_skeleton(frame, data, "", 0.0)

                self.frame_ready.emit(frame)
                self.landmarks.emit(snapshot)

        except Exception as error:  # pragma: no cover - hardware dependent
            self.failed.emit(str(error))
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
            self._running = False
            self.finished.emit()


class HandSnapshot:
    """Immutable hand geometry handed from the worker to the GUI thread."""

    __slots__ = ("index_tip", "pinch_distance", "landmarks")

    def __init__(self, index_tip: Tuple[float, float], pinch_distance: float, landmarks):
        self.index_tip = index_tip
        self.pinch_distance = pinch_distance
        self.landmarks = landmarks


class CalibrationPreview(QWidget):
    """
    Renders the annotated camera feed with the live measurement overlays.
    """

    #: Re-emitted per camera frame so a listener can measure at full frame
    #: rate instead of polling ``snapshot`` on a timer.
    landmarks = Signal(object)  # HandSnapshot or None

    def __init__(self, parent=None, show_trace: bool = True):
        super().__init__(parent)
        self._show_trace = show_trace
        self._frame = None
        self._snapshot: Optional[HandSnapshot] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[CalibrationPreviewWorker] = None

        # Measurement overlays driven by the wizard.
        self.active_box: Optional[Tuple[float, float, float, float]] = None
        self.pinch_threshold: Optional[float] = None
        self.pinch_armed = False

        self._trace: list = []
        self._fps = 0.0
        self._fps_mark = time.time()
        self._fps_frames = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(*PREVIEW_SIZE)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setStyleSheet(
            f"QLabel {{ background-color: {theme.CANVAS_DEEP};"
            f" border: 1px solid {theme.BORDER}; border-radius: {theme.RADIUS_LG}px; }}"
        )
        layout.addWidget(self.image_label)

        self._paint_idle()

    # ------------------------------------------------------------------ #
    # Capture lifecycle
    # ------------------------------------------------------------------ #

    def start(self, camera_index: int) -> None:
        """Opens ``camera_index`` on a worker thread and starts streaming."""
        self.stop()
        self._trace.clear()
        self._frame = None
        self._snapshot = None

        self._thread = QThread(self)
        self._worker = CalibrationPreviewWorker(camera_index)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.landmarks.connect(self._on_landmarks)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def stop(self) -> None:
        """Stops the worker and waits for the capture to be released."""
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2500)
        self._worker = None
        self._thread = None
        self._snapshot = None
        self._trace.clear()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def has_hand(self) -> bool:
        return self._snapshot is not None

    @property
    def snapshot(self) -> Optional["HandSnapshot"]:
        """The most recent hand geometry, or ``None`` when tracking was lost."""
        return self._snapshot

    @property
    def fps(self) -> float:
        return self._fps

    # ------------------------------------------------------------------ #
    # Frame intake
    # ------------------------------------------------------------------ #

    def _on_frame(self, frame) -> None:
        self._frame = frame
        self._fps_frames += 1
        now = time.time()
        if now - self._fps_mark >= 0.5:
            self._fps = self._fps_frames / (now - self._fps_mark)
            self._fps_mark = now
            self._fps_frames = 0
        self._repaint()

    def _on_landmarks(self, snapshot) -> None:
        self._snapshot = snapshot
        if snapshot is not None and self._show_trace:
            self._trace.append(snapshot.index_tip)
            if len(self._trace) > 90:
                del self._trace[:-90]
        elif snapshot is None:
            self._trace.clear()
        self.landmarks.emit(snapshot)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _target_size(self) -> Tuple[int, int]:
        size = self.image_label.size()
        if size.width() <= 1 or size.height() <= 1:
            return PREVIEW_SIZE
        return size.width(), size.height()

    def _paint_idle(self) -> None:
        width, height = PREVIEW_SIZE
        pix = QPixmap(width, height)
        pix.fill(QColor(theme.CANVAS_DEEP))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        inner = pix.rect().adjusted(14, 14, -14, -14)
        painter.setPen(QPen(QColor(theme.BORDER_STRONG), 1, Qt.DashLine))
        painter.drawRoundedRect(inner, theme.RADIUS_MD, theme.RADIUS_MD)
        painter.setPen(QColor(theme.TEXT_FAINT))
        painter.drawText(inner, Qt.AlignCenter, "—")
        painter.end()
        self.image_label.setPixmap(pix)

    def _repaint(self) -> None:
        frame = self._frame
        if frame is None:
            return

        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data, width, height, frame.shape[2] * width, QImage.Format_RGB888
        ).copy()
        pixmap = QPixmap.fromImage(image)

        target = self._target_size()
        pixmap = pixmap.scaled(target[0], target[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_overlays(painter, pixmap.width(), pixmap.height(), width, height)
        painter.end()

        self.image_label.setPixmap(pixmap)

    def _draw_overlays(
        self, painter: QPainter, view_w: int, view_h: int, frame_w: int, frame_h: int
    ) -> None:
        """Draws the reach window, the motion trace and the pinch gauge."""
        if frame_w <= 0 or frame_h <= 0:
            return
        scale_x = view_w / float(frame_w)
        scale_y = view_h / float(frame_h)

        if self.active_box is not None:
            left, top, right, bottom = self.active_box
            painter.setPen(QPen(QColor(theme.VIOLET), 2, Qt.DashLine))
            painter.drawRect(
                int(left * view_w), int(top * view_h),
                int((right - left) * view_w), int((bottom - top) * view_h),
            )

        if self._trace and len(self._trace) > 1:
            pen = QPen(QColor(theme.alpha(theme.ACCENT, 150)), 2)
            painter.setPen(pen)
            points = [
                (int(x * view_w), int(y * view_h)) for (x, y) in self._trace
            ]
            for index in range(1, len(points)):
                painter.drawLine(points[index - 1], points[index])

        if self._snapshot is not None:
            tip_x = int(self._snapshot.index_tip[0] * view_w)
            tip_y = int(self._snapshot.index_tip[1] * view_h)
            painter.setPen(QPen(QColor(theme.ACCENT), 2))
            painter.setBrush(QColor(theme.alpha(theme.ACCENT, 70)))
            painter.drawEllipse(tip_x, tip_y, 14, 14)

        painter.setPen(QColor(theme.TEXT_MUTED))
        painter.drawText(
            10, view_h - 10, f"{self._fps:.0f} FPS"
        )

        if self.pinch_threshold:
            self._draw_pinch_gauge(painter, view_w, view_h)

    def _draw_pinch_gauge(self, painter: QPainter, view_w: int, view_h: int) -> None:
        """
        A vertical gauge showing the live pinch distance against the threshold.

        The threshold line is the whole point: the user watches the bar cross it
        on a real pinch, which is far more convincing than reading a number.
        """
        gauge_w = 12
        gauge_h = min(150, view_h - 40)
        left = view_w - gauge_w - 16
        top = view_h - gauge_h - 24

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.alpha(theme.CANVAS_DEEP, 200)))
        painter.drawRoundedRect(left - 4, top - 4, gauge_w + 8, gauge_h + 8, 6, 6)

        span = 0.14  # covers the plausible normalised pinch-distance range
        distance = self._snapshot.pinch_distance if self._snapshot else 0.0
        fill = max(0.0, min(1.0, distance / span))
        bar_h = int(fill * gauge_h)

        active = self.pinch_armed and distance < (self.pinch_threshold or 0.0)
        painter.setBrush(QColor(theme.SUCCESS if active else theme.ACCENT))
        painter.drawRoundedRect(left, top + gauge_h - bar_h, gauge_w, max(bar_h, 2), 4, 4)

        threshold = max(0.0, min(1.0, (self.pinch_threshold or 0.0) / span))
        line_y = top + gauge_h - int(threshold * gauge_h)
        painter.setPen(QPen(QColor(theme.WARNING), 2))
        painter.drawLine(left - 6, line_y, left + gauge_w + 6, line_y)
