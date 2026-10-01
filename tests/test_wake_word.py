"""
Unit tests for the wake word detector and the speech engine's gating rules.

The wake word is the only thing standing between room noise and an action on
the user's machine, so these tests are as much about what must NOT wake the
engine as about what must.
"""

import os
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from voice.wake_word import WakeWordDetector


class TestWakeWordDetector(unittest.TestCase):

    def setUp(self):
        self.detector = WakeWordDetector()

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #

    def test_wake_word_prefix_is_detected(self):
        for text in ("hey hadj", "hey hadj open chrome", "bonjour hadj ouvre chrome"):
            hit, _ = self.detector.check_wake_word(text)
            self.assertTrue(hit, text)

    def test_wake_word_in_the_middle_is_detected(self):
        hit, remainder = self.detector.check_wake_word("ok hey hadj open chrome")
        self.assertTrue(hit)
        self.assertIn("open chrome", remainder)

    def test_remainder_is_the_command(self):
        self.assertEqual(
            self.detector.check_wake_word("hey hadj open chrome")[1], "open chrome"
        )
        self.assertEqual(self.detector.check_wake_word("hey hadj")[1], "")

    def test_leading_punctuation_is_stripped_from_the_remainder(self):
        self.assertEqual(
            self.detector.check_wake_word("hey hadj, open chrome")[1], "open chrome"
        )

    def test_arabic_wake_word(self):
        hit, remainder = self.detector.check_wake_word("يا حاج افتح كروم")
        self.assertTrue(hit)
        self.assertTrue(remainder)

    def test_detection_is_case_insensitive(self):
        self.assertTrue(self.detector.check_wake_word("HEY HADJ open chrome")[0])

    def test_surrounding_whitespace_is_tolerated(self):
        self.assertTrue(self.detector.check_wake_word("   hey hadj   ")[0])

    def test_ordinary_sentence_does_not_wake_the_engine(self):
        for text in ("open chrome", "what is the weather", "hello there",
                     "volume up", "the meeting is at noon"):
            hit, _ = self.detector.check_wake_word(text)
            self.assertFalse(hit, text)

    def test_empty_text_does_not_wake_the_engine(self):
        self.assertFalse(self.detector.check_wake_word("")[0])
        self.assertFalse(self.detector.check_wake_word("    ")[0])

    def test_no_wake_word_returns_the_text_unchanged(self):
        _, remainder = self.detector.check_wake_word("open chrome")
        self.assertEqual(remainder, "open chrome")

    # ------------------------------------------------------------------ #
    # The wake word must open the phrase, not appear anywhere in it
    # ------------------------------------------------------------------ #

    def test_the_name_inside_a_sentence_does_not_wake_the_engine(self):
        """
        The regression that motivated requiring the wake word to lead.

        Matching anywhere armed the engine on "the hadj committee meets
        tomorrow", so the *next* unrelated sentence was treated as a command.
        """
        for text in ("the hadj committee meets tomorrow",
                     "my cousin haj came by",
                     "thanks hadj for the help"):
            hit, _ = self.detector.check_wake_word(text)
            self.assertFalse(hit, text)

    def test_a_leading_greeting_is_tolerated(self):
        for text in ("ok hey hadj open chrome", "hey hey hadj open chrome",
                     "bonjour hadj ouvre chrome"):
            hit, remainder = self.detector.check_wake_word(text)
            self.assertTrue(hit, text)
            self.assertTrue(remainder, text)

    def test_the_wake_word_is_not_matched_inside_a_longer_word(self):
        for text in ("hadji opened it", "blahblah open chrome"):
            hit, _ = self.detector.check_wake_word(text)
            self.assertFalse(hit, text)


