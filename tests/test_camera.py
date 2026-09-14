"""Tests for camera device discovery and the threaded camera manager.

All camera access is mocked: no physical webcam is touched.
"""

from __future__ import annotations

import numpy as np
import pytest

from hadj_no_touch.camera import camera_config
from hadj_no_touch.camera import camera_manager
from hadj_no_touch.camera.camera_config import (
    apply_exposure,
    find_best_camera,
    is_frame_usable,
    resolve_camera,
)
from hadj_no_touch.camera.camera_manager import CameraManager
from hadj_no_touch.config import CameraSettings


class FakeCap:
    def __init__(self, opened: bool = True, reader=None):
        self._opened = opened
        self._reader = reader
        self.released = False
        self.sets: list = []

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
        if self._reader is None:
            return False, None
        return self._reader()

    def release(self) -> None:
        self.released = True

    def set(self, prop, value):
        self.sets.append((prop, value))
        return True


def _textured_frame() -> np.ndarray:
    return (np.random.RandomState(7).rand(16, 16, 3) * 255).astype(np.uint8)


def _uniform_frame(value: int = 0) -> np.ndarray:
    return np.full((16, 16, 3), value, dtype=np.uint8)


class FakeCV:
    CAP_DSHOW = 700
    CAP_MSMF = 1900
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5
    CAP_PROP_AUTO_EXPOSURE = 10
    CAP_PROP_AUTO_WB = 12
    CAP_PROP_GAIN = 14
    CAP_PROP_BRIGHTNESS = 11

    def __init__(self, factory=None):
        self.factory = factory
        self.instances: list = []

    def VideoCapture(self, index, backend=None):
        self.instances.append((index, backend))
        if self.factory is None:
            return FakeCap(opened=False)
        return self.factory(index, backend)


def _broken_factory(_index, _backend) -> FakeCap:
    return FakeCap(opened=True, reader=lambda: (True, _uniform_frame()))


def _good_only_at(index_ok: int) -> FakeCap:
    def factory(index, backend) -> FakeCap:
        if index == index_ok:
            return FakeCap(opened=True, reader=lambda: (True, _textured_frame()))
        return FakeCap(opened=True, reader=lambda: (False, None))
    return factory


@pytest.fixture(autouse=True)
def _clean_cache_and_fake(monkeypatch):
    camera_config._CHOICE_CACHE.clear()
    fake = FakeCV()
    monkeypatch.setattr(camera_config, "cv2", fake)
    monkeypatch.setattr(camera_manager, "cv2", fake)
    return fake


class TestFrameValidation:
    def test_uniform_frame_rejected(self) -> None:
        assert is_frame_usable(None) is False
        assert is_frame_usable(_uniform_frame(0)) is False
        assert is_frame_usable(_uniform_frame(255)) is False

    def test_textured_frame_accepted(self) -> None:
        assert is_frame_usable(_textured_frame()) is True

    def test_apply_exposure_sets_properties(self) -> None:
        cap = FakeCap()
        apply_exposure(cap)
        props = {prop for prop, _ in cap.sets}
        for expected in (FakeCV.CAP_PROP_AUTO_EXPOSURE, FakeCV.CAP_PROP_AUTO_WB,
                         FakeCV.CAP_PROP_GAIN, FakeCV.CAP_PROP_BRIGHTNESS):
            assert expected in props

    def test_apply_exposure_guarded_when_cap_missing_set(self) -> None:
        class NoSet:
            pass
        apply_exposure(NoSet())  # must not raise


