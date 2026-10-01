from PySide6.QtCore import QObject, Signal


class QtBridge(QObject):
    """
    Thread-safe signal dispatcher bridging background worker threads (OpenCV, MediaPipe, Audio)
    with the PySide6 main GUI event loop via Qt QueuedConnections.
    Completely prevents GUI freezes, deadlocks, and 'Not Responding' states.
    """

    _instance = None

    frame_ready = Signal(object, str, float)       # (frame_bgr, gesture_name, confidence)
    cursor_moved = Signal(int, int)                 # (screen_x, screen_y)
    gesture_detected = Signal(str, float)           # (gesture_name, confidence)
    speech_state = Signal(bool)                     # is_listening
    speech_command = Signal(str, float)             # (command_text, latency_ms)
    emergency_stop = Signal(str)                    # reason
    security_prompt = Signal(dict)                  # prompt payload
    security_cleared = Signal(str)                  # reason the prompt closed

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(QtBridge, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super(QtBridge, self).__init__()
        self._initialized = True
