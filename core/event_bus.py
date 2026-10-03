import threading
import queue
from typing import Callable, Dict, List, Any
from enum import Enum, auto


class EventType(Enum):
    # System events
    SYSTEM_STARTED = auto()
    SYSTEM_STOPPED = auto()
    EMERGENCY_STOP = auto()
    EMERGENCY_RESTORED = auto()
    PROFILE_CHANGED = auto()
    APP_PROFILE_CHANGED = auto()
    SETTINGS_UPDATED = auto()
    PERFORMANCE_STATS = auto()
    CALIBRATION_STARTED = auto()
    CALIBRATION_PHASE_CHANGED = auto()
    CALIBRATION_APPLIED = auto()
    CALIBRATION_ADAPTED = auto()

    # Voice events
    WAKE_WORD_DETECTED = auto()
    SPEECH_LISTENING_START = auto()
    SPEECH_LISTENING_END = auto()
    SPEECH_RECOGNIZED = auto()
    DICTATION_INPUT = auto()

    # Gesture & Vision events
    FRAME_PROCESSED = auto()
    HAND_DETECTED = auto()
    GESTURE_RECOGNIZED = auto()
    GESTURE_ARM_TOGGLED = auto()
    CURSOR_MOVED = auto()
    HEAD_POSE_CHANGED = auto()
    GAZE_POINT_UPDATED = auto()

    # Intent & Command events
    INTENT_PARSED = auto()
    MULTIMODAL_TRIGGER = auto()
    SECURITY_CONFIRM_REQUEST = auto()
    SECURITY_CONFIRMED = auto()
    SECURITY_REJECTED = auto()
    COMMAND_EXECUTING = auto()
    COMMAND_COMPLETED = auto()
    COMMAND_FAILED = auto()

    # Macro & UI events
    MACRO_RECORD_START = auto()
    MACRO_RECORD_STOP = auto()
    MACRO_EXECUTED = auto()
    NOTIFICATION = auto()


class EventBus:
    """Thread-safe publish-subscribe Event Bus for decoupling modules."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._subscribers: Dict[EventType, List[Callable[[Any], None]]] = {}
                cls._instance._any_subscribers: List[Callable[[EventType, Any], None]] = []
        return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[EventType, Any], None]) -> None:
        with self._lock:
            if callback not in self._any_subscribers:
                self._any_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        with self._lock:
            if event_type in self._subscribers and callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event_type: EventType, data: Any = None) -> None:
        callbacks_to_run = []
        with self._lock:
            if event_type in self._subscribers:
                callbacks_to_run.extend(self._subscribers[event_type])
            any_cbs = list(self._any_subscribers)

        for cb in callbacks_to_run:
            try:
                cb(data)
            except Exception as e:
                print(f"[EventBus] Error in handler for {event_type.name}: {e}")

        for cb in any_cbs:
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"[EventBus] Error in global handler for {event_type.name}: {e}")

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self._any_subscribers.clear()
