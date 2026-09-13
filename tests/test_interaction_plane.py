"""Tests for the virtual interaction plane (mapping, smoothing, jump rejection)."""

from __future__ import annotations

from hadj_no_touch.config import CursorSettings
from hadj_no_touch.interaction.calibration import CalibrationManager
from hadj_no_touch.interaction.interaction_plane import InteractionPlane


class TestFallbackMapping:
    def _plane(self, **kw) -> InteractionPlane:
        cs = CursorSettings(smoothing=1.0, speed=1.0, dead_zone=0.001, **kw)
        return InteractionPlane(CalibrationManager(), cursor_settings=cs)

    def test_center_maps_to_center(self) -> None:
        p = self._plane()
        p.set_screen_size(1920, 1080)
        x, y = p.process((0.5, 0.5))
        assert abs(x - 960) < 60
        assert abs(y - 540) < 60

    def test_mirror_handedness(self) -> None:
        # fingertip on the right of the image should map to the left of screen
        p = self._plane()
        p.set_screen_size(1000, 1000)
        x, _ = p.process((0.9, 0.5))
        assert x < 500

    def test_result_stays_in_bounds(self) -> None:
        for n in [(0.0, 0.0), (1.0, 1.0), (0.3, 0.7)]:
            p = self._plane()  # fresh plane: jump rejection must not trip
            p.set_screen_size(1920, 1080)
            out = p.process(n)
            assert out is not None
            x, y = out
            assert 0 <= x <= 1920
            assert 0 <= y <= 1080

    def test_jump_rejection(self) -> None:
        p = self._plane()
        p.set_screen_size(1920, 1080)
        p.process((0.5, 0.5))
        out = p.process((0.05, 0.05))  # huge jump = tracking glitch
        assert out is None

    def test_dead_zone_stability(self) -> None:
        p = self._plane()
        p.set_screen_size(1920, 1080)
        x0, y0 = p.process((0.5, 0.5))
        x1, y1 = p.process((0.5002, 0.5002))  # within dead zone
        assert (x0, y0) == (x1, y1)