import os
import time
import threading
from typing import Dict, Any, Optional

from intents.intent_definitions import IntentType, IntentResult
from intents.local_ai_adapter import LocalAIAdapter
from intents.multimodal_fusion import MultimodalFusionEngine
from automation.windows_control import WindowsControlEngine
from automation.app_launcher import AppLauncher
from automation.file_manager import FileManager
from automation.browser_control import BrowserControl
from core.security_engine import SecurityEngine, RiskLevel
from core.macro_engine import MacroEngine
from core.logger import EventLogger
from core.event_bus import EventBus, EventType
from core.audio_effects import AudioEffects
from voice.tts_engine import TTSEngine
from core.custom_commands import CustomCommandManager
from config.settings_manager import SettingsManager


class CommandOrchestrator:
    """The central brain coordinating input, security validation, execution, logging, and audio feedback."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CommandOrchestrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.settings = SettingsManager()
        self.event_bus = EventBus()
        self.security = SecurityEngine()
        self.logger = EventLogger()
        self.tts = TTSEngine()
        self.audio_effects = AudioEffects()
        self.custom_cmd_mgr = CustomCommandManager()

        # Engine integrations
        self.ai_adapter = LocalAIAdapter()
        self.multimodal = MultimodalFusionEngine()
        self.win_control = WindowsControlEngine()
        self.app_launcher = AppLauncher()
        self.file_manager = FileManager()
        self.browser_control = BrowserControl()
        self.macro_engine = MacroEngine()

        self.current_language = self.settings.get("language", "ar")

    def execute_command_text(self, text: str, source: str = "VOICE", latency_ms: float = 0.0) -> Dict[str, Any]:
        """
        Entry point for incoming voice, GUI or API text commands.

        The emergency stop is checked here as well as in the gesture pipeline:
        this is the only gate that voice, the manual input and the companion
        REST API all pass through, so a halt has to be enforced before parsing
        rather than only where gestures are handled.
        """
        if self.security.is_emergency_stopped:
            return {
                "status": "BLOCKED",
                "reason": "EMERGENCY_STOP_ACTIVE",
                "action": "COMMAND_BLOCKED",
                "success": False,
            }

        self.current_language = self.settings.get("language", "ar")

        # Check for custom user-defined commands first
        match_custom = self.custom_cmd_mgr.find_match(text)
        if match_custom:
            return self._execute_custom_command(match_custom, source)

        # Parse intent
        intent_res: IntentResult = self.ai_adapter.parse_with_fallback(text)
        self.event_bus.publish(EventType.INTENT_PARSED, {
            "intent": intent_res.intent_type.name,
            "target": intent_res.target,
            "confidence": intent_res.confidence
        })

        # Handle Compound Plans (e.g. "افتح Chrome ثم افتح Downloads")
        if intent_res.intent_type == IntentType.COMPOUND_PLAN and intent_res.sub_intents:
            return self._execute_compound_plan(intent_res.sub_intents, source)

        return self._execute_single_intent(intent_res, source, latency_ms)

    def _execute_custom_command(self, cmd: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Executes a matched user-defined custom command through the Security Risk Engine."""
        risk_level_str = cmd.get("risk_level", "LOW")
        try:
            risk_level = RiskLevel[risk_level_str]
        except Exception:
            risk_level = RiskLevel.LOW

        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if not self.security.is_waiting_confirmation():
                prompt = self.security.create_confirmation_prompt(
                    intent_name=f"CUSTOM_{cmd['id']}",
                    risk_level=risk_level,
                    action_text=f"Exécuter la commande personnalisée : {cmd['name']}"
                )
                return {"status": "WAITING_CONFIRMATION", "prompt": prompt}

        act_type = cmd.get("action_type", "open_path")
        target = cmd.get("action_target", "")
        success = True

        try:
            if act_type == "open_path":
                self.file_manager.open_path(target)
            elif act_type == "launch_app":
                self.app_launcher.launch(target)
            elif act_type == "shortcut":
                self.win_control.press_hotkey(target)
            elif act_type == "type_text":
                self.win_control.type_text(target)
            elif act_type == "open_url":
                self.browser_control.open_url(target)
        except Exception as e:
            success = False
            print(f"[Orchestrator] Custom command error: {e}")

        # Log event in Audit Journal & trigger feedback
        self.logger.log_event(
            event_type="CUSTOM_COMMAND_EXECUTED",
            details={"cmd_id": cmd["id"], "name": cmd["name"], "target": target, "success": success},
            risk_level=risk_level_str
        )
        if success and self.settings.get("audio.feedback_enabled", True):
            self.audio_effects.play_success_tone()

        return {"status": "EXECUTED", "action": f"CUSTOM_{cmd['name']}", "success": success}

    def _execute_compound_plan(self, sub_intents, source: str) -> Dict[str, Any]:
        def _runner():
            for sub_res in sub_intents:
                # A halt raised mid-plan must abandon the remaining steps, not
                # just skip the next one, so every step is re-checked.
                if self.security.is_emergency_stopped:
                    break
                self._execute_single_intent(sub_res, source)
                time.sleep(0.8)

        threading.Thread(target=_runner, daemon=True).start()
        return {"action": "COMPOUND_PLAN_STARTED", "steps": len(sub_intents)}

    def _execute_single_intent(self, intent_res: IntentResult, source: str, latency_ms: float = 0.0) -> Dict[str, Any]:
        intent_name = intent_res.intent_type.name
        risk = self.security.evaluate_risk(intent_name)

        # A halt has to stop every action, including the LOW-risk ones that
        # normally bypass the confirmation gate. Re-checking here covers callers
        # that reach this method directly rather than through
        # execute_command_text.
        if self.security.is_emergency_stopped:
            return {
                "status": "BLOCKED",
                "reason": "EMERGENCY_STOP_ACTIVE",
                "action": "COMMAND_BLOCKED",
                "success": False,
            }

        # Check if Security Confirmation is required
        if self.security.requires_confirmation(intent_name):
            self.audio_effects.play_warning_prompt()
            prompt_text = {
                "ar": f"هل أنت متأكد من تنفيذ: {intent_res.original_text}؟",
                "fr": f"Êtes-vous sûr de vouloir exécuter: {intent_res.original_text}?",
                "en": f"Are you sure you want to execute: {intent_res.original_text}?"
            }.get(self.current_language, "Confirmation required")

            self.tts.speak(prompt_text, self.current_language)

            def _run_confirmed() -> Dict[str, Any]:
                result = self._dispatch_action(intent_res)
                self._log_result(intent_res, result, risk, source)
                return result

            self.security.request_confirmation(
                intent_name=intent_name,
                command_text=intent_res.original_text,
                action_fn=_run_confirmed
            )
            return {"status": "AWAITING_CONFIRMATION", "intent": intent_name, "risk": risk.value}

        # Otherwise execute immediately
        result = self._dispatch_action(intent_res)
        if result.get("success", True):
            self.audio_effects.play_command_success()
        self._log_result(intent_res, result, risk, source)

        return result

    def _log_result(
        self,
        intent_res: IntentResult,
        result: Dict[str, Any],
        risk: RiskLevel,
        source: str
    ) -> None:
        """Writes one audit record.

        A confirmed command is logged here too, from inside the action closure:
        logging only on the immediate path meant every gated command — the ones
        that actually delete and shut down — left no trace in the audit log.
        """
        self.logger.log(
            command=intent_res.original_text,
            intent=intent_res.intent_type.name,
            action=str(result.get("action", intent_res.intent_type.name)),
            result="SUCCESS" if result.get("success", True) else "FAILED",
            confidence=intent_res.confidence,
            risk_level=risk.value,
            source=source
        )

        # Optional offline spoken voice confirmation (configurable in settings)
        if result.get("success", True) and getattr(self, "tts", None) and self.settings.get("voice.spoken_feedback", False):
            lang = self.settings.get("language", "ar")
            if lang == "ar":
                phrase = "تم"
            elif lang == "fr":
                phrase = "C'est fait"
            else:
                phrase = "Done"
            try:
                self.tts.speak(phrase, lang=lang)
            except Exception as e:
                print(f"[CommandOrchestrator] Spoken feedback error: {e}")

    def _dispatch_action(self, intent_res: IntentResult) -> Dict[str, Any]:
        t = intent_res.intent_type
        target = intent_res.target

        # ==========================================
        # APPLICATIONS & WINDOWS
        # ==========================================
        if t == IntentType.LAUNCH_APP:
            if intent_res.parameters and intent_res.parameters.get("action") == "close":
                ok = self.app_launcher.close_app_by_name(target)
                return {"action": "CLOSE_APP", "success": ok}
            else:
                ok = self.app_launcher.launch(target)
                return {"action": "LAUNCH_APP", "target": target, "success": ok}

        elif t == IntentType.CLOSE_WINDOW:
            self.win_control.close_current_window()
            return {"action": "CLOSE_WINDOW", "success": True}

        elif t == IntentType.MINIMIZE_WINDOW:
            self.win_control.minimize_window()
            return {"action": "MINIMIZE_WINDOW", "success": True}

        elif t == IntentType.MAXIMIZE_WINDOW:
            self.win_control.maximize_window()
            return {"action": "MAXIMIZE_WINDOW", "success": True}

        elif t == IntentType.SWITCH_APP:
            self.win_control.switch_app()
            return {"action": "SWITCH_APP", "success": True}

        elif t == IntentType.SHOW_DESKTOP:
            self.win_control.show_desktop()
            return {"action": "SHOW_DESKTOP", "success": True}

        elif t == IntentType.SNAP_WINDOW_LEFT:
            self.win_control.snap_window_left()
            return {"action": "SNAP_WINDOW_LEFT", "success": True}

        elif t == IntentType.SNAP_WINDOW_RIGHT:
            self.win_control.snap_window_right()
            return {"action": "SNAP_WINDOW_RIGHT", "success": True}

        elif t == IntentType.TASK_VIEW:
            self.win_control.open_task_view()
            return {"action": "TASK_VIEW", "success": True}

        elif t == IntentType.NEW_DESKTOP:
            self.win_control.new_virtual_desktop()
            return {"action": "NEW_DESKTOP", "success": True}

        elif t == IntentType.CLOSE_DESKTOP:
            self.win_control.close_virtual_desktop()
            return {"action": "CLOSE_DESKTOP", "success": True}

        elif t == IntentType.NEXT_DESKTOP:
            self.win_control.next_virtual_desktop()
            return {"action": "NEXT_DESKTOP", "success": True}

        elif t == IntentType.PREV_DESKTOP:
            self.win_control.prev_virtual_desktop()
            return {"action": "PREV_DESKTOP", "success": True}

        elif t == IntentType.OPEN_TASK_MANAGER:
            self.win_control.open_task_manager()
            return {"action": "OPEN_TASK_MANAGER", "success": True}

        elif t == IntentType.EMPTY_RECYCLE_BIN:
            ok = self.win_control.empty_recycle_bin()
            msg = {
                "ar": "تم إفراغ سلة المحذوفات",
                "fr": "La corbeille a été vidée",
                "en": "Recycle bin emptied"
            }.get(self.current_language, "Recycle bin emptied")
            self.tts.speak(msg, self.current_language)
            return {"action": "EMPTY_RECYCLE_BIN", "success": ok}

        elif t == IntentType.ZOOM_IN:
            self.win_control.zoom_in()
            return {"action": "ZOOM_IN", "success": True}

        elif t == IntentType.ZOOM_OUT:
            self.win_control.zoom_out()
            return {"action": "ZOOM_OUT", "success": True}

        elif t == IntentType.ZOOM_RESET:
            self.win_control.zoom_reset()
            return {"action": "ZOOM_RESET", "success": True}

        elif t == IntentType.REFRESH_SCREEN:
            self.win_control.refresh()
            return {"action": "REFRESH_SCREEN", "success": True}

        # ==========================================
        # FILES & FOLDERS
        # ==========================================
        elif t == IntentType.OPEN_FOLDER:
            ok = self.file_manager.open_folder(target)
            return {"action": "OPEN_FOLDER", "target": target, "success": ok}

        elif t == IntentType.CREATE_FOLDER:
            ok = self.file_manager.create_folder(target)
            return {"action": "CREATE_FOLDER", "target": target, "success": ok}

        elif t == IntentType.OPEN_RECENT_FILE:
            ok = self.file_manager.open_recent_download()
            return {"action": "OPEN_RECENT_FILE", "success": ok}

        elif t == IntentType.DELETE_FILE:
            return self._delete_file_target(intent_res)

        elif t == IntentType.DELETE_FOLDER:
            return self._delete_folder_target(intent_res)

        # ==========================================
        # BROWSER
        # ==========================================
        elif t == IntentType.BROWSER_NEW_TAB:
            self.browser_control.new_tab()
            return {"action": "BROWSER_NEW_TAB", "success": True}

        elif t == IntentType.BROWSER_CLOSE_TAB:
            self.browser_control.close_tab()
            return {"action": "BROWSER_CLOSE_TAB", "success": True}

        elif t == IntentType.BROWSER_NEXT_TAB:
            self.browser_control.next_tab()
            return {"action": "BROWSER_NEXT_TAB", "success": True}

        elif t == IntentType.BROWSER_PREV_TAB:
            self.browser_control.prev_tab()
            return {"action": "BROWSER_PREV_TAB", "success": True}

        elif t == IntentType.BROWSER_SEARCH:
            self.browser_control.search_query(target)
            return {"action": "BROWSER_SEARCH", "target": target, "success": True}

        elif t == IntentType.NAVIGATE_BACK:
            self.browser_control.go_back()
            return {"action": "NAVIGATE_BACK", "success": True}

        elif t == IntentType.NAVIGATE_FORWARD:
            self.browser_control.go_forward()
            return {"action": "NAVIGATE_FORWARD", "success": True}

        # ==========================================
        # SYSTEM & MEDIA
        # ==========================================
        elif t == IntentType.VOLUME_UP:
            self.win_control.volume_up()
            return {"action": "VOLUME_UP", "success": True}

        elif t == IntentType.VOLUME_DOWN:
            self.win_control.volume_down()
            return {"action": "VOLUME_DOWN", "success": True}

        elif t == IntentType.VOLUME_MUTE:
            self.win_control.volume_mute()
            return {"action": "VOLUME_MUTE", "success": True}

        elif t == IntentType.MEDIA_PLAY_PAUSE:
            self.win_control.media_play_pause()
            return {"action": "MEDIA_PLAY_PAUSE", "success": True}

        elif t == IntentType.MEDIA_NEXT:
            self.win_control.media_next()
            return {"action": "MEDIA_NEXT", "success": True}

        elif t == IntentType.MEDIA_PREVIOUS:
            self.win_control.media_prev()
            return {"action": "MEDIA_PREVIOUS", "success": True}

        elif t == IntentType.BRIGHTNESS_UP:
            self.win_control.brightness_up()
            return {"action": "BRIGHTNESS_UP", "success": True}

        elif t == IntentType.BRIGHTNESS_DOWN:
            self.win_control.brightness_down()
            return {"action": "BRIGHTNESS_DOWN", "success": True}

        elif t == IntentType.SCREENSHOT:
            path = self.win_control.take_screenshot()
            msg = {
                "ar": "تم التقاط لقطة الشاشة",
                "fr": "Capture d'écran enregistrée",
                "en": "Screenshot captured"
            }.get(self.current_language, "Screenshot saved")
            self.tts.speak(msg, self.current_language)
            return {"action": "SCREENSHOT", "path": path, "success": True}

        # ==========================================
        # CLIPBOARD
        # ==========================================
        elif t == IntentType.CLIPBOARD_COPY:
            self.win_control.copy()
            return {"action": "CLIPBOARD_COPY", "success": True}

        elif t == IntentType.CLIPBOARD_PASTE:
            self.win_control.paste()
            return {"action": "CLIPBOARD_PASTE", "success": True}

        elif t == IntentType.CLIPBOARD_CUT:
            self.win_control.cut()
            return {"action": "CLIPBOARD_CUT", "success": True}

        elif t == IntentType.SELECT_ALL:
            self.win_control.select_all()
            return {"action": "SELECT_ALL", "success": True}

        elif t == IntentType.UNDO:
            self.win_control.undo()
            return {"action": "UNDO", "success": True}

        # ==========================================
        # SCROLLING
        # ==========================================
        elif t == IntentType.SCROLL_UP:
            self.win_control.scroll(500)
            return {"action": "SCROLL_UP", "success": True}

        elif t == IntentType.SCROLL_DOWN:
            self.win_control.scroll(-500)
            return {"action": "SCROLL_DOWN", "success": True}

        # ==========================================
        # POWER (Confirmed actions)
        # ==========================================
        elif t == IntentType.SYSTEM_LOCK:
            self.win_control.lock_pc()
            return {"action": "SYSTEM_LOCK", "success": True}

        elif t == IntentType.SYSTEM_RESTART:
            self.win_control.restart_pc()
            return {"action": "SYSTEM_RESTART", "success": True}

        elif t == IntentType.SYSTEM_SHUTDOWN:
            self.win_control.shutdown_pc()
            return {"action": "SYSTEM_SHUTDOWN", "success": True}

        # ==========================================
        # MULTIMODAL & VISION
        # ==========================================
        elif t in (IntentType.MULTIMODAL_CLICK_TARGET, IntentType.MULTIMODAL_OPEN_TARGET, IntentType.FIND_ELEMENT):
            cur_pos = self.win_control.get_cursor_position()
            return self.multimodal.process_multimodal_intent(intent_res, cur_pos)

        # ==========================================
        # MACROS
        # ==========================================
        elif t == IntentType.EXECUTE_MACRO:
            ok = self.macro_engine.execute_macro(target, self._execute_macro_step)
            return {"action": "EXECUTE_MACRO", "macro": target, "success": ok}

        return {"action": "UNKNOWN_INTENT", "success": False}

    def _resolve_existing_path(self, target: Optional[str]) -> Optional[str]:
        """
        Resolves a spoken folder/file alias to an absolute path that exists.

        Resolution is deliberately narrow: a known alias, an absolute path, or a
        path relative to the last folder that was opened. Nothing is invented,
        so a misheard word cannot resolve to an unrelated directory.
        """
        if not target:
            return None
        from automation.file_manager import STANDARD_FOLDERS

        candidate = target.strip()
        if not candidate:
            return None

        alias_path = STANDARD_FOLDERS.get(candidate.lower())
        if alias_path:
            return alias_path if os.path.exists(alias_path) else None

        expanded = os.path.expanduser(candidate)
        if os.path.exists(expanded):
            return expanded

        relative = os.path.join(self.file_manager.last_accessed_dir, candidate)
        if os.path.exists(relative):
            return relative

        return None

    def _delete_file_target(self, intent_res: IntentResult) -> Dict[str, Any]:
        """
        Deletes a single named file after the security gate has cleared it.

        Reaching this point means the gate already ran, so the only remaining
        question is whether the target actually resolves. A refusal here is
        reported as a failure so the audit log never records a deletion that
        did not happen.
        """
        path = self._resolve_existing_path(intent_res.target)
        if path is None or not os.path.isfile(path):
            return {
                "action": "DELETE_FILE",
                "success": False,
                "reason": "TARGET_NOT_RESOLVED",
                "target": intent_res.target,
            }
        ok = self.file_manager.delete_path(path)
        return {"action": "DELETE_FILE", "success": bool(ok), "target": path}

    def _delete_folder_target(self, intent_res: IntentResult) -> Dict[str, Any]:
        """Deletes a whole directory. Gated as HIGH risk before it gets here."""
        path = self._resolve_existing_path(intent_res.target)
        if path is None or not os.path.isdir(path):
            return {
                "action": "DELETE_FOLDER",
                "success": False,
                "reason": "TARGET_NOT_RESOLVED",
                "target": intent_res.target,
            }
        ok = self.file_manager.delete_path(path)
        return {"action": "DELETE_FOLDER", "success": bool(ok), "target": path}

    def _execute_macro_step(self, action: str, target: Any):
        """Dispatches an individual macro step."""
        if action == "LAUNCH_APP":
            self.app_launcher.launch(str(target))
        elif action == "VOLUME_SET":
            self.win_control.set_volume_percent(int(target))
        elif action == "BRIGHTNESS_SET":
            self.win_control.set_brightness_percent(int(target))
        elif action == "OPEN_FOLDER":
            self.file_manager.open_folder(str(target))
        elif action == "SHORTCUT" or action == "KEY_PRESS":
            self.win_control.press_key(str(target))
        elif action == "TYPE_TEXT":
            self.win_control.type_text(str(target))
        elif action == "HOTKEY":
            keys = [k.strip().lower() for k in str(target).split("+")]
            import pyautogui
            pyautogui.hotkey(*keys)
        elif action == "WAIT":
            import time
            time.sleep(float(target))
