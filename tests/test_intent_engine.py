"""Tests for the AI intent engine (context-aware gesture/voice mapping)."""

from __future__ import annotations

from hadj_no_touch.ai.context_engine import ApplicationContext
from hadj_no_touch.ai.intent_engine import (
    IntentEngine, NEXT_TRACK, PREV_TRACK, NEXT_SLIDE, PREV_SLIDE,
    NEXT_PAGE, PREV_PAGE, ZOOM_IN, SCROLL, VOLUME_SET, OPEN_APP,
)
from hadj_no_touch.gestures import gesture_engine as ge
from hadj_no_touch.voice import voice_commands as vc


def _ev(kind: str, **kw) -> ge.GestureEvent:
    return ge.GestureEvent(kind=kind, confidence=0.8, gesture=kind, **kw)


class TestGestureIntent:
    def test_swipe_in_media_is_next_track(self) -> None:
        eng = IntentEngine()
        ctx = ApplicationContext(category="media")
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT), ctx)
        assert intent.action == NEXT_TRACK

    def test_swipe_in_presentation_is_next_slide(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT),
                                  ApplicationContext(category="presentation"))
        assert intent.action == NEXT_SLIDE

    def test_swipe_back_in_presentation_is_prev_slide(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_RIGHT),
                                  ApplicationContext(category="presentation"))
        assert intent.action == PREV_SLIDE

    def test_swipe_in_pdf_is_next_page(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT),
                                  ApplicationContext(category="pdf"))
        assert intent.action == NEXT_PAGE

    def test_swipe_up_in_pdf_is_previous_page(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_UP),
                                  ApplicationContext(category="pdf"))
        assert intent.action == PREV_PAGE

    def test_circle_in_imaging_rotates(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.CIRCLE_CW),
                                  ApplicationContext(category="imaging"))
        assert intent.action == "ROTATE_3D"

    def test_unmapped_gesture_is_none(self) -> None:
        eng = IntentEngine()
        assert eng.from_gesture(_ev(ge.MOVE), ApplicationContext(category="other")) is None

    def test_swipe_other_falls_back_to_next_page(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT), ApplicationContext(category="other"))
        assert intent.action == NEXT_PAGE


class TestVoiceIntent:
    def test_open_chrome(self) -> None:
        eng = IntentEngine()
        vi = vc.parse("open chrome")
        intent = eng.from_voice(vi, ApplicationContext(category="other"))
        assert intent.action == OPEN_APP
        assert intent.params.get("app") == "chrome"

    def test_volume_set(self) -> None:
        eng = IntentEngine()
        vi = vc.parse("volume 50 percent")
        intent = eng.from_voice(vi, ApplicationContext(category="media"))
        assert intent.action == VOLUME_SET
        assert intent.params["percent"] == 50.0

    def test_scroll_direction(self) -> None:
        eng = IntentEngine()
        up = eng.from_voice(vc.parse("scroll up"), ApplicationContext())
        down = eng.from_voice(vc.parse("scroll down"), ApplicationContext())
        assert up.action == SCROLL and down.action == SCROLL
        assert up.params["direction"] == -1
        assert down.params["direction"] == 1


class TestProfileRemap:
    def test_gesture_map_override(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT),
                                  ApplicationContext(category="media"))
        remapped = eng.remap_for_profile(intent, {ge.SWIPE_LEFT: "SCROLL"})
        assert remapped.action == "SCROLL"

    def test_no_override_without_map(self) -> None:
        eng = IntentEngine()
        intent = eng.from_gesture(_ev(ge.SWIPE_LEFT),
                                  ApplicationContext(category="media"))
        remapped = eng.remap_for_profile(intent, {})
        assert remapped.action == NEXT_TRACK


class TestMultimodalGazeGate:
    def test_gaze_confirms_pointer(self) -> None:
        from hadj_no_touch.ai.multimodal_engine import MultimodalEngine
        mm = MultimodalEngine()
        # no gaze active: pinch confidence decides
        assert mm.gaze_confirms_pointer(0.6)
        assert not mm.gaze_confirms_pointer(0.3)
        # gaze active and aligned: lower pinch confidence acceptable
        mm.set_gaze(0.5, 0.5, True)
        mm.set_pointer(0.55, 0.5, True)
        assert mm.gaze_confirms_pointer(0.4)
        # gaze active but far from pointer: rejected
        mm.set_pointer(0.05, 0.05, True)
        assert not mm.gaze_confirms_pointer(0.4)