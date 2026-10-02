"""
Regression tests for GUI responsiveness while commands run.

The window used to execute every command inline on the Qt thread, so
pyautogui, screenshots and the local LLM's HTTP timeout all blocked the event
loop and the window stopped repainting. These tests pin down that a command
runs on a worker thread and that the result comes back to the GUI thread.
"""

import os
import sys
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_APP = None


def setUpModule():
    global _APP
    from PySide6.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])


class _FakeWindow:
    """
    Carries only the attributes the MainWindow command methods touch.

    Binding the real methods to this stub lets the threading contract be tested
    without starting the camera, the microphone or the companion server.
    """

    def __init__(self):
        self.orchestrator = None
        self.qt_bridge = None
        self._command_in_flight = False
        self._current_command = None
        self.details = []
        self.log_refreshes = 0

    def _set_current_command(self, text):
        self._current_command = text

    def _refresh_command_busy_state(self):
        pass

    def _update_command_details(self, result):
        self.details.append(result)

    def _refresh_event_log(self):
        self.log_refreshes += 1


class _BlockingOrchestrator:
    """Records which thread executed it and blocks until released."""

    def __init__(self, delay=0.0):
        self.executing_thread = None
        self.calls = []
        self.delay = delay

    def execute_command_text(self, text, source="VOICE", latency_ms=0.0):
        self.executing_thread = threading.current_thread()
        self.calls.append((text, source))
        if self.delay:
            time.sleep(self.delay)
        return {"action": "TEST", "success": True, "source": source}


class TestCommandRunsOffGuiThread(unittest.TestCase):

    def setUp(self):
        from ui.main_window import MainWindow
        from core.qt_bridge import QtBridge

        self.window = _FakeWindow()
        self.window.orchestrator = _BlockingOrchestrator()
        self.window.qt_bridge = QtBridge()
        self.run_command = MainWindow._run_command.__get__(self.window)

        # Collect results delivered through the queued signal, and wire the
        # real slot exactly as MainWindow does so the busy flag lifecycle is
        # exercised rather than assumed.
        self.results = []
        self.window.qt_bridge.command_finished.connect(self.results.append)
        self.window.qt_bridge.command_finished.connect(
            MainWindow._on_command_finished.__get__(self.window)
        )

    def _drain(self, timeout=2.0):
        deadline = time.time() + timeout
        while not self.results and time.time() < deadline:
            _APP.processEvents()
            time.sleep(0.01)
        _APP.processEvents()

    def test_command_does_not_run_on_the_calling_thread(self):
        """
        The orchestrator must not be invoked on the thread that called
        _run_command, because that thread is the Qt event loop.
        """
        self.run_command("open chrome", source="VOICE")
        deadline = time.time() + 2.0
        while self.window.orchestrator.executing_thread is None and time.time() < deadline:
            time.sleep(0.005)

        self.assertIsNotNone(self.window.orchestrator.executing_thread)
        self.assertIsNot(
            self.window.orchestrator.executing_thread,
            threading.current_thread(),
        )

    def test_run_command_returns_promptly_even_for_a_slow_command(self):
        """
        This is the actual freeze: the call used to return only once the
        command finished.
        """
        self.window.orchestrator.delay = 1.0
        start = time.time()
        self.run_command("open chrome", source="VOICE")
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.5, "the GUI thread was blocked by the command")

    def test_result_is_delivered_via_the_qt_signal(self):
        self.run_command("open chrome", source="MANUAL")
        self._drain()
        self.assertEqual(len(self.results), 1)
        self.assertTrue(self.results[0]["success"])

    def test_source_is_preserved(self):
        self.run_command("volume up", source="MANUAL")
        self._drain()
        self.assertEqual(self.window.orchestrator.calls, [("volume up", "MANUAL")])

    def test_current_command_label_is_set_before_execution(self):
        self.run_command("open chrome", source="VOICE")
        self.assertEqual(self.window._current_command, '"open chrome"')
        self._drain()

    def test_busy_flag_is_raised_then_cleared(self):
        self.run_command("open chrome", source="VOICE")
        self.assertTrue(self.window._command_in_flight)
        self._drain()
        self.assertFalse(self.window._command_in_flight)

    def test_a_raising_orchestrator_still_reports_and_unlocks(self):
        """An exception must not leave the input disabled forever."""
        def _boom(*args, **kwargs):
            raise RuntimeError("orchestrator exploded")

        self.window.orchestrator.execute_command_text = _boom
        self.run_command("open chrome", source="VOICE")
        self._drain()

        self.assertEqual(len(self.results), 1)
        self.assertFalse(self.results[0]["success"])
        self.assertFalse(self.window._command_in_flight)


class TestCommandFinishedSlot(unittest.TestCase):
    """The result handler only touches widgets from the GUI thread."""

    def test_slot_updates_state_and_refreshes(self):
        from ui.main_window import MainWindow

        calls = []

        class _Sink:
            _command_in_flight = True

            def _refresh_command_busy_state(self):
                calls.append("busy")

            def _update_command_details(self, result):
                calls.append(("details", result))

            def _refresh_event_log(self):
                calls.append("log")

        MainWindow._on_command_finished.__get__(_Sink())({"success": True})
        self.assertEqual(calls, ["busy", ("details", {"success": True}), "log"])

    def test_emergency_stop_unlocks_a_stuck_command(self):
        from ui.main_window import MainWindow

        class _Sink:
            _command_in_flight = True

            def _refresh_command_busy_state(self):
                pass

        sink = _Sink()
        MainWindow._on_emergency_stop_during_command.__get__(sink)()
        self.assertFalse(sink._command_in_flight)


if __name__ == "__main__":
    unittest.main()