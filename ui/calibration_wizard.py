"""
Guided automatic calibration wizard.

Every step measures something. The user is never asked to type or drag a
threshold: HADJ probes the hardware, watches the hand, and derives the numbers
from percentiles of what it observed. Steps that could not be measured are
reported as such and keep the previous value rather than inventing one.

Device scanning, camera timing and microphone capture all block, so they run on
worker threads; the camera feed and the hand snapshot arrive back as signals and
all calibration state stays on the GUI thread.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QStackedWidget, QVBoxLayout, QWidget,
)

import config.i18n as i18n
from config.i18n import tr
from config.settings_manager import SettingsManager
from core.auto_calibration import (
    AdaptiveTuner, CalibrationPhase, CalibrationReport, CalibrationSession,
    HandSample, MicrophoneProbe, begin_device_scan, end_device_scan,
    measure_camera_timing, probe_cameras, probe_microphones,
)
from ui import theme
from ui import widgets as W
from ui.calibration_preview import CalibrationPreview

TOTAL_STEPS = 8

STEP_DEVICES, STEP_CAMERA, STEP_MIC, STEP_HAND, \
    STEP_PINCH, STEP_REACH, STEP_ADAPTIVE, STEP_SUMMARY = range(TOTAL_STEPS)

#: Pinches the user performs during the sensitivity step.
TARGET_PINCHES = 3

#: Frames collected while measuring the comfortable reach (~5 s at 30 FPS).
TARGET_REACH_FRAMES = 150

#: Pixels the reach must span before the measurement is trusted.
MIN_REACH_SPAN = 0.18


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class _Task(QObject):
    """
    Runs one blocking call off the GUI thread and returns its result.

    A plain daemon thread is used on purpose rather than a ``QThread``: closing
    the wizard while a camera scan is still in flight would destroy a running
    ``QThread`` and abort the process. A Python thread is simply left to finish
    and, being a daemon, never holds up interpreter shutdown. Results still
    reach the GUI thread through a queued signal connection.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[], Any]):
        super().__init__()
        self._func = func
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "_Task":
        self._thread.start()
        return self

    def _run(self) -> None:
        try:
            result = self._func()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(result)


class _Text:
    """Binds a label's text to an i18n key so a language switch re-resolves it."""

    def __init__(self, widget: QLabel, key: str, **fmt: Any):
        self.widget = widget
        self.key = key
        self.fmt = fmt

    def apply(self) -> None:
        self.widget.setText(tr(self.key, **self.fmt))


class _Page:
    """A wizard page plus the labels that must follow the interface language."""

    def __init__(self, title_key: str, desc_key: str, accent: str):
        self.title_key = title_key
        self.desc_key = desc_key
        self.accent = accent
        self.card: Optional[QWidget] = None
        self.layout: Optional[QVBoxLayout] = None
        self.heading: Optional[QLabel] = None
        self.body: Optional[QLabel] = None
        self.texts: List[_Text] = []

    def retranslate(self) -> None:
        self.heading.setText(tr(self.title_key))
        self.heading.setStyleSheet(
            f"color: {self.accent}; font-size: 18px; font-weight: 700;"
        )
        self.body.setText(tr(self.desc_key) if self.desc_key else "")
        self.body.setVisible(bool(self.desc_key))
        for item in self.texts:
            item.apply()


# --------------------------------------------------------------------------- #
# Dialog
# --------------------------------------------------------------------------- #

