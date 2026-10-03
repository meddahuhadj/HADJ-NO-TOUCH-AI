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
    arm_state_changed = Signal(bool)                # is_armed
    gesture_diagnostics = Signal(str, str, float, bool, float) # (gesture_name, diagnostic_key, confidence, is_armed, progress)
    speech_state = Signal(bool)                     # is_listening
    speech_command = Signal(str, float)             # (command_text, latency_ms)
    emergency_stop = Signal(str)                    # reason
    security_prompt = Signal(dict)                  # prompt payload
    security_cleared = Signal(str)                  # reason the prompt closed
    command_finished = Signal(dict)                 # command result from a worker thread
    app_profile_changed = Signal(str, str)          # (profile_id, app_info)
    camera_status_changed = Signal(bool, str)       # (is_available, reason)

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
