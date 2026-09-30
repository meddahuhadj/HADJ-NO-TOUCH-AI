import pytest
from core.auto_calibration import perform_one_click_auto_calibration, CalibrationReport
from config.settings_manager import SettingsManager


def test_perform_one_click_auto_calibration():
    settings = SettingsManager()
    res = perform_one_click_auto_calibration(camera_index=-1)
    assert res["success"] is True
    assert "pinch_threshold" in res
    assert "smoothing_factor" in res
    assert "cursor_speed" in res
    assert "quality_score" in res
    assert settings.get("gestures.calibrated") is True