class CalibrationWizardDialog(QDialog):
    """Eight-step wizard that measures the camera, the microphone and the hand."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(720, 660)
        self.settings = SettingsManager()
        self.current_step = STEP_DEVICES

        # Measurement state
        self.session: Optional[CalibrationSession] = None
        self.report = CalibrationReport()
        self.cameras: List[Any] = []
        self.microphones: List[Any] = []
        self.camera_timing: Dict[str, float] = {}
        self.mic_levels: Dict[str, float] = {}
        self.live_tuner: Optional[AdaptiveTuner] = None
        self.measured_steps: set = set()

        # Async plumbing
        self._task: Optional[_Task] = None

        theme.apply_to(self)
        self._build_ui()
        self._build_pages()
        self._start_device_scan()
        self._tick = QTimer(self)
        self._tick.setInterval(90)
        self._tick.timeout.connect(self._on_tick)
        # Samples must be taken per camera frame: at a 30 FPS feed the timer
        # below would only see every third frame, which both shortens the reach
        # routine and quantises the measured pinch timing to 90 ms.
        self.preview.landmarks.connect(self._on_preview_landmarks)

        i18n.on_language_changed(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.PAD + 4, theme.PAD + 4, theme.PAD + 4, theme.PAD + 4
        )
        root.setSpacing(theme.GAP)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, TOTAL_STEPS)
        self.progress_bar.setValue(1)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        root.addWidget(self.progress_bar)

        self.step_label = W.label(self, "", "sectionTitle")
        root.addWidget(self.step_label)

        self.stacked_pages = QStackedWidget(self)
        root.addWidget(self.stacked_pages, 1)

        # The preview is one widget re-used across the camera, hand, pinch and
        # reach steps: reopening a capture handle on every step is slow on
        # Windows and occasionally fails outright.
        self.preview = CalibrationPreview(self)
        self.preview.setVisible(False)
        root.addWidget(self.preview)

        self.status_label = W.label(self, "", "faint", wrap=True)
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        nav = W.hbox()
        self.back_btn = W.button(self, "", "ghost", self._prev_step)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        nav.addWidget(self.back_btn)
        nav.addWidget(W.spacer())
        self.measure_btn = W.button(self, "", "primary", self._on_measure)
        self.measure_btn.setCursor(Qt.PointingHandCursor)
        self.measure_btn.setVisible(False)
        nav.addWidget(self.measure_btn)
        self.next_btn = W.button(self, "", "primary", self._next_step)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setMinimumWidth(132)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

    def _new_page(self, title_key: str, desc_key: str, accent: str) -> _Page:
        page = _Page(title_key, desc_key, accent)
        page.card = W.frame(self, "card")
        lay = QVBoxLayout(page.card)
        lay.setContentsMargins(
            theme.PAD + 2, theme.PAD + 2, theme.PAD + 2, theme.PAD + 2
        )
        lay.setSpacing(10)
        page.layout = lay
        page.heading = W.label(page.card, "", "pageTitle", wrap=True)
        page.body = W.label(page.card, "", "muted", wrap=True)
        lay.addWidget(page.heading)
        lay.addWidget(page.body)
        self.stacked_pages.addWidget(page.card)
        return page

    def _build_pages(self) -> None:
        self.pages: List[_Page] = []
        for spec in (
            ("calib.step_devices", "calib.step_devices_desc", theme.ACCENT),
            ("calib.step_camera", "calib.step_camera_desc", theme.ACCENT),
            ("calib.step_mic", "calib.step_mic_desc", theme.SUCCESS),
            ("calib.step_hand", "calib.step_hand_desc", theme.ACCENT),
            ("calib.step_pinch", "calib.step_pinch_desc", theme.VIOLET),
            ("calib.step_reach", "calib.step_reach_desc", theme.VIOLET),
            ("calib.step_adaptive", "calib.step_adaptive_desc", theme.SUCCESS),
            ("calib.step_summary", "calib.step_summary_desc", theme.SUCCESS),
        ):
            self.pages.append(self._new_page(*spec))

        self._fill_devices(self.pages[STEP_DEVICES])
        self._fill_camera(self.pages[STEP_CAMERA])
        self._fill_mic(self.pages[STEP_MIC])
        self._fill_hand(self.pages[STEP_HAND])
        self._fill_pinch(self.pages[STEP_PINCH])
        self._fill_reach(self.pages[STEP_REACH])
        self._fill_adaptive(self.pages[STEP_ADAPTIVE])
        self._fill_summary(self.pages[STEP_SUMMARY])

    # -- step bodies ------------------------------------------------------- #

    def _fill_devices(self, page: _Page) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.GAP)
        grid.setVerticalSpacing(8)

        self.camera_label = W.label(page.card, "", "faint")
        self.mic_label = W.label(page.card, "", "faint")
        page.texts.append(_Text(self.camera_label, "calib.device_camera"))
        page.texts.append(_Text(self.mic_label, "calib.device_microphone"))

        self.camera_combo = QComboBox(page.card)
        self.mic_combo = QComboBox(page.card)
        self.camera_combo.currentIndexChanged.connect(self._on_device_changed)

        self.rescan_btn = W.button(page.card, "", "ghost", self._start_device_scan)
        self.rescan_btn.setCursor(Qt.PointingHandCursor)
        page.texts.append(
            _Text(self.rescan_btn, "calib.rescan")
        )
        self.rescan_btn.setText(tr("calib.rescan"))

        grid.addWidget(self.camera_label, 0, 0)
        grid.addWidget(self.camera_combo, 0, 1)
        grid.addWidget(self.mic_label, 1, 0)
        grid.addWidget(self.mic_combo, 1, 1)
        grid.addWidget(self.rescan_btn, 2, 1)
        grid.setColumnStretch(1, 1)
        page.layout.addLayout(grid)
        page.layout.addStretch()

    def _fill_camera(self, page: _Page) -> None:
        note = W.label(page.card, "", "mono", wrap=True)
        page.texts.append(_Text(note, "calib.camera_measuring"))
        note.setText(tr("calib.camera_measuring"))
        page.layout.addWidget(note)
        page.layout.addStretch()
        self.camera_result_label = note

    def _fill_mic(self, page: _Page) -> None:
        self.mic_bar = QProgressBar(page.card)
        self.mic_bar.setRange(0, 100)
        self.mic_bar.setValue(0)
        self.mic_bar.setTextVisible(False)
        self.mic_bar.setFixedHeight(6)

        note = W.label(page.card, "", "mono", wrap=True)
        page.texts.append(_Text(note, "calib.mic_measuring"))
        note.setText(tr("calib.mic_measuring"))

        page.layout.addWidget(self.mic_bar)
        page.layout.addWidget(note)
        page.layout.addStretch()
        self.mic_result_label = note

    def _fill_hand(self, page: _Page) -> None:
        self.hand_advice_label = W.label(page.card, tr("calib.hand_waiting"), "pageTitle", wrap=True)
        self.hand_advice_label.setStyleSheet(f"color: {theme.ACCENT}; font-size: 16px; font-weight: 700;")

        self.quality_badge = W.label(page.card, tr("calib.quality_score", score=0), "badgeWarning")
        self.quality_badge.setStyleSheet(
            f"background: {theme.CANVAS_DEEP}; border: 1px solid {theme.BORDER}; border-radius: 6px; padding: 4px 10px; font-weight: 700;"
        )

        self.quality_bar = QProgressBar(page.card)
        self.quality_bar.setRange(0, 100)
        self.quality_bar.setValue(0)
        self.quality_bar.setFixedHeight(8)

        dominant_row = QHBoxLayout()
        dominant_label = W.label(page.card, tr("calib.dominant_hand"), "faint")
        self.dominant_combo = QComboBox(page.card)
        self.dominant_combo.addItem(tr("calib.hand_right"), "Right")
        self.dominant_combo.addItem(tr("calib.hand_left"), "Left")
        dominant_row.addWidget(dominant_label)
        dominant_row.addWidget(self.dominant_combo)
        dominant_row.addStretch()

        note = W.label(page.card, "", "mono", wrap=True)
        page.texts.append(_Text(note, "calib.hand_waiting"))
        note.setText(tr("calib.hand_waiting"))

        page.layout.addWidget(self.hand_advice_label)
        page.layout.addWidget(self.quality_badge)
        page.layout.addWidget(self.quality_bar)
        page.layout.addLayout(dominant_row)
        page.layout.addWidget(note)
        page.layout.addStretch()
        self.hand_result_label = note
        self._good_hand_frames = 0

    def _fill_pinch(self, page: _Page) -> None:
        self.pinch_bar = QProgressBar(page.card)
        self.pinch_bar.setRange(0, TARGET_PINCHES)
        self.pinch_bar.setValue(0)
        self.pinch_bar.setFixedHeight(8)

        note = W.label(page.card, "", "mono", wrap=True)
        page.texts.append(_Text(note, "calib.pinch_waiting"))
        note.setText(tr("calib.pinch_waiting"))

        page.layout.addWidget(self.pinch_bar)
        page.layout.addWidget(note)
        page.layout.addStretch()
        self.pinch_result_label = note

    def _fill_reach(self, page: _Page) -> None:
        self.reach_bar = QProgressBar(page.card)
        self.reach_bar.setRange(0, TARGET_REACH_FRAMES)
        self.reach_bar.setValue(0)
        self.reach_bar.setFixedHeight(8)

        note = W.label(page.card, "", "mono", wrap=True)
        page.texts.append(_Text(note, "calib.reach_waiting"))
        note.setText(tr("calib.reach_waiting"))

        page.layout.addWidget(self.reach_bar)
        page.layout.addWidget(note)
        page.layout.addStretch()
        self.reach_result_label = note

    def _fill_adaptive(self, page: _Page) -> None:
        self.adaptive_check = QCheckBox(page.card)
        self.adaptive_check.setChecked(
            bool(self.settings.get("calibration.adaptive_tuning", True))
        )
        self.adaptive_check.setText(tr("calib.adaptive_enabled"))

        self.adaptive_note = W.label(page.card, "", "mono", wrap=True)
        page.layout.addWidget(self.adaptive_check)
        page.layout.addWidget(self.adaptive_note)
        page.layout.addStretch()

    def _fill_summary(self, page: _Page) -> None:
        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(theme.GAP)
        self.summary_grid.setVerticalSpacing(7)
        self.summary_grid.setColumnStretch(0, 1)
        self.summary_grid.setColumnStretch(1, 0)
        self.summary_rows: Dict[str, Tuple[QLabel, QLabel]] = {}
        page.layout.addLayout(self.summary_grid)
        page.layout.addStretch()
        self._summary_built = False

    # ------------------------------------------------------------------ #
    # Device discovery
    # ------------------------------------------------------------------ #

    def _start_device_scan(self) -> None:
        self.rescan_btn.setEnabled(False)
        if not begin_device_scan():
            # Another dialog is already enumerating the hardware. The capture
            # lock would serialise the two scans, but there is no point paying
            # for it twice: show the fallback list and let the user rescan.
            self._populate_devices()
            self.rescan_btn.setEnabled(True)
            self._set_status(None)
            return

        self._set_status(tr("calib.camera_measuring"))

        def work():
            try:
                return (probe_cameras(), probe_microphones())
            finally:
                end_device_scan()

        self._run_async(work, self._on_devices_found)

    def _on_devices_found(self, result) -> None:
        cameras, microphones = result
        self.cameras = [c for c in cameras]
        self.microphones = list(microphones)
        self._populate_devices()
        self.rescan_btn.setEnabled(True)
        self._set_status(None)

    def _populate_devices(self) -> None:
        previous_camera = self.camera_combo.currentData()

        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        for device in self.cameras:
            label = device.name if device.opened else tr("calib.no_camera")
            self.camera_combo.addItem(
                "%s · %s" % (device.name, device.resolution), device.index
            )
            if not device.opened:
                # A camera that opens but never delivers a frame is kept in the
                # list but disabled, rather than hidden, so the reason is visible.
                self.camera_combo.model().item(
                    self.camera_combo.count() - 1
                ).setEnabled(False)
        if not self.cameras:
            self.camera_combo.addItem(tr("calib.no_camera"), None)
        self.camera_combo.blockSignals(False)

        stored = self.settings.get("performance.camera_index", 0)
        target = previous_camera if previous_camera is not None else stored
        for position in range(self.camera_combo.count()):
            if self.camera_combo.itemData(position) == target:
                self.camera_combo.setCurrentIndex(position)
                break

        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        for device in self.microphones:
            self.mic_combo.addItem(device.name, device.index)
        if not self.microphones:
            self.mic_combo.addItem(tr("calib.no_mic"), None)
        self.mic_combo.blockSignals(False)

    def _on_device_changed(self) -> None:
        if self.preview.is_running:
            self._start_preview()
        if self.current_step == STEP_CAMERA:
            self._clear_camera_result()

    def _selected_camera_index(self) -> Optional[int]:
        data = self.camera_combo.currentData()
        return int(data) if data is not None else None

    def _selected_mic_index(self) -> Optional[int]:
        data = self.mic_combo.currentData()
        return int(data) if data is not None else None

    # ------------------------------------------------------------------ #
    # Preview lifecycle
    # ------------------------------------------------------------------ #

    def _start_preview(self) -> None:
        index = self._selected_camera_index()
        if index is None:
            self.preview.stop()
            return
        self.preview.active_box = None
        self.preview.pinch_threshold = None
        self.preview.start(index)

    def _stop_preview(self) -> None:
        self.preview.stop()
        self.preview.setVisible(False)
        self.session = None

    # ------------------------------------------------------------------ #
    # Async helper
    # ------------------------------------------------------------------ #

    def _run_async(self, func: Callable[[], Any], on_ok: Callable[[Any], None]) -> None:
        task = _Task(func)
        task.succeeded.connect(on_ok)
        task.failed.connect(self._on_task_failed)
        # Kept referenced so it is not collected while the thread is in flight.
        self._task = task
        task.start()

    def _on_task_failed(self, message: str) -> None:
        """A probe threw: report it instead of leaving the step in limbo."""
        self.rescan_btn.setEnabled(True)
        self.measure_btn.setEnabled(True)
        self._set_status(message)

    def _clear_camera_result(self) -> None:
        self.camera_timing = {}
        self.camera_result_label.setText(tr("calib.camera_measuring"))

    # ------------------------------------------------------------------ #
    # Measurements
    # ------------------------------------------------------------------ #

    def _on_measure(self) -> None:
        if self.current_step == STEP_CAMERA:
            self._measure_camera()
        elif self.current_step == STEP_MIC:
            self._measure_mic()

    def _measure_camera(self) -> None:
        index = self._selected_camera_index()
        if index is None:
            return
        self.measure_btn.setEnabled(False)
        self._clear_camera_result()
        # The preview must release the device first: Windows will not hand the
        # same camera to two handles at once.
        self.preview.stop()
        self._run_async(
            lambda: measure_camera_timing(index),
            self._on_camera_timed,
        )

    def _on_camera_timed(self, timing: Dict[str, float]) -> None:
        self.camera_timing = timing or {}
        self.measure_btn.setEnabled(True)

        if not self.camera_timing.get("ok"):
            self.camera_result_label.setText(tr("calib.no_camera"))
            return

        index = self._selected_camera_index()
        device = next((c for c in self.cameras if c.index == index), None)
        resolution = (
            "%d×%d" % (device.width, device.height) if device else "—"
        )
        self.camera_result_label.setText(
            tr(
                "calib.camera_result",
                device=device.name if device else "Camera",
                resolution=resolution,
                fps=self.camera_timing.get("fps", 0.0),
                latency=self.camera_timing.get("latency_ms", 0.0),
            )
        )
        self.measured_steps.add(STEP_CAMERA)
        self._start_preview()

    def _measure_mic(self) -> None:
        self.measure_btn.setEnabled(False)
        self.mic_result_label.setText(tr("calib.mic_measuring"))
        self.mic_bar.setValue(0)
        self._run_async(
            lambda: MicrophoneProbe(self._selected_mic_index()).measure(),
            self._on_mic_measured,
        )

    def _on_mic_measured(self, levels: Dict[str, float]) -> None:
        self.mic_levels = levels or {}
        self.measure_btn.setEnabled(True)
        floor = float(self.mic_levels.get("noise_floor", 0.0))
        self.mic_bar.setValue(int(min(100.0, floor * 100.0 * 4)))

        if not self.mic_levels.get("ok"):
            self.mic_result_label.setText(tr("calib.no_mic"))
            return

        self.mic_result_label.setText(
            tr(
                "calib.mic_result",
                floor=round(floor, 4),
                threshold=round(float(self.mic_levels.get("speech_threshold", 0.06)), 4),
            )
        )
        self.measured_steps.add(STEP_MIC)

    # ------------------------------------------------------------------ #
    # Guided hand routine
    # ------------------------------------------------------------------ #

    def _begin_pinch(self) -> None:
        self.session = CalibrationSession(self.report)
        self.session.begin(CalibrationPhase.PINCH)
        self.pinch_bar.setValue(0)
        self.pinch_result_label.setText(tr("calib.pinch_waiting"))
        self.preview.pinch_threshold = self.report.pinch_threshold
        self.preview.pinch_armed = True
        self._tick.start()

    def _begin_reach(self) -> None:
        if self.session is None or self.session.is_complete:
            self.session = CalibrationSession(self.report)
        self.session.begin(CalibrationPhase.REACH)
        self.reach_bar.setValue(0)
        self.reach_result_label.setText(tr("calib.reach_waiting"))
        self.preview.pinch_threshold = None
        self.preview.pinch_armed = False
        self.preview.active_box = None
        self._tick.start()

    def _on_tick(self) -> None:
        if self.current_step == STEP_PINCH:
            self._tick_pinch()
        elif self.current_step == STEP_REACH:
            self._tick_reach()
        elif self.current_step == STEP_HAND:
            self._tick_hand()
        elif self.current_step == STEP_ADAPTIVE:
            self._tick_adaptive()

    def _tick_hand(self) -> None:
        snapshot = self.preview.snapshot()
        if snapshot is None or not self.preview.has_hand:
            self.quality_bar.setValue(0)
            self.quality_badge.setText(tr("calib.quality_score", score=0))
            self.quality_badge.setStyleSheet(f"color: {theme.DANGER}; font-weight: 700;")
            self.hand_advice_label.setText(tr("calib.tip_center_hand"))
            self.hand_result_label.setText(tr("calib.hand_waiting"))
            self._good_hand_frames = 0
            return

        D = getattr(snapshot, "hand_span", 0.35)
        B = getattr(snapshot, "brightness", 100.0)
        is_out = getattr(snapshot, "is_out_of_frame", False)
        handedness = getattr(snapshot, "handedness", "Right")

        if hasattr(self, "dominant_combo") and not getattr(self, "_dominant_user_selected", False):
            idx = 0 if handedness == "Right" else 1
            self.dominant_combo.setCurrentIndex(idx)

        # Distance score (optimal between 0.24 and 0.50)
        if 0.24 <= D <= 0.50:
            s_d = 100
        else:
            s_d = max(0, int(100 - abs(D - 0.37) * 350))

        # Lighting score (optimal between 70 and 185)
        if 70 <= B <= 185:
            s_b = 100
        elif B < 70:
            s_b = max(0, int(B / 70.0 * 100))
        else:
            s_b = max(0, int(100 - (B - 185) / 70.0 * 100))

        s_c = 30 if is_out else 100
        quality = int(0.40 * s_d + 0.40 * s_b + 0.20 * s_c)
        quality = max(0, min(100, quality))

        self.quality_bar.setValue(quality)
        self.quality_badge.setText(tr("calib.quality_score", score=quality))

        if quality >= 75:
            self.quality_badge.setStyleSheet(f"color: {theme.SUCCESS}; font-weight: 700;")
            self.hand_advice_label.setText(tr("calib.tip_optimal"))
            self.hand_advice_label.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 16px; font-weight: 700;")
            self.hand_result_label.setText(tr("calib.hand_locked"))
            self._good_hand_frames += 1
            if self._good_hand_frames >= 10:
                self.measured_steps.add(STEP_HAND)
                self.next_btn.setEnabled(True)
        elif quality >= 45:
            self.quality_badge.setStyleSheet(f"color: {theme.WARNING}; font-weight: 700;")
            self.hand_advice_label.setStyleSheet(f"color: {theme.WARNING}; font-size: 16px; font-weight: 700;")
            if s_b < s_d:
                self.hand_advice_label.setText(tr("calib.tip_more_light") if B < 70 else tr("calib.tip_less_light"))
            elif is_out:
                self.hand_advice_label.setText(tr("calib.tip_center_hand"))
            else:
                self.hand_advice_label.setText(tr("calib.tip_closer") if D < 0.24 else tr("calib.tip_further"))
            self.hand_result_label.setText(tr("calib.hand_locked"))
        else:
            self.quality_badge.setStyleSheet(f"color: {theme.DANGER}; font-weight: 700;")
            self.hand_advice_label.setStyleSheet(f"color: {theme.DANGER}; font-size: 16px; font-weight: 700;")
            if s_b < 50:
                self.hand_advice_label.setText(tr("calib.tip_more_light"))
            elif is_out:
                self.hand_advice_label.setText(tr("calib.tip_center_hand"))
            else:
                self.hand_advice_label.setText(tr("calib.tip_closer") if D < 0.24 else tr("calib.tip_further"))
            self.hand_result_label.setText(tr("calib.hand_waiting"))

    def _tick_pinch(self) -> None:
        if self.session is None:
            return
        done = self.session.pinch_cycles
        self.pinch_bar.setValue(min(done, TARGET_PINCHES))
        self.pinch_result_label.setText(
            tr("calib.pinch_count", done=min(done, TARGET_PINCHES), total=TARGET_PINCHES)
        )
        if done >= TARGET_PINCHES:
            self._finish_phase()

    def _tick_reach(self) -> None:
        if self.session is None:
            return
        self.reach_bar.setValue(min(self.session.phase_samples, TARGET_REACH_FRAMES))

        box = self.session.reach_box()
        if box is not None:
            left, top, right, bottom = box
            self.preview.active_box = (left, top, right, bottom)
            self.reach_result_label.setText(
                tr(
                    "calib.reach_live",
                    width=int((right - left) * 100),
                    height=int((bottom - top) * 100),
                )
            )
        if self.session.phase_samples >= TARGET_REACH_FRAMES:
            self._finish_phase()

    def _on_preview_landmarks(self, snapshot) -> None:
        """
        Feeds one calibration sample per camera frame.

        Runs on the GUI thread (Qt auto-connection) and only touches plain
        Python state, so no locking is needed here.
        """
        step = self.current_step
        if step == STEP_ADAPTIVE:
            if self.live_tuner is not None and snapshot is not None:
                self.live_tuner.feed(
                    snapshot.index_tip, snapshot.pinch_distance, time.time()
                )
            return
        if step not in (STEP_PINCH, STEP_REACH):
            return
        if self.session is None or self.session.is_complete:
            return
        if snapshot is None:
            self.session.notify_hand_lost()
            return
        self.session.feed(
            HandSample(
                index_tip=snapshot.index_tip,
                pinch_distance=snapshot.pinch_distance,
                timestamp=time.time(),
            )
        )

    def _finish_phase(self) -> None:
        """Commits the current phase and moves on to the next step."""
        self._tick.stop()
        if self.session is not None:
            self.report = self.session.finish()
            if self.current_step == STEP_PINCH:
                self.measured_steps.add(STEP_PINCH)
            else:
                self.measured_steps.add(STEP_REACH)
        self.preview.pinch_armed = False
        self._next_step()

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def _next_step(self) -> None:
        if self.current_step < TOTAL_STEPS - 1:
            self.current_step += 1
        else:
            self._apply_and_close()
            return
        self._enter_step()

    def _prev_step(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._enter_step()

    def _enter_step(self) -> None:
        step = self.current_step
        self.stacked_pages.setCurrentIndex(step)
        self.preview.setVisible(step in (STEP_CAMERA, STEP_HAND, STEP_PINCH, STEP_REACH))

        if step in (STEP_CAMERA, STEP_HAND, STEP_PINCH, STEP_REACH):
            if not self.preview.is_running:
                self._start_preview()
        elif step == STEP_ADAPTIVE:
            # The feed keeps running behind the summary; the tuner needs frames.
            self._start_adaptive_preview()
        elif step in (STEP_SUMMARY, STEP_DEVICES, STEP_MIC):
            if not self.preview.is_running and step == STEP_SUMMARY:
                self._start_preview()

        if step == STEP_PINCH:
            self._begin_pinch()
        elif step == STEP_REACH:
            self._begin_reach()
        elif step in (STEP_HAND, STEP_ADAPTIVE):
            self._tick.start()
        elif step == STEP_SUMMARY:
            self._tick.stop()
            self._build_summary()

        self.measure_btn.setVisible(step in (STEP_CAMERA, STEP_MIC))
        self.measure_btn.setEnabled(True)
        self.retranslate()

    def _start_adaptive_preview(self) -> None:
        self.live_tuner = AdaptiveTuner(
            self.settings,
            window=int(self.settings.get("calibration.adaptive_sample_window", 240)),
            min_samples=int(self.settings.get("calibration.adaptive_min_samples", 45)),
            write_threshold=float(
                self.settings.get("calibration.adaptive_write_threshold", 0.08)
            ),
        )
        if not self.preview.is_running:
            self._start_preview()

    def _tick_adaptive(self) -> None:
        if self.current_step != STEP_ADAPTIVE or self.live_tuner is None:
            return
        self._render_adaptive_note()

    def _render_adaptive_note(self) -> None:
        """Writes the live sample count, ready to be re-run after a switch."""
        if self.live_tuner is None:
            self.adaptive_note.setText(tr("calib.adaptive_waiting"))
            return
        self.adaptive_note.setText(
            tr("calib.adaptive_status", samples=int(self.live_tuner.snapshot()["samples"]))
        )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def _summary_entries(self) -> List[Tuple[str, str, str, float]]:
        """The rows shown on the summary step: label, value, confidence key."""
        r = self.report
        entries = [
            ("calib.value_pinch", "%.4f" % r.pinch_threshold,
             "pinch_click_threshold", r.confidence_of("pinch_click_threshold")),
            ("calib.value_deadzone", "%.4f" % r.dead_zone_radius,
             "dead_zone_radius", r.confidence_of("dead_zone_radius")),
            ("calib.value_smoothing", "%.3f" % r.smoothing_factor,
             "smoothing_factor", r.confidence_of("smoothing_factor")),
            ("calib.value_cursor_speed", "%.2f" % r.cursor_speed,
             "cursor_speed", r.confidence_of("cursor_speed")),
            ("calib.value_drag", "%.2f s" % r.drag_hold_delay,
             "pinch_hold_drag_delay", r.confidence_of("pinch_hold_drag_delay")),
            ("calib.value_double", "%.2f s" % r.double_pinch_window,
             "double_pinch_window", r.confidence_of("double_pinch_window")),
            ("calib.value_scroll", "%d" % r.scroll_speed,
             "scroll_speed", r.confidence_of("scroll_speed")),
            ("calib.value_swipe", "%.2f" % r.swipe_velocity_threshold,
             "swipe_velocity_threshold", r.confidence_of("swipe_velocity_threshold")),
        ]
        box = r.active_box
        entries.append((
            "calib.value_box",
            "%.0f,%.0f → %.0f,%.0f" % (box[0] * 100, box[1] * 100,
                                       box[2] * 100, box[3] * 100),
            "active_box",
            r.confidence_of("active_box"),
        ))
        if self.camera_timing.get("ok"):
            entries.append((
                "calib.value_latency",
                "%.1f ms @ %.0f FPS" % (
                    self.camera_timing.get("latency_ms", 0.0),
                    self.camera_timing.get("fps", 0.0),
                ),
                "camera_timing", 1.0,
            ))
        if self.mic_levels.get("ok"):
            entries.append((
                "calib.value_noise",
                "%.4f" % float(self.mic_levels.get("noise_floor", 0.0)),
                "mic_noise", 1.0,
            ))
        return entries

    def _build_summary(self) -> None:
        if self._summary_built:
            self._refresh_summary()
            return

        page_card = self.pages[STEP_SUMMARY].card
        for row, (label_key, value, conf_key, confidence) in enumerate(
            self._summary_entries()
        ):
            name = W.label(page_card, "", "muted")
            name.setText(tr(label_key))
            value_label = W.label(page_card, value, "mono")
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            confidence_label = W.label(page_card, "", "faint")
            if confidence >= 0.6:
                confidence_label.setText(tr("calib.confidence_note", percent=int(confidence * 100)))
                confidence_label.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 11px;")
            else:
                confidence_label.setText(tr("calib.skipped"))
                confidence_label.setStyleSheet(f"color: {theme.WARNING}; font-size: 11px;")

            self.summary_grid.addWidget(name, row, 0)
            self.summary_grid.addWidget(value_label, row, 1)
            self.summary_grid.addWidget(confidence_label, row, 2)

            self.pages[STEP_SUMMARY].texts.append(_Text(name, label_key))
            self.summary_rows[conf_key] = (value_label, confidence_label)

        self._summary_built = True

    def _refresh_summary(self) -> None:
        for _label_key, value, conf_key, confidence in self._summary_entries():
            if conf_key not in self.summary_rows:
                continue
            value_label, confidence_label = self.summary_rows[conf_key]
            value_label.setText(value)
            if confidence >= 0.6:
                confidence_label.setText(
                    tr("calib.confidence_note", percent=int(confidence * 100))
                )
                confidence_label.setStyleSheet(
                    f"color: {theme.SUCCESS}; font-size: 11px;"
                )
            else:
                confidence_label.setText(tr("calib.skipped"))
                confidence_label.setStyleSheet(
                    f"color: {theme.WARNING}; font-size: 11px;"
                )

    # ------------------------------------------------------------------ #
    # Applying
    # ------------------------------------------------------------------ #

    def _apply_and_close(self) -> None:
        """Persists everything that was measured, then closes the wizard."""
        camera_index = self._selected_camera_index()
        if camera_index is not None:
            self.settings.set("performance.camera_index", camera_index)

        mic_index = self._selected_mic_index()
        if mic_index is not None:
            self.settings.set("audio.input_device", str(mic_index))
        if self.mic_levels.get("ok"):
            self.settings.set("audio.noise_floor",
                              round(float(self.mic_levels.get("noise_floor", 0.0)), 5))
            self.settings.set("audio.speech_threshold",
                              round(float(self.mic_levels.get("speech_threshold", 0.06)), 5))

        if self.camera_timing.get("ok"):
            self.settings.set(
                "performance.measured_fps",
                round(float(self.camera_timing.get("fps", 0.0)), 1),
            )

        self.settings.set("calibration.adaptive_tuning", self.adaptive_check.isChecked())
        self.settings.set("calibration.last_run", int(time.time()))
        self.settings.set("calibration.guided_done", True)
        dominant = self.dominant_combo.currentData() if hasattr(self, "dominant_combo") else "Right"
        if dominant:
            self.settings.set("gestures.dominant_hand", dominant)

        # Only the gesture block is written from the report; the settings
        # manager already saved each key individually above.
        for key, value in self.report.to_settings_patch().items():
            self.settings.set(key, value)

        self.accept()

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    def _set_status(self, text: Optional[str]) -> None:
        self.status_label.setText(text or "")
        self.status_label.setVisible(bool(text))

    def _on_language_changed(self, code: str) -> None:
        theme.apply_to(self)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("calib.title"))
        self.step_label.setText(
            tr("common.step_of", current=self.current_step + 1, total=TOTAL_STEPS)
        )
        self.progress_bar.setValue(self.current_step + 1)

        for page in self.pages:
            page.retranslate()

        self.back_btn.setText(tr("common.back"))
        self.back_btn.setEnabled(self.current_step > 0)
        self.measure_btn.setText(
            tr("calib.measure")
            if self.current_step == STEP_CAMERA
            else tr("calib.remeasure")
        )
        self.next_btn.setText(
            tr("calib.apply")
            if self.current_step == STEP_SUMMARY
            else tr("common.next")
        )
        if self._summary_built:
            self._refresh_summary()

        # Built imperatively rather than through a page binding, so they need
        # re-resolving on their own when the interface language changes.
        self.adaptive_check.setText(tr("calib.adaptive_enabled"))
        self._render_adaptive_note()

    # ------------------------------------------------------------------ #

    def done(self, result: int) -> None:
        self._tick.stop()
        self.preview.stop()
        # The probe task is a daemon thread and is deliberately not joined: it
        # only touches local variables, and waiting here would freeze the UI.
        if self._task is not None:
            try:
                self._task.succeeded.disconnect()
                self._task.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._task = None
        i18n.get_translator().remove_listener(self._on_language_changed)
        super().done(result)