class TestEmergencyStopPhrases(unittest.TestCase):

    def setUp(self):
        self.detector = WakeWordDetector()

    def test_explicit_emergency_phrases(self):
        for text in ("stop hadj", "emergency stop", "توقف يا حاج", "arrête hadj"):
            self.assertTrue(self.detector.check_emergency_stop(text), text)

    def test_emergency_phrase_inside_a_sentence(self):
        self.assertTrue(
            self.detector.check_emergency_stop("please emergency stop now")
        )

    def test_ordinary_text_is_not_an_emergency(self):
        for text in ("open chrome", "what time is it", "volume up"):
            self.assertFalse(self.detector.check_emergency_stop(text), text)

    def test_empty_text_is_not_an_emergency(self):
        self.assertFalse(self.detector.check_emergency_stop(""))
        self.assertFalse(self.detector.check_emergency_stop("   "))

    def test_emergency_phrase_is_not_matched_inside_a_longer_word(self):
        """Word boundaries keep "stopwatch" from halting the machine."""
        self.assertFalse(self.detector.check_emergency_stop("stopwatch"))

    # ------------------------------------------------------------------ #
    # A bare verb only halts when it is all that was said
    # ------------------------------------------------------------------ #

    def test_ordinary_sentences_containing_stop_are_not_emergencies(self):
        """
        The regression that motivated splitting the emergency list.

        "stop" was matched anywhere on word boundaries, so "do not stop" and
        "non-stop running" halted the machine. An emergency that fires on
        ordinary speech trains the user to ignore it.
        """
        for text in ("do not stop", "non-stop running", "the bus will stop here",
                     "it stops raining"):
            self.assertFalse(self.detector.check_emergency_stop(text), text)

    def test_a_bare_stop_on_its_own_is_an_emergency(self):
        for text in ("stop", "stop.", "STOP", "arrête", "توقف", "قف"):
            self.assertTrue(self.detector.check_emergency_stop(text), text)

    def test_explicit_emergency_phrases_still_match_anywhere(self):
        for text in ("please emergency stop now", "i need emergency stop",
                     "stop hadj please"):
            self.assertTrue(self.detector.check_emergency_stop(text), text)

    def test_emergency_phrases_beat_the_wake_word(self):
        """A halt must not be softened by the name appearing in the phrase."""
        self.assertTrue(self.detector.check_emergency_stop("stop hadj"))


