"""Tests for the voice command parser (EN / FR / AR)."""

from __future__ import annotations

from hadj_no_touch.voice import voice_commands as vc


class TestEnglish:
    def test_open_app(self) -> None:
        vi = vc.parse("open chrome")
        assert vi.intent == vc.OPEN_APP
        assert vi.params.get("app") == "chrome"

    def test_volume_set(self) -> None:
        vi = vc.parse("volume 50 percent")
        assert vi.intent == vc.VOLUME_SET
        assert abs(float(vi.params["percent"]) - 50.0) < 1e-6

        vi = vc.parse("set volume to 30")
        assert vi.intent == vc.VOLUME_SET
        assert abs(float(vi.params["percent"]) - 30.0) < 1e-6

    def test_scroll(self) -> None:
        assert vc.parse("scroll down").intent == vc.SCROLL_DOWN
        assert vc.parse("scroll up").intent == vc.SCROLL_UP

    def test_window_actions(self) -> None:
        assert vc.parse("close this window").intent == vc.CLOSE_WINDOW
        assert vc.parse("minimize").intent == vc.MINIMIZE
        assert vc.parse("maximize").intent == vc.MAXIMIZE

    def test_media(self) -> None:
        assert vc.parse("pause").intent == vc.PLAY_PAUSE
        assert vc.parse("next track").intent == vc.NEXT_TRACK
        assert vc.parse("previous track").intent == vc.PREV_TRACK
        assert vc.parse("mute").intent == vc.MUTE

    def test_presentation(self) -> None:
        assert vc.parse("next slide").intent == vc.NEXT_SLIDE
        assert vc.parse("previous slide").intent == vc.PREV_SLIDE
        assert vc.parse("start presentation").intent == vc.START_PRESENTATION
        assert vc.parse("black screen").intent == vc.BLACK_SCREEN

    def test_page_and_tabs(self) -> None:
        assert vc.parse("next page").intent == vc.NEXT_PAGE
        assert vc.parse("previous page").intent == vc.PREV_PAGE
        assert vc.parse("next tab").intent == vc.NEXT_TAB
        assert vc.parse("close a tab").intent == vc.CLOSE_TAB

    def test_editing(self) -> None:
        assert vc.parse("copy").intent == vc.COPY
        assert vc.parse("paste").intent == vc.PASTE
        assert vc.parse("cut").intent == vc.CUT
        assert vc.parse("undo").intent == vc.UNDO
        assert vc.parse("select all").intent == vc.SELECT_ALL

    def test_emergency(self) -> None:
        assert vc.parse("emergency stop").intent == vc.EMERGENCY_STOP

    def test_freeze_is_emergency(self) -> None:
        assert vc.parse("freeze").intent == vc.EMERGENCY_STOP
        assert vc.parse("stop everything").intent == vc.EMERGENCY_STOP

    def test_screenshot(self) -> None:
        assert vc.parse("take a screenshot").intent == vc.SCREENSHOT

    def test_garbage(self) -> None:
        assert vc.parse("blah blahwidget").intent == vc.NONE_INTENT


class TestSpecificity:
    """Fixed-phrase commands must beat generic "open/start/type <x>"."""

    def test_start_presentation_not_open_app(self) -> None:
        assert vc.parse("start presentation").intent == vc.START_PRESENTATION

    def test_open_settings_not_open_app(self) -> None:
        assert vc.parse("open settings").intent == vc.OPEN_SETTINGS

    def test_start_calibration_not_open_app(self) -> None:
        assert vc.parse("start calibration").intent == vc.CALIBRATE

    def test_open_a_new_tab_not_open_app(self) -> None:
        assert vc.parse("open a new tab").intent == vc.NEW_TAB

    def test_generic_open_still_works(self) -> None:
        vi = vc.parse("open chrome")
        assert vi.intent == vc.OPEN_APP
        assert vi.params["app"] == "chrome"


class TestFrench:
    def test_open_app(self) -> None:
        vi = vc.parse("ouvre chrome", language="fr")
        assert vi.intent == vc.OPEN_APP
        assert vi.params.get("app") == "chrome"

    def test_next_page(self) -> None:
        assert vc.parse("page suivante", language="fr").intent == vc.NEXT_PAGE

    def test_close_window(self) -> None:
        assert vc.parse("ferme cette fenetre", language="fr").intent == vc.CLOSE_WINDOW

    def test_zoom(self) -> None:
        assert vc.parse("zoom avant", language="fr").intent == vc.ZOOM_IN
        assert vc.parse("zoom arriere", language="fr").intent == vc.ZOOM_OUT

    def test_garbage(self) -> None:
        assert vc.parse("chatons mignons", language="fr").intent == vc.NONE_INTENT

    def test_bloque_tout_is_emergency(self) -> None:
        assert vc.parse("bloque tout", language="fr").intent == vc.EMERGENCY_STOP

    def test_note_typing(self) -> None:
        vi = vc.parse("note : rappeler demain", language="fr")
        assert vi.intent == vc.TYPE_TEXT
        assert vi.params.get("text") == "rappeler demain"


class TestArabic:
    def test_open_app(self) -> None:
        vi = vc.parse("افتح نوت", language="ar")
        assert vi.intent == vc.OPEN_APP

    def test_next_page(self) -> None:
        assert vc.parse("الصفحة التاليه", language="ar").intent == vc.NEXT_PAGE

    def test_close_window(self) -> None:
        assert vc.parse("اغلق النافذه", language="ar").intent == vc.CLOSE_WINDOW

    def test_volume(self) -> None:
        vi = vc.parse("الصوت 70", language="ar")
        assert vi.intent == vc.VOLUME_SET
        assert abs(float(vi.params["percent"]) - 70.0) < 1e-6

    def test_open_multi_word_app(self) -> None:
        vi = vc.parse("افتح متصفح الكروم", language="ar")
        assert vi.intent == vc.OPEN_APP
        assert vi.params.get("app") == "متصفح الكروم"

    def test_garbage(self) -> None:
        assert vc.parse("كلمة عشوائية جدا", language="ar").intent == vc.NONE_INTENT

    def test_freezing_is_emergency(self) -> None:
        assert vc.parse("تجمد", language="ar").intent == vc.EMERGENCY_STOP


class TestConfidence:
    """Confidence is derived from how much of the spoken sentence matched a
    command — a clean full-sentence match outscores a lone keyword in chatter."""

    def test_full_match_high_confidence(self) -> None:
        assert vc.parse("open chrome").confidence >= 0.9
        assert vc.parse("next slide").confidence >= 0.9

    def test_chatter_lowers_confidence(self) -> None:
        full = vc.parse("open chrome").confidence
        partial = vc.parse("please can you open chrome for me").confidence
        assert partial < full

    def test_param_extraction_keeps_multiword(self) -> None:
        vi = vc.parse("type hello world")
        assert vi.params.get("text") == "hello world"


class TestLanguageDispatch:
    def test_language_normalization(self) -> None:
        assert vc.parse("next slide", language="en-US").intent == vc.NEXT_SLIDE
        assert vc.parse("suivante", language="fr-FR").intent in (vc.NEXT_PAGE, vc.GO_FORWARD)

    def test_params_propagate(self) -> None:
        vi = vc.parse("type hello world")
        assert vi.intent == vc.TYPE_TEXT
        assert vi.params.get("text") == "hello world"

    def test_type_with_colon(self) -> None:
        vi = vc.parse("type: call back at 3pm")
        assert vi.intent == vc.TYPE_TEXT
        assert vi.params.get("text") == "call back at 3pm"