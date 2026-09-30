import time
from typing import Optional, Tuple, Dict, Any
from intents.intent_definitions import IntentType, IntentResult
from automation.windows_control import WindowsControlEngine
from vision.screen_understanding import ScreenUnderstandingEngine


class MultimodalFusionEngine:
    """Fuses temporal spatial inputs (hand pointer position, screen vision) with voice intents."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MultimodalFusionEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.win = WindowsControlEngine()
        self.screen_vision = ScreenUnderstandingEngine()

        # Cache last highlighted or pointed UI target
        self.last_target_location: Optional[Tuple[int, int]] = None
        self.last_target_type: Optional[str] = None
        self.last_target_timestamp: float = 0.0

    def register_pointed_target(self, screen_x: int, screen_y: int, target_type: str = "POINTED_OBJECT"):
        """Called by camera/gesture stream when user points steadily at a location."""
        self.last_target_location = (screen_x, screen_y)
        self.last_target_type = target_type
        self.last_target_timestamp = time.time()

    def process_multimodal_intent(self, intent_res: IntentResult, current_cursor_pos: Tuple[int, int]) -> Dict[str, Any]:
        """
        Executes unified multimodal action based on intent and spatial target.
        """
        now = time.time()
        # If pointing happened within last 3 seconds, prioritize pointed location, otherwise current cursor position
        if self.last_target_location and (now - self.last_target_timestamp) < 3.0:
            target_pos = self.last_target_location
        else:
            target_pos = current_cursor_pos

        if intent_res.intent_type == IntentType.MULTIMODAL_CLICK_TARGET:
            self.win.click(target_pos[0], target_pos[1])
            return {
                "action": "CLICK_POINTED_TARGET",
                "coords": target_pos,
                "success": True
            }

        elif intent_res.intent_type == IntentType.MULTIMODAL_OPEN_TARGET:
            self.win.double_click(target_pos[0], target_pos[1])
            return {
                "action": "DOUBLE_CLICK_POINTED_TARGET",
                "coords": target_pos,
                "success": True
            }

        elif intent_res.intent_type == IntentType.FIND_ELEMENT:
            if intent_res.target == "close_button":
                close_pos = self.screen_vision.locate_active_window_close_button()
                if close_pos:
                    self.win.move_mouse(close_pos[0], close_pos[1])
                    self.register_pointed_target(close_pos[0], close_pos[1], "CLOSE_BUTTON")
                    return {
                        "action": "LOCATE_CLOSE_BUTTON",
                        "coords": close_pos,
                        "success": True
                    }

        return {"action": "NONE", "success": False}