class TestSpeechEngineGate(unittest.TestCase):
    """
    The SpeechEngine is a singleton that owns real audio hardware, so these
    cases build it from a bare instance with mocked collaborators. What is
    exercised is the gate itself, not speech recognition.
    """

    def _engine(self, hands_free=False, security=None):
        from voice.speech_engine import SpeechEngine

        engine = SpeechEngine.__new__(SpeechEngine)
        engine.settings = mock.MagicMock()
        engine.settings.get.side_effect = lambda key, default=None: {
            "voice.hands_free_mode": hands_free,
            "voice.listen_timeout_seconds": 6.0,
            "language": "en",
        }.get(key, default)

        engine.event_bus = mock.MagicMock()
        engine.audio_effects = mock.MagicMock()
        engine.tts = mock.MagicMock()
        engine.qt_bridge = mock.MagicMock()
        engine.command_handler = mock.MagicMock()
        engine.dictation = mock.MagicMock()
        engine.ai_adapter = mock.MagicMock()

        engine.security = security or _FakeSecurity()
        engine.wake_detector = WakeWordDetector()
        engine.is_listening = False
        engine.listening_start_time = 0.0
        engine.listen_timeout = 6.0
        engine.current_language = "en"
        engine.hands_free_enabled = hands_free
        return engine

    # ------------------------------------------------------------------ #
    # Without the wake word nothing must happen
    # ------------------------------------------------------------------ #

    def test_idle_speech_does_not_reach_the_command_handler(self):
        engine = self._engine()
        engine.on_speech_received("open chrome")
        engine.command_handler.assert_not_called()
        engine.qt_bridge.speech_command.emit.assert_not_called()

    def test_idle_speech_does_not_reach_dictation(self):
        engine = self._engine()
        engine.on_speech_received("write a report")
        engine.dictation.handle_voice_edit_or_dictation.assert_not_called()

    def test_idle_speech_publishes_a_wake_word_required_notice(self):
        engine = self._engine()
        engine.on_speech_received("open chrome")
        engine.event_bus.publish.assert_called()
        _event, payload = engine.event_bus.publish.call_args[0]
        self.assertEqual(payload["message"], "WAKE_WORD_REQUIRED")

    # ------------------------------------------------------------------ #
    # The wake word opens the gate
    # ------------------------------------------------------------------ #

    def test_wake_word_alone_arms_the_engine(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        self.assertTrue(engine.is_listening)
        engine.tts.speak.assert_called()

    def test_conversation_mentioning_the_name_does_not_arm_the_engine(self):
        """
        Regression: the name used to arm the engine from anywhere in a
        sentence, so the next unrelated remark was executed as a command.
        """
        engine = self._engine()
        engine.on_speech_received("the hadj committee meets tomorrow")
        self.assertFalse(engine.is_listening)

        engine.on_speech_received("open chrome")
        engine.command_handler.assert_not_called()

    def test_ordinary_sentence_containing_stop_is_not_an_emergency(self):
        engine = self._engine()
        engine.on_speech_received("do not stop")
        self.assertFalse(engine.security.stopped)

    def test_wake_word_plus_command_dispatches_immediately(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj open chrome")
        engine.command_handler.assert_called_once()
        self.assertIn("open chrome",
                      engine.command_handler.call_args[0][0])

    def test_command_after_the_wake_word_is_dispatched(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        self.assertTrue(engine.is_listening)

        engine.on_speech_received("open chrome")
        engine.command_handler.assert_called_once()
        self.assertFalse(engine.is_listening)

    def test_the_listening_window_closes_after_a_command(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        engine.on_speech_received("open chrome")
        self.assertFalse(engine.is_listening)

    def test_the_listening_window_expires(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        engine.listening_start_time -= 100.0
        engine.on_speech_received("open chrome")
        engine.command_handler.assert_not_called()

    # ------------------------------------------------------------------ #
    # Hands-free mode is opt-in
    # ------------------------------------------------------------------ #

    def test_hands_free_mode_allows_idle_commands(self):
        from intents.intent_definitions import IntentType
        engine = self._engine(hands_free=True)
        # Dictation is tried first and returns False so the parser is reached.
        engine.dictation.handle_voice_edit_or_dictation.return_value = False
        engine.ai_adapter.parse_with_fallback.return_value = mock.Mock(
            intent_type=IntentType.LAUNCH_APP
        )
        engine.on_speech_received("open chrome")
        engine.command_handler.assert_called_once()

    def test_hands_free_mode_allows_idle_dictation(self):
        engine = self._engine(hands_free=True)
        engine.dictation.handle_voice_edit_or_dictation.return_value = True
        engine.on_speech_received("write a report")
        engine.dictation.handle_voice_edit_or_dictation.assert_called_once()

    def test_hands_free_mode_still_ignores_unknown_text(self):
        from intents.intent_definitions import IntentType
        engine = self._engine(hands_free=True)
        engine.dictation.handle_voice_edit_or_dictation.return_value = False
        engine.ai_adapter.parse_with_fallback.return_value = mock.Mock(
            intent_type=IntentType.UNKNOWN
        )
        engine.on_speech_received("what is the weather")
        engine.command_handler.assert_not_called()

    # ------------------------------------------------------------------ #
    # Emergency stop and confirmation take priority
    # ------------------------------------------------------------------ #

    def test_emergency_phrase_halts_without_the_wake_word(self):
        engine = self._engine()
        engine.on_speech_received("emergency stop")
        self.assertTrue(engine.security.stopped)
        engine.command_handler.assert_not_called()

    def test_confirmation_is_accepted_without_the_wake_word(self):
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        engine.on_speech_received("yes")
        self.assertTrue(security.confirmed)

    def test_rejection_is_accepted_without_the_wake_word(self):
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        engine.on_speech_received("no")
        self.assertTrue(security.cancelled)

    def test_an_unrelated_word_does_not_confirm_a_prompt(self):
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        engine.on_speech_received("open chrome")
        self.assertFalse(security.confirmed)
        self.assertFalse(security.cancelled)

    def test_an_ordinary_sentence_does_not_reject_a_prompt(self):
        """
        Regression: "no" was matched as a substring, so "no problem thanks"
        and "cancel my subscription" rejected the pending action.
        """
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        for text in ("no problem thanks", "cancel my subscription",
                     "nothing to report", "can you cancel the noise"):
            engine.on_speech_received(text)
            self.assertFalse(security.cancelled, text)

    def test_an_ordinary_sentence_does_not_confirm_a_prompt(self):
        """
        Regression: "confirm" was a substring, so "the confirmation is fine"
        approved a destructive action.
        """
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        for text in ("the confirmation is fine",
                     "confirm the file was already deleted",
                     "yes but actually delete everything"):
            engine.on_speech_received(text)
            self.assertFalse(security.confirmed, text)

    def test_a_command_after_a_prompt_still_reaches_the_gate(self):
        """A non-decision must fall through, not be swallowed by the prompt."""
        security = _FakeSecurity(waiting=True)
        engine = self._engine(security=security)
        engine.on_speech_received("hey hadj open chrome")
        self.assertFalse(security.confirmed)
        self.assertFalse(security.cancelled)
        engine.command_handler.assert_called_once()


class TestConfirmationReplies(unittest.TestCase):
    """
    The prompt reply matcher decides whether a destructive action proceeds.
    It is therefore required to be strict: silence is safer than agreement.
    """

    def setUp(self):
        from voice.speech_engine import (
            AFFIRMATIVE_REPLIES,
            NEGATIVE_REPLIES,
            is_confirmation_reply,
        )
        self.affirmative = AFFIRMATIVE_REPLIES
        self.negative = NEGATIVE_REPLIES
        self.is_reply = is_confirmation_reply

    def test_common_affirmatives(self):
        for text in ("yes", "Yes.", "yep", "yeah", "sure", "ok", "okay",
                     "confirm", "oui", "نعم", "أكيد", "تمام", "موافق"):
            self.assertTrue(self.is_reply(text, self.affirmative), text)

    def test_common_negatives(self):
        for text in ("no", "No.", "nope", "cancel", "abort", "stop",
                     "do not", "non", "لا", "تراجع", "إلغاء"):
            self.assertTrue(self.is_reply(text, self.negative), text)

    def test_politeness_does_not_change_a_decision(self):
        self.assertTrue(self.is_reply("yes please", self.affirmative))
        self.assertTrue(self.is_reply("cancel please", self.negative))
        self.assertTrue(self.is_reply("oui merci", self.affirmative))
        self.assertTrue(self.is_reply("من فضلك نعم", self.affirmative))

    def test_multi_word_decisions(self):
        self.assertTrue(self.is_reply("go ahead", self.affirmative))
        self.assertTrue(self.is_reply("do it", self.affirmative))
        self.assertTrue(self.is_reply("do not do it", self.negative))

    def test_ordinary_sentences_never_decide(self):
        """
        Each of these contains a decision word as a substring of longer
        speech; none of them may resolve a prompt.
        """
        for text in ("no problem thanks", "cancel my subscription",
                     "the confirmation is fine", "notify me",
                     "nothing to report", "knowledge base", "nonetheless",
                     "i do not know", "nordic nord", "yes or no",
                     "either yes or no", "stop the music and open chrome"):
            self.assertFalse(self.is_reply(text, self.affirmative), text)
            self.assertFalse(self.is_reply(text, self.negative), text)

    def test_an_empty_reply_never_decides(self):
        for text in ("", "   ", "\n"):
            self.assertFalse(self.is_reply(text, self.affirmative))
            self.assertFalse(self.is_reply(text, self.negative))

    def test_a_decision_never_satisfies_both_lists(self):
        for text in ("yes", "no", "cancel", "confirm", "لا", "نعم"):
            both = (self.is_reply(text, self.affirmative)
                    and self.is_reply(text, self.negative))
            self.assertFalse(both, text)


class TestSpeechEngineLanguageAndInput(unittest.TestCase):
    """Language switching and input hygiene on the same gated entry point."""

    _engine = TestSpeechEngineGate._engine

    # ------------------------------------------------------------------ #
    # Language switching
    # ------------------------------------------------------------------ #

    def test_language_request_needs_the_wake_word(self):
        engine = self._engine()
        engine.on_speech_received("switch to french")
        self.assertEqual(engine.current_language, "en")

    def test_language_request_inside_the_listening_window_is_honoured(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        engine.on_speech_received("french")
        self.assertEqual(engine.current_language, "fr")

    def test_ordinary_sentence_does_not_switch_the_language(self):
        engine = self._engine()
        engine.on_speech_received("hey hadj")
        engine.on_speech_received("read this english article")
        self.assertEqual(engine.current_language, "en")

    # ------------------------------------------------------------------ #
    # Input hygiene
    # ------------------------------------------------------------------ #

    def test_empty_input_is_ignored(self):
        engine = self._engine()
        for text in ("", "   ", "\n"):
            engine.on_speech_received(text)
        engine.command_handler.assert_not_called()
        engine.event_bus.publish.assert_not_called()

    def test_inject_text_command_goes_through_the_same_gate(self):
        """The GUI and tests share this path, so it must not be a bypass."""
        engine = self._engine()
        engine.inject_text_command("open chrome")
        engine.command_handler.assert_not_called()

        engine.inject_text_command("hey hadj open chrome")
        engine.command_handler.assert_called_once()


class _FakeSecurity:
    """Minimal SecurityEngine stand-in that records what the engine asked of it."""

    def __init__(self, waiting: bool = False):
        self.stopped = False
        self.waiting = waiting
        self.confirmed = False
        self.cancelled = False

    def is_emergency_stopped(self):
        return self.stopped

    def is_waiting_confirmation(self):
        return self.waiting

    def trigger_emergency_stop(self, reason=""):
        self.stopped = True

    def confirm_pending(self, source=""):
        self.confirmed = True
        self.waiting = False

    def cancel_pending(self, reason=""):
        self.cancelled = True
        self.waiting = False


if __name__ == "__main__":
    unittest.main()