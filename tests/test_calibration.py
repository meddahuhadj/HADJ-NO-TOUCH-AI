"""Tests for the calibration manager (homography mapping)."""

from __future__ import annotations

import time

from hadj_no_touch.interaction.calibration import (
    CalibrationManager, SCREEN_ANCHORS,
)

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False


def _calibrated_manager() -> CalibrationManager:
    cal = CalibrationManager()
    # camera points arranged like a slightly skewed screen
    cal.points_camera = [(0.10, 0.10), (0.88, 0.12), (0.85, 0.90), (0.12, 0.88)]
    cal._try_build(silent=True)
    return cal


class TestCalibrationCollect:
    def test_pinch_dwell_advances_stage(self) -> None:
        cal = CalibrationManager()
        now = time.monotonic()
        # no pinch: no samples
        assert not cal.collect((0.5, 0.5), False, now=now)
        assert cal.stage == 0
        # pinch held long enough: stage advances
        cal.collect((0.5, 0.5), True, now=now)
        assert not cal.done
        assert cal.stage == 0
        # simulate holding the pinch for 500ms
        cal.start_point(now)
        for i in range(20):
            cal.collect((0.5, 0.5), True, now=now + 0.025 * i)
        assert cal.stage == 1

    def test_confirm_point_manual(self) -> None:
        cal = CalibrationManager()
        for i, anchor in enumerate(SCREEN_ANCHORS):
            cal.confirm_point(tuple(anchor))
            assert cal.stage == i + 1
        assert not cal.done
        cal.confirm_point((0.5, 0.5))  # center verification
        assert cal.done


class TestCalibrationMapping:
    def test_mapping_lands_on_anchors(self) -> None:
        if not HAVE_CV2:
            return
        cal = _calibrated_manager()
        assert cal.calibrated and cal.homography is not None
        for cam, dst in zip(cal.points_camera[:4], SCREEN_ANCHORS):
            m = cal.map(cam)
            assert m is not None
            # mapped point should sit near the destination anchor
            assert abs(m[0] - dst[0]) < 0.08
            assert abs(m[1] - dst[1]) < 0.08

    def test_uncalibrated_returns_none(self) -> None:
        cal = CalibrationManager()
        assert cal.map((0.5, 0.5)) is None

    def test_center_verify_error_bounded(self) -> None:
        if not HAVE_CV2:
            return
        cal = _calibrated_manager()
        err = cal.verify_center_error((0.5, 0.5))
        assert err < 0.3