class TestResolveCamera:
    def test_picks_working_camera(self, _clean_cache_and_fake) -> None:
        _clean_cache_and_fake.factory = _good_only_at(1)
        index, backend = resolve_camera(0, max_index=4)
        assert index == 1
        assert backend is not None

    def test_preferred_index_first(self, _clean_cache_and_fake) -> None:
        _clean_cache_and_fake.factory = _good_only_at(0)
        index, _ = resolve_camera(0, max_index=4)
        assert index == 0

    def test_none_usable_returns_minus_one(self, _clean_cache_and_fake) -> None:
        index, backend = resolve_camera(3, max_index=2)
        assert index == -1
        assert backend is None

    def test_result_is_cached(self, _clean_cache_and_fake) -> None:
        _clean_cache_and_fake.factory = _good_only_at(1)
        assert resolve_camera(0, max_index=4)[0] == 1
        attempts_after_first = len(_clean_cache_and_fake.instances)
        assert resolve_camera(0, max_index=4)[0] == 1
        assert len(_clean_cache_and_fake.instances) == attempts_after_first

    def test_use_cache_false_reprobes(self, _clean_cache_and_fake) -> None:
        _clean_cache_and_fake.factory = _good_only_at(1)
        assert resolve_camera(0, max_index=4)[0] == 1
        attempts_after_first = len(_clean_cache_and_fake.instances)
        assert resolve_camera(0, max_index=4, use_cache=False)[0] == 1
        assert len(_clean_cache_and_fake.instances) > attempts_after_first

    def test_find_best_camera_wrapper(self, _clean_cache_and_fake) -> None:
        _clean_cache_and_fake.factory = _good_only_at(2)
        assert find_best_camera(0, max_index=4) == 2


class TestCameraManagerOpen:
    def test_persists_resolved_index(self, _clean_cache_and_fake, monkeypatch) -> None:
        fake = _clean_cache_and_fake
        fake.factory = _good_only_at(1)
        m = CameraManager(CameraSettings(index=0))
        assert m.open() is True
        assert m.settings.index == 1
        assert m.error is None
        assert m._cap is not None
        assert m.is_running is False
        m.stop()

    def test_open_failure_sets_error(self, _clean_cache_and_fake) -> None:
        m = CameraManager(CameraSettings(index=0))
        assert m.open() is False
        assert m.error is not None
        assert m._cap is None

    def test_explicit_index_honoured(self, _clean_cache_and_fake) -> None:
        fake = _clean_cache_and_fake
        fake.factory = _good_only_at(2)
        m = CameraManager(CameraSettings(index=0))
        assert m.open(2) is True
        assert m.settings.index == 2

    def test_forced_resolution_falls_back_to_native(self, _clean_cache_and_fake) -> None:
        fake = _clean_cache_and_fake
        m = CameraManager(CameraSettings(index=0, width=640, height=480))

        class NativeOnlyCap(FakeCap):
            def __init__(self):
                super().__init__(opened=True)
                self._forced = False

            def set(self, prop, value):
                if prop == FakeCV.CAP_PROP_FRAME_WIDTH and value > 0:
                    self._forced = True
                super().set(prop, value)

            def read(self):
                if self._forced:
                    return True, _uniform_frame()
                return True, _textured_frame()

        def factory(index, backend):
            if index == 0:
                return NativeOnlyCap()
            return FakeCap(opened=False)
        fake.factory = factory
        assert m.open() is True
        assert m.settings.index == 0
        assert m.error is None
        m.stop()


class TestReconnect:
    def test_reopen_swaps_camera_without_attribute_error(self, _clean_cache_and_fake,
                                                         monkeypatch) -> None:
        fake = _clean_cache_and_fake
        fake.factory = _good_only_at(1)
        monkeypatch.setattr(
            camera_manager,
            "resolve_camera",
            lambda *a, **k: (1, FakeCV.CAP_DSHOW),
        )
        m = CameraManager(CameraSettings(index=0))
        m._cap = FakeCap(opened=True, reader=lambda: (False, None))
        assert m._reopen() is True
        assert m._cap is not None
        assert m.error is None

    def test_reopen_can_recover_from_none(self, _clean_cache_and_fake, monkeypatch) -> None:
        fake = _clean_cache_and_fake
        fake.factory = _good_only_at(1)
        monkeypatch.setattr(
            camera_manager,
            "resolve_camera",
            lambda *a, **k: (1, FakeCV.CAP_DSHOW),
        )
        m = CameraManager(CameraSettings(index=0))
        m._cap = None
        assert m._reopen() is True
        assert m._cap is not None

    def test_reopen_sets_error_when_no_camera(self, _clean_cache_and_fake, monkeypatch) -> None:
        monkeypatch.setattr(camera_manager, "resolve_camera", lambda *a, **k: (-1, None))
        m = CameraManager(CameraSettings(index=0))
        m._cap = FakeCap(opened=True)
        assert m._reopen() is False
        assert m.error is not None