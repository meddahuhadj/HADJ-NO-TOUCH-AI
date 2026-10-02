"""
Internationalisation layer for HADJ NO-TOUCH OFFLINE AI.

Every user-facing string in the interface is resolved through :func:`tr`, so the
whole application (main window, dialogs, overlays, system tray, audit log)
follows the language selected in the settings under the ``language`` key.

Supported languages: Arabic (ar, right-to-left), French (fr), English (en).
English acts as the fallback for any missing key.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List

from config.settings_manager import SettingsManager

# --------------------------------------------------------------------------- #
# Language registry
# --------------------------------------------------------------------------- #

FALLBACK_LANGUAGE = "en"
RTL_LANGUAGES = ("ar",)

LANGUAGES: Dict[str, str] = {
    "ar": "العربية",
    "fr": "Français",
    "en": "English",
}

# Per-language font stacks. Arabic needs a face with proper Arabic shaping;
# Segoe UI and Tahoma both cover it on Windows.
FONT_STACKS: Dict[str, str] = {
    "ar": "'Segoe UI', 'Tahoma', 'Traditional Arabic', 'Arial', sans-serif",
    "fr": "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', sans-serif",
    "en": "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', sans-serif",
}

MONO_STACK = "'Cascadia Mono', 'Consolas', 'Courier New', monospace"


# --------------------------------------------------------------------------- #
# Reference catalogue (English)
# --------------------------------------------------------------------------- #

_EN: Dict[str, str] = {
    # ---------------- Application ----------------
    "app.name": "HADJ NO-TOUCH OFFLINE AI",
    "app.tagline": "Complete touchless control — voice, gesture, vision and offline AI",
    "app.offline_first": "Offline first",
    "app.tray_tooltip": "HADJ NO-TOUCH OFFLINE AI",

    # ---------------- Shared vocabulary ----------------
    "common.on": "ON",
    "common.off": "OFF",
    "common.close": "Close",
    "common.done": "Done",
    "common.cancel": "Cancel",
    "common.back": "Back",
    "common.next": "Next",
    "common.finish": "Finish",
    "common.delete": "Delete",
    "common.run": "Run",
    "common.execute": "Execute",
    "common.language": "Language",
    "common.yes": "Yes",
    "common.no": "No",
    "common.confidence": "Conf",
    "common.step_of": "STEP {current} OF {total}",

    # ---------------- Main window ----------------
    "main.emergency_stop": "⚠  STOP HADJ",
    "main.emergency_restore": "↺  Restore system",
    "main.emergency_active": "⚠  EMERGENCY STOP ACTIVATED",
    "main.emergency_halted": "All automation has been halted immediately.",
    "main.voice": "Voice",
    "main.gesture": "Gesture",
    "main.vision": "Vision",
    "main.toggle": "{name}: {state}",
    "main.listening": "Listening…",
    "main.ready": "Ready",
    "main.profile": "Profile",
    "main.telemetry": "CPU {cpu}%   ·   RAM {ram}%   ·   {fps} FPS   ·   {latency} ms",
    "main.gesture_info": "{gesture}   ·   {conf}%",
    "main.skeleton": "Hand skeleton",
    "main.cmd_title": "Current command and intent",
    "main.cmd_idle": "Say “Hey Hadj” then your command (e.g. “Hey Hadj, open Facebook”)",
    "main.intent_line": "Intent {intent}   ·   Risk {risk}   ·   {result}",
    "main.intent_standby": "Standby",
    "main.cmd_input_hint": "Type a command (e.g. “Open Chrome”, “Volume up”) and press Enter…",
    "main.log_title": "Live event audit log — privacy enforced",
    "main.security_confirm": "Confirmation required: {command}",
    "main.security_hint": "Risk {risk} · say “{yes}” or raise your thumb to confirm.",
    "main.calibration": "Calibration",
    "main.privacy": "Privacy",
    "main.accessibility": "Accessibility",
    "main.keyboard": "Virtual keyboard",
    "main.macros": "Macros",
    "main.demo": "Demo mode",
    "main.footer": "No data ever leaves this device",
    "main.minimized_title": "HADJ NO-TOUCH AI",
    "main.minimized_body": "Minimised to the Windows notification area. Touchless control stays active in the background.",
    "main.status_ready": "System restored — touchless control is active again",
    "main.ready_desc": "Voice, gesture and vision are listening. Say the wake word to begin.",
    "main.dock_title": "🎮  FULL PC CONTROL:",
    "main.web_companion": "🌐  Web Companion",
    "main.theme_light": "☀️ Light mode",
    "main.theme_dark": "🌙 Dark mode",
    "main.theme_high_contrast": "⚡ High Contrast",
    "main.compact_mode": "🗗 Compact",
    "main.full_mode": "🗖 Full Mode",
    "main.dominant_hand": "Dominant Hand",
    "toast.dominant_hand_changed": "Dominant hand set to {hand} ✓",
    "main.view_dashboard": "🌐 Web Dashboard",
    "main.view_native": "📷 Camera & Sensors",
    "main.view_dashboard_toast": "Switched to Interactive Web Dashboard",
    "main.view_native_toast": "Switched to Camera & Sensor Diagnostic View",

    # ---------------- Quick control dock ----------------
    "dock.desktop": "🖥️  Desktop",
    "dock.task_view": "📑  Tasks",
    "dock.snap_left": "🗔  Snap left",
    "dock.snap_right": "🗖  Snap right",
    "dock.screenshot": "📸  Capture",
    "dock.volume_up": "🔊  Vol +",
    "dock.volume_down": "🔉  Vol -",
    "dock.volume_mute": "🔇  Mute",
    "dock.keyboard": "⌨️  Keyboard",
    "dock.lock": "🔒  Lock",
    "dock.task_manager": "⚡  TaskMgr",

    # ---------------- Quick auto-calibration ----------------
    "calib.auto_btn": "⚡  Auto calibration",
    "calib.auto_running": "⚡  Analysing…",
    "calib.auto_start": "⚡  Automatic calibration running…",
    "calib.auto_detail": "Measuring camera, frame rate, ambient noise and computing the optimal thresholds…",
    "calib.auto_done": "✅  Auto calibration complete (score {score}%)",
    "calib.auto_values": "Camera: {fps} FPS · Pinch: {pinch} · Smoothing: {smoothing} · Speed: {speed}",
    "calib.auto_failed": "⚠️  Auto calibration failed",
    "shot.saved": "Screenshot saved",
    "shot.saved_at": "Saved to: {path}",
    "shot.failed": "Capture failed: {error}",

    # ---------------- Diagnostics & Arming ----------------
    "diag.no_hand": "No hand in frame",
    "diag.low_light": "Low lighting — please add more light",
    "diag.out_of_frame": "Hand partially out of frame",
    "diag.too_far": "Hand too far — move closer",
    "diag.too_close": "Hand too close — move back",
    "diag.disarmed": "Disarmed · Hold open palm 1s to arm",
    "diag.arming": "Arming in progress… {progress}%",
    "diag.disarming": "Disarming in progress… {progress}%",
    "diag.armed_ready": "Armed · Ready for gestures",
    "arm.armed": "ARMED",
    "arm.disarmed": "DISARMED",
    "emergency.shortcut_hint": "Emergency Stop: Ctrl+Alt+Esc",

    # ---------------- Guided Calibration & Quality ----------------
    "calib.quality_score": "Live Quality: {score}%",
    "calib.tip_closer": "Move your hand closer to the camera",
    "calib.tip_further": "Move your hand slightly further back",
    "calib.tip_more_light": "Low lighting detected — increase room light",
    "calib.tip_less_light": "Too much light or backlight",
    "calib.tip_center_hand": "Center your hand within the camera frame",
    "calib.tip_optimal": "Optimal tracking conditions! Hold steady",
    "calib.dominant_hand": "Dominant Hand",
    "calib.hand_right": "Right Hand",
    "calib.hand_left": "Left Hand",

    # ---------------- Audit log columns ----------------
    "col.time": "Time",
    "col.command": "Command",
    "col.intent": "Intent",
    "col.risk": "Risk",
    "col.result": "Result",

    # ---------------- Calibration wizard ----------------
    "calib.title": "HADJ Calibration Wizard",
    "calib.subtitle": "HADJ measures your camera, your microphone and your hand, then tunes every threshold itself.",
    "calib.step_devices": "Devices",
    "calib.step_devices_desc": "HADJ scanned the hardware and kept whatever answered. Choose the camera and the microphone to keep.",
    "calib.step_camera": "Camera",
    "calib.step_camera_desc": "Measuring the frame rate and the capture latency your webcam really delivers.",
    "calib.step_mic": "Microphone",
    "calib.step_mic_desc": "Measuring the ambient noise floor, so speech recognition can tell your voice from the room.",
    "calib.step_hand": "Hand tracking",
    "calib.step_hand_desc": "Hold your hand in front of the camera, palm facing the lens, and let HADJ lock on.",
    "calib.step_pinch": "Pinch sensitivity",
    "calib.step_pinch_desc": "Pinch and release three times. HADJ places the click threshold in the gap between your open and closed hand, so there is no number to guess.",
    "calib.step_reach": "Comfortable reach",
    "calib.step_reach_desc": "Move your index finger through your comfortable range. That range becomes the whole screen, so you never have to stretch towards a corner.",
    "calib.step_adaptive": "Continuous learning",
    "calib.step_adaptive_desc": "From here on, HADJ keeps re-checking the pinch threshold against your hand in real time and corrects itself when the light or your posture changes.",
    "calib.step_summary": "Your calibration",
    "calib.step_summary_desc": "Everything below was measured, not guessed. Anything measured with low confidence is worth repeating.",
    "calib.rescan": "Scan again",
    "calib.device_camera": "Camera",
    "calib.device_microphone": "Microphone",
    "calib.no_camera": "No camera answered",
    "calib.no_mic": "No microphone found, the system default will be used",
    "calib.camera_measuring": "Measuring the video stream…",
    "calib.camera_result": "{device} · {resolution} at {fps} FPS · {latency} ms latency",
    "calib.mic_measuring": "Measuring the noise floor, stay quiet…",
    "calib.mic_result": "Noise floor {floor} · speech threshold {threshold}",
    "calib.hand_waiting": "No hand detected, place it in frame",
    "calib.hand_locked": "Hand locked · 21 landmarks",
    "calib.pinch_waiting": "Waiting for the first pinch",
    "calib.pinch_count": "{done} of {total} pinches",
    "calib.reach_waiting": "Move your index finger through your whole comfortable range",
    "calib.reach_live": "Reach measured: {width}% × {height}%",
    "calib.adaptive_enabled": "Continuous learning",
    "calib.adaptive_status": "{samples} samples analysed",
    "calib.adaptive_waiting": "Waiting for the first frames...",
    "calib.value_pinch": "Pinch threshold",
    "calib.value_deadzone": "Tremor dead zone",
    "calib.value_smoothing": "EMA smoothing",
    "calib.value_cursor_speed": "Cursor speed",
    "calib.value_drag": "Drag hold delay",
    "calib.value_double": "Double-pinch window",
    "calib.value_scroll": "Scroll speed",
    "calib.value_swipe": "Swipe threshold",
    "calib.value_box": "Reach window",
    "calib.value_noise": "Microphone noise floor",
    "calib.value_latency": "Camera latency",
    "calib.measure": "Measure",
    "calib.remeasure": "Measure again",
    "calib.apply": "Apply calibration",
    "calib.applied": "Calibration applied, the pinch threshold is now {value}",
    "calib.confidence_note": "Confidence {percent}%",
    "calib.skipped": "Not measured, the current value was kept",

    # ---------------- Privacy dashboard ----------------
    "privacy.title": "HADJ Privacy Dashboard",
    "privacy.heading": "Privacy & security",
    "privacy.intro": "All computer vision, speech recognition and automation logic runs locally on this machine. Nothing is ever sent to an external service.",
    "privacy.microphone": "Microphone",
    "privacy.camera": "Camera stream",
    "privacy.voice_processing": "Voice processing",
    "privacy.gesture_processing": "Gesture processing",
    "privacy.internet": "Internet connection",
    "privacy.telemetry": "Cloud telemetry",
    "privacy.biometric": "Biometric data",
    "privacy.remote_apis": "Remote APIs",
    "privacy.status_enabled": "Enabled",
    "privacy.status_active": "Active",
    "privacy.status_local": "100% local",
    "privacy.status_offline": "Offline enforced",
    "privacy.status_disabled": "Disabled",
    "privacy.status_never": "Never stored",
    "privacy.status_blocked": "Blocked",
    "privacy.guarantee": "Privacy guarantee — camera frames are discarded from memory as soon as landmarks are extracted. No audio file and no face image is ever written to your drive.",
    "privacy.offline_active": "Offline mode active",
    "privacy.hybrid_mode": "Hybrid mode",

    # ---------------- Accessibility ----------------
    "access.title": "HADJ Accessibility & input modes",
    "access.heading": "Accessibility input profiles",
    "access.intro": "Choose the interaction profile that suits your needs — no mouse or keyboard required.",
    "access.profiles_title": "Interaction profile",
    "access.options_title": "Comfort options",
    "access.mode_MULTIMODAL_name": "Full multimodal",
    "access.mode_MULTIMODAL_desc": "Voice, gestures and vision combined.",
    "access.mode_VOICE_ONLY_name": "Voice only",
    "access.mode_VOICE_ONLY_desc": "Speech recognition and dictation.",
    "access.mode_GESTURE_ONLY_name": "Gesture only",
    "access.mode_GESTURE_ONLY_desc": "Hand tracking with a virtual mouse.",
    "access.mode_HEAD_ONLY_name": "Head only",
    "access.mode_HEAD_ONLY_desc": "Tilt to navigate, nod to click.",
    "access.mode_VOICE_GAZE_name": "Voice and gaze",
    "access.mode_VOICE_GAZE_desc": "Dwell focus with voice commands.",
    "access.dwell_name": "Dwell click",
    "access.dwell_desc": "A steady hover of 1.0 s triggers a click.",
    "access.contrast_desc": "High contrast black and electric neon palette for optimal readability.",
    "access.large_cursor_name": "Enlarged virtual cursor",
    "access.large_cursor_desc": "High contrast to make tracking easier.",

    # ---------------- Macros ----------------
    "macro.title": "HADJ Macro Manager",
    "macro.heading": "Automation macros & sequences",
    "macro.saved": "Saved macros",
    "macro.preview": "Macro steps preview",
    "macro.run": "▶  Run macro",
    "macro.running_title": "Macro running",
    "macro.running_body": "Macro “{name}” has started in the background.",
    "macro.empty": "No macro saved yet.",

    # ---------------- Demo mode ----------------
    "demo.title": "HADJ Interactive Demo",
    "demo.heading": "System capabilities showcase",
    "demo.intro": "Choose a scenario to execute and watch the touchless automation layer at work.",
    "demo.s1": "1.  Voice — “افتح Calculator ثم ارفع الصوت”",
    "demo.s2": "2.  Multimodal — point at a target, then say “افتحه”",
    "demo.s3": "3.  Screen vision — “أين زر الإغلاق؟”",
    "demo.s4": "4.  Browser navigation — “افتح تبويب جديد ثم ابحث عن Arduino”",
    "demo.s5": "5.  Dictation & editing — “اكتب مرحبا بكم في تطبيقي”",
    "demo.s6": "6.  Macro automation — “Morning Setup”",
    "demo.scenarios_title": "Scenarios",
    "demo.output": "Live execution output",
    "demo.ready": "Ready. Choose one of the scenarios above…",
    "demo.executing": "Executing: “{command}”",
    "demo.result": "Result: {result}",

    # ---------------- System tray ----------------
    "tray.show": "Show dashboard",
    "tray.voice": "Voice control",
    "tray.gesture": "Gesture control",
    "tray.offline": "Offline mode",
    "tray.emergency": "⚠  Emergency stop",
    "tray.quit": "Exit HADJ",

    # ---------------- Floating HUD ----------------
    "hud.title": "HADJ NO-TOUCH OFFLINE AI",
    "hud.awaiting": "Waiting for “Hey Hadj” or “يا حاج”…",
    "hud.listening": "Listening…",
    "hud.ready": "Ready",
    "hud.ready_active": "Ready — touchless control active",
    "hud.badge_ready": "READY",
    "hud.badge_tracking": "TRACKING",
    "hud.badge_halted": "HALTED",
    "hud.badge_confirm": "CONFIRM?",
    "hud.emergency": "⚠  EMERGENCY STOP ACTIVE",
    "hud.confirm": "Confirm: {command}?",

    # ---------------- Virtual keyboard ----------------
    "kb.title": "HADJ Virtual Keyboard",
    "kb.heading": "HADJ TOUCHLESS KEYBOARD",
    "kb.bksp": "Bksp",
    "kb.tab": "Tab",
    "kb.enter": "Enter",
    "kb.space": "Space",
    "kb.copy": "Copy",
    "kb.paste": "Paste",
    "kb.undo": "Undo",
    "kb.del_word": "Del word",
    "kb.next_line": "New line",

    # ---------------- Camera widget ----------------
    "camera.standby": "CAMERA STANDBY",

    # ---------------- Gestures ----------------
    "gesture.NONE": "No gesture",
    "gesture.INDEX_POINT": "Pointing",
    "gesture.PINCH": "Pinch",
    "gesture.DOUBLE_PINCH": "Double pinch",
    "gesture.PINCH_HOLD": "Pinch & hold",
    "gesture.OPEN_PALM": "Open palm",
    "gesture.TWO_FINGER_SCROLL_UP": "Scroll up",
    "gesture.TWO_FINGER_SCROLL_DOWN": "Scroll down",
    "gesture.SWIPE_LEFT": "Swipe left",
    "gesture.SWIPE_RIGHT": "Swipe right",
    "gesture.THUMB_UP": "Thumb up",
    "gesture.FIST": "Fist",

    # ---------------- Risk & result ----------------
    "risk.LOW": "low",
    "risk.MEDIUM": "medium",
    "risk.HIGH": "high",
    "risk.CRITICAL": "critical",
    "result.SUCCESS": "Success",
    "result.FAILED": "Failed",

    # ---------------- Performance profiles ----------------
    "profile.ECO": "Eco",
    "profile.BALANCED": "Balanced",
    "profile.PERFORMANCE": "Performance",
    "profile.AI_MAX": "AI Max",

    # ---------------- Intents ----------------
    "intent.UNKNOWN": "Unrecognised",
    "intent.LAUNCH_APP": "Open application",
    "intent.CLOSE_WINDOW": "Close window",
    "intent.MINIMIZE_WINDOW": "Minimise window",
    "intent.MAXIMIZE_WINDOW": "Maximise window",
    "intent.RESTORE_WINDOW": "Restore window",
    "intent.SWITCH_APP": "Switch application",
    "intent.SHOW_DESKTOP": "Show desktop",
    "intent.OPEN_FOLDER": "Open folder",
    "intent.CREATE_FOLDER": "Create folder",
    "intent.DELETE_FILE": "Delete file",
    "intent.DELETE_FOLDER": "Delete folder",
    "intent.SEARCH_FILES": "Search files",
    "intent.OPEN_RECENT_FILE": "Open recent file",
    "intent.BROWSER_NEW_TAB": "New browser tab",
    "intent.BROWSER_CLOSE_TAB": "Close browser tab",
    "intent.BROWSER_NEXT_TAB": "Next browser tab",
    "intent.BROWSER_PREV_TAB": "Previous browser tab",
    "intent.BROWSER_SEARCH": "Search the web",
    "intent.NAVIGATE_BACK": "Navigate back",
    "intent.NAVIGATE_FORWARD": "Navigate forward",
    "intent.NAVIGATE_REFRESH": "Refresh page",
    "intent.TOGGLE_FULLSCREEN": "Toggle full screen",
    "intent.VOLUME_UP": "Volume up",
    "intent.VOLUME_DOWN": "Volume down",
    "intent.VOLUME_MUTE": "Mute",
    "intent.VOLUME_SET": "Set volume",
    "intent.MEDIA_PLAY_PAUSE": "Play / pause",
    "intent.MEDIA_NEXT": "Next track",
    "intent.MEDIA_PREVIOUS": "Previous track",
    "intent.BRIGHTNESS_UP": "Brightness up",
    "intent.BRIGHTNESS_DOWN": "Brightness down",
    "intent.BRIGHTNESS_SET": "Set brightness",
    "intent.SCREENSHOT": "Screenshot",
    "intent.CLIPBOARD_COPY": "Copy",
    "intent.CLIPBOARD_PASTE": "Paste",
    "intent.CLIPBOARD_CUT": "Cut",
    "intent.SELECT_ALL": "Select all",
    "intent.UNDO": "Undo",
    "intent.DICTATION": "Dictation",
    "intent.SCROLL_UP": "Scroll up",
    "intent.SCROLL_DOWN": "Scroll down",
    "intent.SNAP_WINDOW_LEFT": "Snap to the left",
    "intent.SNAP_WINDOW_RIGHT": "Snap to the right",
    "intent.TASK_VIEW": "Task view",
    "intent.NEW_DESKTOP": "New desktop",
    "intent.CLOSE_DESKTOP": "Close desktop",
    "intent.NEXT_DESKTOP": "Next desktop",
    "intent.PREV_DESKTOP": "Previous desktop",
    "intent.OPEN_TASK_MANAGER": "Task manager",
    "intent.EMPTY_RECYCLE_BIN": "Empty recycle bin",
    "intent.ZOOM_IN": "Zoom in",
    "intent.ZOOM_OUT": "Zoom out",
    "intent.ZOOM_RESET": "Reset zoom",
    "intent.REFRESH_SCREEN": "Refresh screen",
    "intent.TOGGLE_KEYBOARD_HUD": "Virtual keyboard",
    "intent.SYSTEM_LOCK": "Lock session",
    "intent.SYSTEM_RESTART": "Restart",
    "intent.SYSTEM_SHUTDOWN": "Shut down",
    "intent.SYSTEM_SLEEP": "Sleep",
    "intent.FIND_ELEMENT": "Locate on screen",
    "intent.MULTIMODAL_CLICK_TARGET": "Click pointed target",
    "intent.MULTIMODAL_OPEN_TARGET": "Open pointed target",
    "intent.EXECUTE_MACRO": "Run macro",
    "intent.COMPOUND_PLAN": "Compound plan",

    # ---------------- Log table & Toasts (EN) ----------------
    "col.time": "Time",
    "col.command": "Command",
    "col.intent": "Intent",
    "col.confidence": "Confidence",
    "col.risk": "Risk",
    "col.result": "Result",
    "log.search_placeholder": "🔍 Search history...",
    "log.export_csv": "Export CSV",
    "toast.screenshot_saved": "Screenshot saved ✓",
    "toast.csv_exported": "Event log exported to CSV ✓",
    "toast.action_executed": "{action} executed ✓",
    "main.eco_mode": "Eco Mode",
    "toast.eco_activated": "Eco Mode activated (CPU > 80%)",

    # ---------------- App Profiles (EN) ----------------
    "profile.browser": "Browser",
    "profile.media": "Media Player",
    "profile.document": "Document",
    "profile.desktop": "Desktop",
    "profile.active_label": "Active Profile: {profile}",
    "profile.action.browser_back": "Back (History)",
    "profile.action.browser_forward": "Forward (History)",
    "profile.action.media_seek_back": "Seek Back 10s",
    "profile.action.media_seek_forward": "Seek Forward 10s",
    "profile.action.media_play_pause": "Play / Pause",
    "profile.action.doc_page_prev": "Previous Page",
    "profile.action.doc_page_next": "Next Page",
    "profile.action.click": "Left Click",

    # ---------------- Macros (EN) ----------------
    "macro.title": "Automation Macros",
    "macro.heading": "Custom Multi-Step Automation Workflows",
    "macro.saved": "Saved Macros",
    "macro.preview": "Steps & Triggers",
    "macro.run": "Run Macro",
    "macro.new": "+ New Macro",
    "macro.empty": "No macros configured yet. Click '+ New Macro' to create your first workflow.",
    "macro.running_title": "Running Macro",
    "macro.running_body": "Executing macro: {name}",
    "macro.create_title": "Create New Macro",
    "macro.name": "Macro Name",
    "macro.name_placeholder": "e.g. Morning Workflow, Code Setup...",
    "macro.voice_trigger": "Voice Trigger (optional)",
    "macro.voice_placeholder": "e.g. open work, morning setup...",
    "macro.gesture_trigger": "Gesture Trigger (optional)",
    "macro.none": "None",
    "macro.steps": "Macro Steps",
    "macro.add_step": "+ Add Step",
    "macro.remove_step": "Remove Step",
    "macro.action": "Action Type",
    "macro.target": "Target / Argument",
    "macro.delay": "Delay (s)",
    "macro.save": "Save Macro",
    "macro.step_launch_app": "Launch Application",
    "macro.step_type_text": "Type Text",
    "macro.step_key_press": "Key Press",
    "macro.step_hotkey": "Keyboard Shortcut (e.g. ctrl+c)",
    "macro.step_volume": "Set Volume (0-100)",
    "macro.step_brightness": "Set Brightness (0-100)",
    "macro.step_folder": "Open Folder",
    "macro.step_wait": "Wait (seconds)",

    # ---------------- Privacy & Safety (EN) ----------------
    "privacy.mode": "Privacy Mode",
    "privacy.mode_active": "🛡️ PRIVACY ACTIVE",
    "privacy.cam_on": "📷 CAM ON",
    "privacy.cam_off": "📷 CAM OFF",
    "privacy.mic_on": "🎙️ MIC ON",
    "privacy.mic_off": "🎙️ MIC OFF",
    "toast.privacy_mode_activated": "Privacy Mode: Camera and Mic disabled",
    "toast.privacy_mode_deactivated": "Privacy Mode deactivated: Sensors restored",
    "security.prompt_delete": "Are you sure you want to permanently delete: {target}?",
    "security.prompt_empty_bin": "Are you sure you want to empty the Recycle Bin?",
    "security.prompt_shutdown": "Are you sure you want to shut down the PC?",
    "security.prompt_restart": "Are you sure you want to restart the PC?",
    "security.prompt_close": "Are you sure you want to close this application?",
    "security.confirm_btn": "✔ Confirm",
    "security.cancel_btn": "✖ Cancel",
    "security.countdown": "Auto-cancels in {seconds}s",
    "log.clear": "Clear Log",
    "log.clear_confirm_title": "Clear Audit Log",
    "log.clear_confirm_msg": "Are you sure you want to permanently clear the audit log?",
    "toast.log_cleared": "Audit log cleared ✓",
}


# --------------------------------------------------------------------------- #
# French
# --------------------------------------------------------------------------- #

_FR: Dict[str, str] = {
    "app.name": "HADJ NO-TOUCH OFFLINE AI",
    "app.tagline": "Pilotage complet sans contact — voix, gestes, vision et IA hors ligne",
    "app.offline_first": "Hors ligne",
    "app.tray_tooltip": "HADJ NO-TOUCH OFFLINE AI",

    "common.on": "ACTIVÉ",
    "common.off": "DÉSACTIVÉ",
    "common.close": "Fermer",
    "common.done": "Terminé",
    "common.cancel": "Annuler",
    "common.back": "Précédent",
    "common.next": "Suivant",
    "common.finish": "Terminer",
    "common.delete": "Supprimer",
    "common.run": "Lancer",
    "common.execute": "Exécuter",
    "common.language": "Langue",
    "common.yes": "Oui",
    "common.no": "Non",
    "common.confidence": "Conf",
    "common.step_of": "ÉTAPE {current} SUR {total}",

    "main.emergency_stop": "⚠  ARRÊTER HADJ",
    "main.emergency_restore": "↺  Réactiver le système",
    "main.emergency_active": "⚠  ARRÊT D'URGENCE ACTIVÉ",
    "main.emergency_halted": "Toutes les automatisations ont été interrompues immédiatement.",
    "main.voice": "Voix",
    "main.gesture": "Gestes",
    "main.vision": "Vision",
    "main.toggle": "{name} : {state}",
    "main.listening": "À l'écoute…",
    "main.ready": "Prêt",
    "main.profile": "Profil",
    "main.telemetry": "CPU {cpu}%   ·   RAM {ram}%   ·   {fps} FPS   ·   {latency} ms",
    "main.gesture_info": "{gesture}   ·   {conf} %",
    "main.skeleton": "Squelette de la main",
    "main.cmd_title": "Commande et intention en cours",
    "main.cmd_idle": "Dites « Bonjour Hadj » puis votre commande (ex: « Ouvre Facebook »)",
    "main.intent_line": "Intention {intent}   ·   Risque {risk}   ·   {result}",
    "main.intent_standby": "Veille",
    "main.cmd_input_hint": "Saisissez une commande (par ex. « Ouvre Chrome », « Monte le son ») puis Entrée…",
    "main.log_title": "Journal d'audit en direct — confidentialité garantie",
    "main.security_confirm": "Confirmation requise : {command}",
    "main.security_hint": "Risque {risk} · dites « {yes} » ou le pouce levé pour confirmer.",
    "main.calibration": "Calibrage",
    "main.privacy": "Confidentialité",
    "main.accessibility": "Accessibilité",
    "main.keyboard": "Clavier virtuel",
    "main.macros": "Macros",
    "main.demo": "Mode démo",
    "main.footer": "Aucune donnée ne quitte cet appareil",
    "main.minimized_title": "HADJ NO-TOUCH AI",
    "main.minimized_body": "Réduit dans la zone de notification Windows. Le contrôle sans contact reste actif en arrière-plan.",
    "main.status_ready": "Système restauré — le contrôle sans contact est de nouveau actif",
    "main.ready_desc": "La voix, les gestes et la vision écoutent. Dites le mot d'activation pour commencer.",
    "main.dock_title": "🎮  CONTRÔLE TOTAL DU PC :",
    "main.web_companion": "🌐  Compagnon Web",
    "main.theme_light": "☀️ Mode clair",
    "main.theme_dark": "🌙 Mode sombre",
    "main.theme_high_contrast": "⚡ Contraste élevé",
    "main.compact_mode": "🗗 Mode compact",
    "main.full_mode": "🗖 Mode complet",
    "main.dominant_hand": "Main dominante",
    "toast.dominant_hand_changed": "Main dominante réglée sur {hand} ✓",
    "main.view_dashboard": "🌐 Dashboard Web",
    "main.view_native": "📷 Capteurs & Caméra",
    "main.view_dashboard_toast": "Passage au Dashboard Web Interactif",
    "main.view_native_toast": "Passage à la vue Capteurs & Caméra",

    "dock.desktop": "🖥️  Bureau",
    "dock.task_view": "📑  Tâches",
    "dock.snap_left": "🗔  Ancrer G",
    "dock.snap_right": "🗖  Ancrer D",
    "dock.screenshot": "📸  Capture",
    "dock.volume_up": "🔊  Vol +",
    "dock.volume_down": "🔉  Vol -",
    "dock.volume_mute": "🔇  Muet",
    "dock.keyboard": "⌨️  Clavier",
    "dock.lock": "🔒  Verrouiller",
    "dock.task_manager": "⚡  TaskMgr",

    "calib.auto_btn": "⚡  Calibrage Auto",
    "calib.auto_running": "⚡  Analyse en cours…",
    "calib.auto_start": "⚡  Calibrage automatique en cours…",
    "calib.auto_detail": "Mesure de la caméra, du nombre d'images, du bruit ambiant et calcul des seuils optimaux…",
    "calib.auto_done": "✅  Calibrage Auto Réussi (Score {score}%)",
    "calib.auto_values": "Caméra : {fps} FPS · Seuil Pince : {pinch} · Lissage : {smoothing} · Vitesse : {speed}",
    "calib.auto_failed": "⚠️  Erreur Calibrage Auto",
    "shot.saved": "Capture d'écran enregistrée",
    "shot.saved_at": "Enregistré : {path}",
    "shot.failed": "Erreur capture : {error}",

    # ---------------- Diagnostics & Armement ----------------
    "diag.no_hand": "Aucune main dans le champ",
    "diag.low_light": "Éclairage trop faible — ajoutez de la lumière",
    "diag.out_of_frame": "Main partiellement hors cadre",
    "diag.too_far": "Main trop éloignée — rapprochez-vous",
    "diag.too_close": "Main trop proche — reculez un peu",
    "diag.disarmed": "Désarmé · Paume ouverte 1 s pour armer",
    "diag.arming": "Armement en cours… {progress} %",
    "diag.disarming": "Désarmement en cours… {progress} %",
    "diag.armed_ready": "Armé · Prêt pour les gestes",
    "arm.armed": "ARMÉ",
    "arm.disarmed": "DÉSARMÉ",
    "emergency.shortcut_hint": "Arrêt d'urgence : Ctrl+Alt+Échap",

    # ---------------- Calibrage guidé & Qualité ----------------
    "calib.quality_score": "Qualité en direct : {score} %",
    "calib.tip_closer": "Rapprochez votre main de la caméra",
    "calib.tip_further": "Éloignez légèrement votre main",
    "calib.tip_more_light": "Éclairage insuffisant — ajoutez de la lumière",
    "calib.tip_less_light": "Éclairage trop intense ou contre-jour",
    "calib.tip_center_hand": "Centrez votre main dans le cadre de la caméra",
    "calib.tip_optimal": "Conditions optimales ! Maintenez la position",
    "calib.dominant_hand": "Main dominante",
    "calib.hand_right": "Main droite",
    "calib.hand_left": "Main gauche",

    "col.time": "Heure",
    "col.command": "Commande",
    "col.intent": "Intention",
    "col.risk": "Risque",
    "col.result": "Résultat",

    "calib.title": "Assistant de calibrage HADJ",
    "calib.subtitle": "HADJ mesure votre caméra, votre microphone et votre main, puis règle lui-même tous les seuils.",
    "calib.step_devices": "Périphériques",
    "calib.step_devices_desc": "HADJ a inspecté le matériel et gardé ce qui a répondu. Choisissez la caméra et le micro à conserver.",
    "calib.step_camera": "Caméra",
    "calib.step_camera_desc": "Mesure de la fréquence d'images et de la latence de capture que votre webcam offre réellement.",
    "calib.step_mic": "Microphone",
    "calib.step_mic_desc": "Mesure du bruit de fond ambiant, pour que la reconnaissance vocale distingue votre voix de la pièce.",
    "calib.step_hand": "Suivi de la main",
    "calib.step_hand_desc": "Placez votre main devant la caméra, paume vers l'objectif, et laissez HADJ verrouiller la détection.",
    "calib.step_pinch": "Sensibilité du pincement",
    "calib.step_pinch_desc": "Pincer et relâchez trois fois. HADJ place le seuil de clic dans l'écart entre votre main ouverte et fermée : aucun chiffre à deviner.",
    "calib.step_reach": "Portée confortable",
    "calib.step_reach_desc": "Déplacez votre index dans votre plage de confort. Cette plage devient tout l'écran, donc plus besoin de s'étirer vers un coin.",
    "calib.step_adaptive": "Apprentissage continu",
    "calib.step_adaptive_desc": "À partir d'ici, HADJ revérifie le seuil de pincement en temps réel et se corrige si la lumière ou votre posture change.",
    "calib.step_summary": "Votre calibrage",
    "calib.step_summary_desc": "Tout ce qui suit a été mesuré, pas deviné. Les valeurs mesurées avec peu de confiance méritent d'être reprises.",
    "calib.rescan": "Rechercher",
    "calib.device_camera": "Caméra",
    "calib.device_microphone": "Microphone",
    "calib.no_camera": "Aucune caméra n'a répondu",
    "calib.no_mic": "Aucun microphone trouvé, le micro par défaut sera utilisé",
    "calib.camera_measuring": "Mesure du flux vidéo…",
    "calib.camera_result": "{device} · {resolution} à {fps} i/s · latence {latency} ms",
    "calib.mic_measuring": "Mesure du bruit de fond, restez silencieux…",
    "calib.mic_result": "Bruit de fond {floor} · seuil de voix {threshold}",
    "calib.hand_waiting": "Main non détectée, placez-la dans le cadre",
    "calib.hand_locked": "Main verrouillée · 21 points de repère",
    "calib.pinch_waiting": "En attente du premier pincement",
    "calib.pinch_count": "{done} sur {total} pincements",
    "calib.reach_waiting": "Déplacez votre index dans toute votre plage confortable",
    "calib.reach_live": "Portée mesurée : {width} % × {height} %",
    "calib.adaptive_enabled": "Apprentissage continu",
    "calib.adaptive_status": "{samples} échantillons analysés",
    "calib.adaptive_waiting": "En attente des premières images...",
    "calib.value_pinch": "Seuil de pincement",
    "calib.value_deadzone": "Zone morte anti-tremblement",
    "calib.value_smoothing": "Lissage EMA",
    "calib.value_cursor_speed": "Vitesse du curseur",
    "calib.value_drag": "Délai de maintien du glissement",
    "calib.value_double": "Fenêtre de double pincement",
    "calib.value_scroll": "Vitesse de défilement",
    "calib.value_swipe": "Seuil de balayage",
    "calib.value_box": "Plage de portée",
    "calib.value_noise": "Bruit de fond du micro",
    "calib.value_latency": "Latence caméra",
    "calib.measure": "Mesurer",
    "calib.remeasure": "Re-mesurer",
    "calib.apply": "Appliquer le calibrage",
    "calib.applied": "Calibrage appliqué, le seuil de pincement est maintenant {value}",
    "calib.confidence_note": "Confiance {percent} %",
    "calib.skipped": "Non mesuré, la valeur actuelle a été conservée",

    "privacy.title": "Tableau de bord de confidentialité HADJ",
    "privacy.heading": "Confidentialité et sécurité",
    "privacy.intro": "Toute la vision informatique, la reconnaissance vocale et la logique d'automatisation s'exécutent localement sur cette machine. Rien n'est jamais transmis à un service externe.",
    "privacy.microphone": "Microphone",
    "privacy.camera": "Flux caméra",
    "privacy.voice_processing": "Traitement vocal",
    "privacy.gesture_processing": "Traitement gestuel",
    "privacy.internet": "Connexion Internet",
    "privacy.telemetry": "Télémétrie cloud",
    "privacy.biometric": "Données biométriques",
    "privacy.remote_apis": "API distantes",
    "privacy.status_enabled": "Activé",
    "privacy.status_active": "Actif",
    "privacy.status_local": "100 % local",
    "privacy.status_offline": "Hors ligne imposé",
    "privacy.status_disabled": "Désactivé",
    "privacy.status_never": "Jamais stocké",
    "privacy.status_blocked": "Bloqué",
    "privacy.guarantee": "Garantie de confidentialité — les images de la caméra sont supprimées de la mémoire dès que les points de repère sont extraits. Aucun fichier audio ni portrait n'est écrit sur votre disque.",
    "privacy.offline_active": "Mode hors ligne actif",
    "privacy.hybrid_mode": "Mode hybride",

    "access.title": "Accessibilité et modes d'entrée HADJ",
    "access.heading": "Profils d'entrée accessibles",
    "access.intro": "Choisissez le profil d'interaction adapté à vos besoins — sans souris ni clavier.",
    "access.profiles_title": "Profil d'interaction",
    "access.options_title": "Options de confort",
    "access.mode_MULTIMODAL_name": "Multimodal complet",
    "access.mode_MULTIMODAL_desc": "Voix, gestes et vision réunis.",
    "access.mode_VOICE_ONLY_name": "Voix uniquement",
    "access.mode_VOICE_ONLY_desc": "Reconnaissance vocale et dictée.",
    "access.mode_GESTURE_ONLY_name": "Gestes uniquement",
    "access.mode_GESTURE_ONLY_desc": "Suivi de la main avec souris virtuelle.",
    "access.mode_HEAD_ONLY_name": "Tête uniquement",
    "access.mode_HEAD_ONLY_desc": "Inclinaison pour naviguer, hochement pour cliquer.",
    "access.mode_VOICE_GAZE_name": "Voix et regard",
    "access.mode_VOICE_GAZE_desc": "Focus au maintien avec commandes vocales.",
    "access.dwell_name": "Clic au maintien",
    "access.dwell_desc": "Un survol stable de 1,0 s déclenche un clic.",
    "access.contrast_desc": "Palette noir et néon à fort contraste pour une lisibilité optimale.",
    "access.large_cursor_name": "Curseur virtuel agrandi",
    "access.large_cursor_desc": "Fort contraste pour faciliter le suivi.",

    "macro.title": "Gestionnaire de macros HADJ",
    "macro.heading": "Macros et séquences d'automatisation",
    "macro.saved": "Macros enregistrées",
    "macro.preview": "Aperçu des étapes",
    "macro.run": "▶  Lancer la macro",
    "macro.running_title": "Macro en cours",
    "macro.running_body": "La macro « {name} » a démarré en arrière-plan.",
    "macro.empty": "Aucune macro enregistrée.",

    "demo.title": "Mode démo interactif HADJ",
    "demo.heading": "Présentation des capacités du système",
    "demo.intro": "Choisissez un scénario à exécuter et observez la couche d'automatisation sans contact.",
    "demo.s1": "1.  Voix — « افتح Calculator ثم ارفع الصوت »",
    "demo.s2": "2.  Multimodal — visez une cible, puis dites « افتحه »",
    "demo.s3": "3.  Vision de l'écran — « أين زر الإغلاق؟ »",
    "demo.s4": "4.  Navigation web — « افتح تبويب جديد ثم ابحث عن Arduino »",
    "demo.s5": "5.  Dictée et édition — « اكتب مرحبا بكم في تطبيقي »",
    "demo.s6": "6.  Macro — « Morning Setup »",
    "demo.scenarios_title": "Scénarios",
    "demo.output": "Sortie d'exécution en direct",
    "demo.ready": "Prêt. Choisissez un scénario ci-dessus…",
    "demo.executing": "Exécution : « {command} »",
    "demo.result": "Résultat : {result}",

    "tray.show": "Afficher le tableau de bord",
    "tray.voice": "Contrôle vocal",
    "tray.gesture": "Contrôle gestuel",
    "tray.offline": "Mode hors ligne",
    "tray.emergency": "⚠  Arrêt d'urgence",
    "tray.quit": "Quitter HADJ",

    "hud.title": "HADJ NO-TOUCH OFFLINE AI",
    "hud.awaiting": "En attente de « Hey Hadj » ou « يا حاج »…",
    "hud.listening": "À l'écoute…",
    "hud.ready": "Prêt",
    "hud.ready_active": "Prêt — contrôle sans contact actif",
    "hud.badge_ready": "PRÊT",
    "hud.badge_tracking": "SUIVI",
    "hud.badge_halted": "ARRÊTÉ",
    "hud.badge_confirm": "CONFIRMER ?",
    "hud.emergency": "⚠  ARRÊT D'URGENCE ACTIF",
    "hud.confirm": "Confirmer : {command} ?",

    "kb.title": "Clavier virtuel HADJ",
    "kb.heading": "CLAVIER SANS CONTACT HADJ",
    "kb.bksp": "⌫",
    "kb.tab": "Tab",
    "kb.enter": "Entrée",
    "kb.space": "Espace",
    "kb.copy": "Copier",
    "kb.paste": "Coller",
    "kb.undo": "Annuler",
    "kb.del_word": "Suppr. mot",
    "kb.next_line": "Nouvelle ligne",

    "camera.standby": "CAMÉRA EN VEILLE",

    "gesture.NONE": "Aucun geste",
    "gesture.INDEX_POINT": "Index tendu",
    "gesture.PINCH": "Pincement",
    "gesture.DOUBLE_PINCH": "Double pincement",
    "gesture.PINCH_HOLD": "Pincement maintenu",
    "gesture.OPEN_PALM": "Paume ouverte",
    "gesture.TWO_FINGER_SCROLL_UP": "Défilement haut",
    "gesture.TWO_FINGER_SCROLL_DOWN": "Défilement bas",
    "gesture.SWIPE_LEFT": "Balayage gauche",
    "gesture.SWIPE_RIGHT": "Balayage droite",
    "gesture.THUMB_UP": "Pouce levé",
    "gesture.FIST": "Poing fermé",

    "risk.LOW": "faible",
    "risk.MEDIUM": "moyen",
    "risk.HIGH": "élevé",
    "risk.CRITICAL": "critique",

    "result.SUCCESS": "Réussi",
    "result.FAILED": "Échec",

    "profile.ECO": "Éco",
    "profile.BALANCED": "Équilibré",
    "profile.PERFORMANCE": "Performance",
    "profile.AI_MAX": "IA Max",

    "intent.UNKNOWN": "Non reconnu",
    "intent.LAUNCH_APP": "Ouvrir une application",
    "intent.CLOSE_WINDOW": "Fermer la fenêtre",
    "intent.MINIMIZE_WINDOW": "Réduire la fenêtre",
    "intent.MAXIMIZE_WINDOW": "Agrandir la fenêtre",
    "intent.RESTORE_WINDOW": "Restaurer la fenêtre",
    "intent.SWITCH_APP": "Changer d'application",
    "intent.SHOW_DESKTOP": "Afficher le bureau",
    "intent.OPEN_FOLDER": "Ouvrir un dossier",
    "intent.CREATE_FOLDER": "Créer un dossier",
    "intent.DELETE_FILE": "Supprimer un fichier",
    "intent.DELETE_FOLDER": "Supprimer un dossier",
    "intent.SEARCH_FILES": "Rechercher des fichiers",
    "intent.OPEN_RECENT_FILE": "Ouvrir un fichier récent",
    "intent.BROWSER_NEW_TAB": "Nouvel onglet",
    "intent.BROWSER_CLOSE_TAB": "Fermer l'onglet",
    "intent.BROWSER_NEXT_TAB": "Onglet suivant",
    "intent.BROWSER_PREV_TAB": "Onglet précédent",
    "intent.BROWSER_SEARCH": "Rechercher sur le web",
    "intent.NAVIGATE_BACK": "Retour",
    "intent.NAVIGATE_FORWARD": "Avancer",
    "intent.NAVIGATE_REFRESH": "Actualiser la page",
    "intent.TOGGLE_FULLSCREEN": "Basculer en plein écran",
    "intent.VOLUME_UP": "Volume +",
    "intent.VOLUME_DOWN": "Volume −",
    "intent.VOLUME_MUTE": "Couper le son",
    "intent.VOLUME_SET": "Régler le volume",
    "intent.MEDIA_PLAY_PAUSE": "Lecture / pause",
    "intent.MEDIA_NEXT": "Piste suivante",
    "intent.MEDIA_PREVIOUS": "Piste précédente",
    "intent.BRIGHTNESS_UP": "Luminosité +",
    "intent.BRIGHTNESS_DOWN": "Luminosité −",
    "intent.BRIGHTNESS_SET": "Régler la luminosité",
    "intent.SCREENSHOT": "Capture d'écran",
    "intent.CLIPBOARD_COPY": "Copier",
    "intent.CLIPBOARD_PASTE": "Coller",
    "intent.CLIPBOARD_CUT": "Couper",
    "intent.SELECT_ALL": "Tout sélectionner",
    "intent.UNDO": "Annuler",
    "intent.DICTATION": "Dictée",
    "intent.SCROLL_UP": "Défiler vers le haut",
    "intent.SCROLL_DOWN": "Défiler vers le bas",
    "intent.SNAP_WINDOW_LEFT": "Ancrer à gauche",
    "intent.SNAP_WINDOW_RIGHT": "Ancrer à droite",
    "intent.TASK_VIEW": "Vue des tâches",
    "intent.NEW_DESKTOP": "Nouveau bureau",
    "intent.CLOSE_DESKTOP": "Fermer le bureau",
    "intent.NEXT_DESKTOP": "Bureau suivant",
    "intent.PREV_DESKTOP": "Bureau précédent",
    "intent.OPEN_TASK_MANAGER": "Gestionnaire des tâches",
    "intent.EMPTY_RECYCLE_BIN": "Vider la corbeille",
    "intent.ZOOM_IN": "Zoom avant",
    "intent.ZOOM_OUT": "Zoom arrière",
    "intent.ZOOM_RESET": "Réinitialiser le zoom",
    "intent.REFRESH_SCREEN": "Actualiser l'écran",
    "intent.TOGGLE_KEYBOARD_HUD": "Clavier virtuel",
    "intent.SYSTEM_LOCK": "Verrouiller la session",
    "intent.SYSTEM_RESTART": "Redémarrer",
    "intent.SYSTEM_SHUTDOWN": "Éteindre",
    "intent.SYSTEM_SLEEP": "Mettre en veille",
    "intent.FIND_ELEMENT": "Localiser à l'écran",
    "intent.MULTIMODAL_CLICK_TARGET": "Cliquer sur la cible visée",
    "intent.MULTIMODAL_OPEN_TARGET": "Ouvrir la cible visée",
    "intent.EXECUTE_MACRO": "Lancer une macro",
    "intent.COMPOUND_PLAN": "Plan composite",

    # ---------------- Log table & Toasts (FR) ----------------
    "col.time": "Heure",
    "col.command": "Commande",
    "col.intent": "Intention",
    "col.confidence": "Confiance",
    "col.risk": "Risque",
    "col.result": "Résultat",
    "log.search_placeholder": "🔍 Rechercher dans l'historique...",
    "log.export_csv": "Exporter CSV",
    "toast.screenshot_saved": "Capture d'écran enregistrée ✓",
    "toast.csv_exported": "Journal exporté en CSV ✓",
    "toast.action_executed": "{action} exécuté ✓",
    "main.eco_mode": "Mode Éco",
    "toast.eco_activated": "Mode Éco activé (CPU > 80%)",

    # ---------------- App Profiles (FR) ----------------
    "profile.browser": "Navigateur",
    "profile.media": "Lecteur Média",
    "profile.document": "Document",
    "profile.desktop": "Bureau",
    "profile.active_label": "Profil actif : {profile}",
    "profile.action.browser_back": "Précédent (Historique)",
    "profile.action.browser_forward": "Suivant (Historique)",
    "profile.action.media_seek_back": "Reculer 10s",
    "profile.action.media_seek_forward": "Avancer 10s",
    "profile.action.media_play_pause": "Lecture / Pause",
    "profile.action.doc_page_prev": "Page précédente",
    "profile.action.doc_page_next": "Page suivante",
    "profile.action.click": "Clic gauche",

    # ---------------- Macros (FR) ----------------
    "macro.title": "Macros d'automatisation",
    "macro.heading": "Séquences d'automatisation personnalisées",
    "macro.saved": "Macros enregistrées",
    "macro.preview": "Étapes et déclencheurs",
    "macro.run": "Exécuter",
    "macro.new": "+ Nouveau Macro",
    "macro.empty": "Aucun macro configuré. Cliquez sur '+ Nouveau Macro' pour créer votre séquence.",
    "macro.running_title": "Exécution de macro",
    "macro.running_body": "Exécution de la macro : {name}",
    "macro.create_title": "Créer un nouveau Macro",
    "macro.name": "Nom du macro",
    "macro.name_placeholder": "ex : Démarrage matin, Session code...",
    "macro.voice_trigger": "Déclencheur vocal (optionnel)",
    "macro.voice_placeholder": "ex : démarre le travail, mon setup...",
    "macro.gesture_trigger": "Déclencheur gestuel (optionnel)",
    "macro.none": "Aucun",
    "macro.steps": "Étapes du macro",
    "macro.add_step": "+ Ajouter une étape",
    "macro.remove_step": "Supprimer l'étape",
    "macro.action": "Type d'action",
    "macro.target": "Cible / Paramètre",
    "macro.delay": "Délai (s)",
    "macro.save": "Enregistrer le macro",
    "macro.step_launch_app": "Lancer une application",
    "macro.step_type_text": "Taper du texte",
    "macro.step_key_press": "Appuyer sur une touche",
    "macro.step_hotkey": "Raccourci clavier (ex: ctrl+c)",
    "macro.step_volume": "Régler le volume (0-100)",
    "macro.step_brightness": "Régler la luminosité (0-100)",
    "macro.step_folder": "Ouvrir un dossier",
    "macro.step_wait": "Attendre (secondes)",

    # ---------------- Privacy & Safety (FR) ----------------
    "privacy.mode": "Mode Confidentialité",
    "privacy.mode_active": "🛡️ CONFIDENTIALITÉ ACTIVE",
    "privacy.cam_on": "📷 CAM ON",
    "privacy.cam_off": "📷 CAM OFF",
    "privacy.mic_on": "🎙️ MIC ON",
    "privacy.mic_off": "🎙️ MIC OFF",
    "toast.privacy_mode_activated": "Mode Confidentialité : Caméra et Micro coupés ✓",
    "toast.privacy_mode_deactivated": "Mode Confidentialité désactivé : Capteurs réactivés ✓",
    "security.prompt_delete": "Êtes-vous sûr de vouloir supprimer définitivement : {target} ?",
    "security.prompt_empty_bin": "Êtes-vous sûr de vouloir vider la corbeille ?",
    "security.prompt_shutdown": "Êtes-vous sûr de vouloir éteindre le PC ?",
    "security.prompt_restart": "Êtes-vous sûr de vouloir redémarrer le PC ?",
    "security.prompt_close": "Êtes-vous sûr de vouloir fermer l'application ?",
    "security.confirm_btn": "✔ Confirmer",
    "security.cancel_btn": "✖ Annuler",
    "security.countdown": "Annulation auto dans {seconds}s",
    "log.clear": "Effacer l'historique",
    "log.clear_confirm_title": "Effacer le journal d'audit",
    "log.clear_confirm_msg": "Êtes-vous sûr de vouloir effacer définitivement le journal d'audit ?",
    "toast.log_cleared": "Journal d'audit effacé ✓",
}


# --------------------------------------------------------------------------- #
# Arabic
# --------------------------------------------------------------------------- #

_AR: Dict[str, str] = {
    "app.name": "حاج — تحكّم بدون لمس",
    "app.tagline": "تحكّم كامل بدون لمس — صوت وإيماءات ورؤية وذكاء اصطناعي محلي",
    "app.offline_first": "دون إنترنت",
    "app.tray_tooltip": "حاج — تحكّم بدون لمس",

    "common.on": "مُفعَّل",
    "common.off": "مُعطَّل",
    "common.close": "إغلاق",
    "common.done": "تم",
    "common.cancel": "إلغاء",
    "common.back": "السابق",
    "common.next": "التالي",
    "common.finish": "إنهاء",
    "common.delete": "حذف",
    "common.run": "تشغيل",
    "common.execute": "تنفيذ",
    "common.language": "اللغة",
    "common.yes": "نعم",
    "common.no": "لا",
    "common.confidence": "الدقة",
    "common.step_of": "الخطوة {current} من {total}",

    "main.emergency_stop": "⚠  أوقف حاج",
    "main.emergency_restore": "↺  استعادة النظام",
    "main.emergency_active": "⚠  تم تفعيل التوقف الطارئ",
    "main.emergency_halted": "تم إيقاف كل عمليات الأتمتة فوراً.",
    "main.voice": "الصوت",
    "main.gesture": "الإيماءات",
    "main.vision": "الرؤية",
    "main.toggle": "{name}: {state}",
    "main.listening": "جارٍ الاستماع…",
    "main.ready": "جاهز",
    "main.profile": "نمط الأداء",
    "main.telemetry": "المعالج {cpu}%   ·   الذاكرة {ram}%   ·   {fps} إطار/ث   ·   {latency} مللي ثانية",
    "main.gesture_info": "{gesture}   ·   {conf}%",
    "main.skeleton": "هيكل اليد",
    "main.cmd_title": "الأمر الحالي والنية",
    "main.cmd_idle": "قل «يا حاج» ثم طلبك (مثال: «يا حاج افتح فيسبوك»)",
    "main.intent_line": "النية {intent}   ·   الخطورة {risk}   ·   {result}",
    "main.intent_standby": "الانتظار",
    "main.cmd_input_hint": "اكتب أمراً (مثل «افتح Chrome» أو «Morning Setup») ثم اضغط Enter…",
    "main.log_title": "سجل الأحداث المباشر — الخصوصية مضمونة",
    "main.security_confirm": "يتطلب تأكيداً: {command}",
    "main.security_hint": "الخطورة {risk} · قل «{yes}» أو ارفع إبهامك للتأكيد.",
    "main.calibration": "المعايرة",
    "main.privacy": "الخصوصية",
    "main.accessibility": "إمكانية الوصول",
    "main.keyboard": "لوحة المفاتيح",
    "main.macros": "الماكروهات",
    "main.demo": "الوضع التجريبي",
    "main.footer": "لا تغادر بياناتك هذا الجهاز أبداً",
    "main.minimized_title": "حاج — تحكّم بدون لمس",
    "main.minimized_body": "تم التصغير إلى منطقة إشعارات ويندوز، ويظل التحكّم بدون لمس نشطاً في الخلفية.",
    "main.status_ready": "تمت استعادة النظام — التحكّم بدون لمس نشط من جديد",
    "main.ready_desc": "الصوت والإيماءات والرؤية في حالة انتظار. قل كلمة التنبيه للبدء.",
    "main.dock_title": "🎮  التحكّم الكامل بالكمبيوتر:",
    "main.web_companion": "🌐  Companion Web",
    "main.theme_light": "☀️ الوضع الفاتح",
    "main.theme_dark": "🌙 الوضع الداكن",
    "main.theme_high_contrast": "⚡ تباين عالٍ",
    "main.compact_mode": "🗗 الوضع المصغر",
    "main.full_mode": "🗖 الوضع الكامل",
    "main.dominant_hand": "اليد الأساسية",
    "toast.dominant_hand_changed": "تم ضبط اليد الأساسية: {hand} ✓",
    "main.view_dashboard": "🌐 لوحة التحكم العصرية",
    "main.view_native": "📷 الكاميرا والحساسات",
    "main.view_dashboard_toast": "تم التبديل إلى لوحة التحكم التفاعلية",
    "main.view_native_toast": "تم التبديل إلى واجهة الحساسات والكاميرا",

    "dock.desktop": "🖥️  سطح المكتب",
    "dock.task_view": "📑  المهام",
    "dock.snap_left": "🗔  يسار",
    "dock.snap_right": "🗖  يمين",
    "dock.screenshot": "📸  التقاط",
    "dock.volume_up": "🔊  صوت +",
    "dock.volume_down": "🔉  صوت -",
    "dock.volume_mute": "🔇  كتم",
    "dock.keyboard": "⌨️  لوحة",
    "dock.lock": "🔒  قفل",
    "dock.task_manager": "⚡  المهام",

    "calib.auto_btn": "⚡  المعايرة التلقائية",
    "calib.auto_running": "⚡  تحليل جارٍ…",
    "calib.auto_start": "⚡  جارٍ المعايرة التلقائية…",
    "calib.auto_detail": "قياس الكاميرا وعدد الإطارات وضجيج الخلفية وحساب الحدود المثلى…",
    "calib.auto_done": "✅  نجحت المعايرة التلقائية (النتيجة {score}%)",
    "calib.auto_values": "الكاميرا: {fps} إطار/ث · حد القرص: {pinch} · التنعيم: {smoothing} · السرعة: {speed}",
    "calib.auto_failed": "⚠️  فشلت المعايرة التلقائية",
    "shot.saved": "تم التقاط صورة الشاشة",
    "shot.saved_at": "حُفظت في: {path}",
    "shot.failed": "خطأ في الالتقاط: {error}",

    # ---------------- التشخيص والتفعيل ----------------
    "diag.no_hand": "لا توجد يد في الإطار",
    "diag.low_light": "الإضاءة ضعيفة — يرجى زيادة الإضاءة",
    "diag.out_of_frame": "اليد خارج الإطار جزئياً",
    "diag.too_far": "اليد بعيدة جداً — اقترب أكثر",
    "diag.too_close": "اليد قريبة جداً — ابتعد قليلاً",
    "diag.disarmed": "معطّل · افتح كفك ثانية واحدة للتفعيل",
    "diag.arming": "جارٍ التفعيل… {progress} %",
    "diag.disarming": "جارٍ إلغاء التفعيل… {progress} %",
    "diag.armed_ready": "مفعّل · جاهز للإيماءات",
    "arm.armed": "مفعّل",
    "arm.disarmed": "معطّل",
    "emergency.shortcut_hint": "إيقاف الطوارئ: Ctrl+Alt+Esc",

    # ---------------- المعايرة وجودة الإشارة ----------------
    "calib.quality_score": "الجودة المباشرة: {score} %",
    "calib.tip_closer": "قرّب يدك أكثر من الكاميرا",
    "calib.tip_further": "أبعد يدك قليلاً عن الكاميرا",
    "calib.tip_more_light": "الإضاءة ضعيفة — يرجى تشغيل إضاءة الغرفة",
    "calib.tip_less_light": "الإضاءة ساطعة جداً أو معاكسة",
    "calib.tip_center_hand": "ضع يدك في منتصف إطار الكاميرا",
    "calib.tip_optimal": "الظروف مثالية! حافظ على موضعك",
    "calib.dominant_hand": "اليد الأساسية",
    "calib.hand_right": "اليد اليمنى",
    "calib.hand_left": "اليد اليسرى",

    "col.time": "الوقت",
    "col.command": "الأمر",
    "col.intent": "النية",
    "col.risk": "الخطورة",
    "col.result": "النتيجة",

    "calib.title": "معالج المعايرة",
    "calib.subtitle": "يقيس حاج كاميرتك وميكروفونك ويدك، ثم يضبط كل الحدود بنفسه.",
    "calib.step_devices": "الأجهزة",
    "calib.step_devices_desc": "فحص حاج الأجهزة واحتفظ بما استجاب. اختر الكاميرا والميكروفون اللذين تريد إبقائهما.",
    "calib.step_camera": "الكاميرا",
    "calib.step_camera_desc": "قياس عدد الإطارات في الثانية وزمن الاستجابة الفعلي الذي تقدّمه كاميرتك.",
    "calib.step_mic": "الميكروفون",
    "calib.step_mic_desc": "قياس ضجيج الخلفية ليُميّز التعرّف الصوتي صوتك عن ضجيج الغرفة.",
    "calib.step_hand": "تتبّع اليد",
    "calib.step_hand_desc": "أمسك يدك أمام الكاميرا ووجه راحة اليد نحو العدسة، ودع حاج يتعرّف عليها.",
    "calib.step_pinch": "حساسية القرص",
    "calib.step_pinch_desc": "اضغط بإبهامك وسبابتك ثم افتحهما ثلاث مرات. يضع حاج حدّ النقر في الفجوة بين يدك المفتوحة والمغلقة، بلا أرقام تخمّنها.",
    "calib.step_reach": "مدى الحركة المريح",
    "calib.step_reach_desc": "حرّك سبابتك ضمن مداك المريح. يصبح هذا المدى الشاشة كاملة، فلا حاجة للتمدّد نحو الزوايا.",
    "calib.step_adaptive": "تعلّم مستمر",
    "calib.step_adaptive_desc": "من هنا فصاعداً، يتحقق حاج من حدّ القرص مع يدك لحظياً ويصحّح نفسه عند تغيّر الإضاءة أو وضعيتك.",
    "calib.step_summary": "معايرتك",
    "calib.step_summary_desc": "كل ما يلي مقيس لا مرخم. وما قِيست دقته منخفضة يستحق إعادة القياس.",
    "calib.rescan": "إعادة البحث",
    "calib.device_camera": "الكاميرا",
    "calib.device_microphone": "الميكروفون",
    "calib.no_camera": "لم تستجب أي كاميرا",
    "calib.no_mic": "لم يُعثر على ميكروفون، سيُستخدم الميكروفون الافتراضي",
    "calib.camera_measuring": "جارٍ قياس بث الفيديو…",
    "calib.camera_result": "{device} · {resolution} بسرعة {fps} إطار/ث · استجابة {latency} مللي ثانية",
    "calib.mic_measuring": "جارٍ قياس ضجيج الخلفية، ابقَ صامتاً…",
    "calib.mic_result": "ضجيج الخلفية {floor} · حدّ الصوت {threshold}",
    "calib.hand_waiting": "لم تُكتشف اليد، ضعها داخل الإطار",
    "calib.hand_locked": "التُقطت اليد · 21 نقطة معلم",
    "calib.pinch_waiting": "بانتظار أول ضغطة",
    "calib.pinch_count": "{done} من {total} ضغطات",
    "calib.reach_waiting": "حرّك سبابتك في كامل مداك المريح",
    "calib.reach_live": "المدى المقيس: {width}٪ × {height}٪",
    "calib.adaptive_enabled": "تعلّم مستمر",
    "calib.adaptive_status": "تم تحليل {samples} عيّنة",
    "calib.adaptive_waiting": "في انتظار أولى الإطارات...",
    "calib.value_pinch": "حدّ القرص",
    "calib.value_deadzone": "المنطقة الميتة للاهتزاز",
    "calib.value_smoothing": "تنعيم EMA",
    "calib.value_cursor_speed": "سرعة المؤشر",
    "calib.value_drag": "مهلة السحب",
    "calib.value_double": "نافذة القرص المزدوج",
    "calib.value_scroll": "سرعة التمرير",
    "calib.value_swipe": "حدّ السحب الأفقي",
    "calib.value_box": "مجال الحركة",
    "calib.value_noise": "ضجيج خلفية الميكروفون",
    "calib.value_latency": "استجابة الكاميرا",
    "calib.measure": "قياس",
    "calib.remeasure": "إعادة القياس",
    "calib.apply": "تطبيق المعايرة",
    "calib.applied": "طُبّقت المعايرة، حدّ القرص الآن {value}",
    "calib.confidence_note": "الثقة {percent}٪",
    "calib.skipped": "غير مقيس، أُبقيت القيمة الحالية",

    "privacy.title": "لوحة الخصوصية",
    "privacy.heading": "الخصوصية والأمان",
    "privacy.intro": "كل عمليات الرؤية الحاسوبية والتعرّف الصوتي ومنطق الأتمتة تُنفَّذ محلياً على هذا الجهاز، ولا يُرسَل أي شيء إلى أي خدمة خارجية.",
    "privacy.microphone": "الميكروفون",
    "privacy.camera": "بث الكاميرا",
    "privacy.voice_processing": "معالجة الصوت",
    "privacy.gesture_processing": "معالجة الإيماءات",
    "privacy.internet": "الاتصال بالإنترنت",
    "privacy.telemetry": "التتبّع السحابي",
    "privacy.biometric": "البيانات الحيوية",
    "privacy.remote_apis": "الواجهات البعيدة",
    "privacy.status_enabled": "مُفعَّل",
    "privacy.status_active": "نشط",
    "privacy.status_local": "محلي 100%",
    "privacy.status_offline": "دون إنترنت",
    "privacy.status_disabled": "مُعطَّل",
    "privacy.status_never": "لا يُحفظ أبداً",
    "privacy.status_blocked": "محجوب",
    "privacy.guarantee": "ضمان الخصوصية — تُمحى إطارات الكاميرا من الذاكرة فور استخراج نقاط المعالم، ولا يُكتب أي ملف صوتي أو صورة وجه على القرص.",
    "privacy.offline_active": "الوضع دون إنترنت مُفعَّل",
    "privacy.hybrid_mode": "الوضع الهجين",

    "access.title": "إمكانية الوصول وأنماط الإدخال",
    "access.heading": "أنماط الإدخال المُيسَّرة",
    "access.intro": "اختر نمط التفاعل المناسب لاحتياجك، دون فأرة ولا لوحة مفاتيح.",
    "access.profiles_title": "نمط التفاعل",
    "access.options_title": "خيارات الراحة",
    "access.mode_MULTIMODAL_name": "متعدد الوسائط",
    "access.mode_MULTIMODAL_desc": "صوت وإيماءات ورؤية معًا.",
    "access.mode_VOICE_ONLY_name": "الصوت فقط",
    "access.mode_VOICE_ONLY_desc": "تعرّف صوتي وإملاء.",
    "access.mode_GESTURE_ONLY_name": "الإيماءات فقط",
    "access.mode_GESTURE_ONLY_desc": "تتبّع اليد مع فأرة افتراضية.",
    "access.mode_HEAD_ONLY_name": "الرأس فقط",
    "access.mode_HEAD_ONLY_desc": "إمالة للتنقّل وهزّ للنقر.",
    "access.mode_VOICE_GAZE_name": "الصوت والنظر",
    "access.mode_VOICE_GAZE_desc": "تركيز بالثبات مع أوامر صوتية.",
    "access.dwell_name": "النقر بالثبات",
    "access.dwell_desc": "ثبات المؤشر 1.0 ثانية يُحدث نقرة.",
    "access.contrast_desc": "لوحة ألوان سوداء ونيون عالية التباين لقراءة مثالية.",
    "access.large_cursor_name": "مؤشر افتراضي كبير",
    "access.large_cursor_desc": "تباين عالٍ لتتبّع أسهل.",

    "macro.title": "مدير الماكروهات",
    "macro.heading": "ماكروهات وتسلسلات الأتمتة",
    "macro.saved": "الماكروهات المحفوظة",
    "macro.preview": "معاينة خطوات الماكرو",
    "macro.run": "▶  شغّل الماكرو",
    "macro.running_title": "الماكرو قيد التشغيل",
    "macro.running_body": "بدأ الماكرو «{name}» في الخلفية.",
    "macro.empty": "لا يوجد ماكرو محفوظ بعد.",

    "demo.title": "الوضع التجريبي التفاعلي",
    "demo.heading": "عرض قدرات النظام",
    "demo.intro": "اختر سيناريو لتُنفّذه ومراقبته أثناء عمل طبقة الأتمتة بدون لمس.",
    "demo.s1": "1.  صوت — «افتح Calculator ثم ارفع الصوت»",
    "demo.s2": "2.  متعدد الوسائط — أشِر إلى هدف ثم قل «افتحه»",
    "demo.s3": "3.  رؤية الشاشة — «أين زر الإغلاق؟»",
    "demo.s4": "4.  تصفّح الويب — «افتح تبويب جديد ثم ابحث عن Arduino»",
    "demo.s5": "5.  الإملاء والتحرير — «اكتب مرحبا بكم في تطبيقي»",
    "demo.s6": "6.  أتمتة الماكرو — «Morning Setup»",
    "demo.scenarios_title": "السيناريوهات",
    "demo.output": "مخرجات التنفيذ المباشرة",
    "demo.ready": "جاهز. اختر أحد السيناريوهات أعلاه…",
    "demo.executing": "جارٍ التنفيذ: «{command}»",
    "demo.result": "النتيجة: {result}",

    "tray.show": "إظهار لوحة التحكم",
    "tray.voice": "التحكّم الصوتي",
    "tray.gesture": "التحكّم بالإيماءات",
    "tray.offline": "الوضع دون إنترنت",
    "tray.emergency": "⚠  التوقف الطارئ",
    "tray.quit": "إنهاء حاج",

    "hud.title": "حاج — تحكّم بدون لمس",
    "hud.awaiting": "بانتظار «يا حاج»…",
    "hud.listening": "جارٍ الاستماع…",
    "hud.ready": "جاهز",
    "hud.ready_active": "جاهز — التحكّم بدون لمس نشط",
    "hud.badge_ready": "جاهز",
    "hud.badge_tracking": "تتبّع",
    "hud.badge_halted": "متوقف",
    "hud.badge_confirm": "تأكيد؟",
    "hud.emergency": "⚠  التوقف الطارئ مُفعَّل",
    "hud.confirm": "تأكيد: {command}؟",

    "kb.title": "لوحة مفاتيح حاج الافتراضية",
    "kb.heading": "لوحة مفاتيح حاج بدون لمس",
    "kb.bksp": "⌫",
    "kb.tab": "Tab",
    "kb.enter": "Enter",
    "kb.space": "مسافة",
    "kb.copy": "نسخ",
    "kb.paste": "لصق",
    "kb.undo": "تراجع",
    "kb.del_word": "حذف كلمة",
    "kb.next_line": "سطر جديد",

    "camera.standby": "الكاميرا في الانتظار",

    "gesture.NONE": "لا إيماءة",
    "gesture.INDEX_POINT": "تأشير بالسبابة",
    "gesture.PINCH": "قرص",
    "gesture.DOUBLE_PINCH": "قرص مزدوج",
    "gesture.PINCH_HOLD": "قرص مع الاستمرار",
    "gesture.OPEN_PALM": "راحة اليد مفتوحة",
    "gesture.TWO_FINGER_SCROLL_UP": "تمرير لأعلى",
    "gesture.TWO_FINGER_SCROLL_DOWN": "تمرير لأسفل",
    "gesture.SWIPE_LEFT": "سحب لليسار",
    "gesture.SWIPE_RIGHT": "سحب لليمين",
    "gesture.THUMB_UP": "إبهام لأعلى",
    "gesture.FIST": "قبضة اليد",

    "risk.LOW": "منخفض",
    "risk.MEDIUM": "متوسط",
    "risk.HIGH": "مرتفع",
    "risk.CRITICAL": "حرج",

    "result.SUCCESS": "نجاح",
    "result.FAILED": "فشل",

    "profile.ECO": "اقتصادي",
    "profile.BALANCED": "متوازن",
    "profile.PERFORMANCE": "الأداء",
    "profile.AI_MAX": "الذكاء الأقصى",

    "intent.UNKNOWN": "غير معروف",
    "intent.LAUNCH_APP": "فتح تطبيق",
    "intent.CLOSE_WINDOW": "إغلاق النافذة",
    "intent.MINIMIZE_WINDOW": "تصغير النافذة",
    "intent.MAXIMIZE_WINDOW": "تكبير النافذة",
    "intent.RESTORE_WINDOW": "استعادة النافذة",
    "intent.SWITCH_APP": "تبديل التطبيق",
    "intent.SHOW_DESKTOP": "إظهار سطح المكتب",
    "intent.OPEN_FOLDER": "فتح مجلد",
    "intent.CREATE_FOLDER": "إنشاء مجلد",
    "intent.DELETE_FILE": "حذف ملف",
    "intent.DELETE_FOLDER": "حذف مجلد",
    "intent.SEARCH_FILES": "البحث عن ملفات",
    "intent.OPEN_RECENT_FILE": "فتح ملف حديث",
    "intent.BROWSER_NEW_TAB": "تبويب جديد",
    "intent.BROWSER_CLOSE_TAB": "إغلاق التبويب",
    "intent.BROWSER_NEXT_TAB": "التبويب التالي",
    "intent.BROWSER_PREV_TAB": "التبويب السابق",
    "intent.BROWSER_SEARCH": "البحث في الويب",
    "intent.NAVIGATE_BACK": "رجوع",
    "intent.NAVIGATE_FORWARD": "تقدّم",
    "intent.NAVIGATE_REFRESH": "تحديث الصفحة",
    "intent.TOGGLE_FULLSCREEN": "ملء الشاشة",
    "intent.VOLUME_UP": "رفع الصوت",
    "intent.VOLUME_DOWN": "خفض الصوت",
    "intent.VOLUME_MUTE": "كتم الصوت",
    "intent.VOLUME_SET": "ضبط الصوت",
    "intent.MEDIA_PLAY_PAUSE": "تشغيل / إيقاف",
    "intent.MEDIA_NEXT": "المقطع التالي",
    "intent.MEDIA_PREVIOUS": "المقطع السابق",
    "intent.BRIGHTNESS_UP": "رفع السطوع",
    "intent.BRIGHTNESS_DOWN": "خفض السطوع",
    "intent.BRIGHTNESS_SET": "ضبط السطوع",
    "intent.SCREENSHOT": "لقطة الشاشة",
    "intent.CLIPBOARD_COPY": "نسخ",
    "intent.CLIPBOARD_PASTE": "لصق",
    "intent.CLIPBOARD_CUT": "قص",
    "intent.SELECT_ALL": "تحديد الكل",
    "intent.UNDO": "تراجع",
    "intent.DICTATION": "إملاء",
    "intent.SCROLL_UP": "تمرير لأعلى",
    "intent.SCROLL_DOWN": "تمرير لأسفل",
    "intent.SNAP_WINDOW_LEFT": "إلحاق يسار",
    "intent.SNAP_WINDOW_RIGHT": "إلحاق يمين",
    "intent.TASK_VIEW": "عرض المهام",
    "intent.NEW_DESKTOP": "سطح مكتب جديد",
    "intent.CLOSE_DESKTOP": "إغلاق سطح المكتب",
    "intent.NEXT_DESKTOP": "سطح المكتب التالي",
    "intent.PREV_DESKTOP": "سطح المكتب السابق",
    "intent.OPEN_TASK_MANAGER": "مدير المهام",
    "intent.EMPTY_RECYCLE_BIN": "إفراغ سلة المحذوفات",
    "intent.ZOOM_IN": "تكبير",
    "intent.ZOOM_OUT": "تصغير",
    "intent.ZOOM_RESET": "إعادة ضبط التكبير",
    "intent.REFRESH_SCREEN": "تحديث الشاشة",
    "intent.TOGGLE_KEYBOARD_HUD": "لوحة المفاتيح الافتراضية",
    "intent.SYSTEM_LOCK": "قفل الجلسة",
    "intent.SYSTEM_RESTART": "إعادة التشغيل",
    "intent.SYSTEM_SHUTDOWN": "إيقاف التشغيل",
    "intent.SYSTEM_SLEEP": "السكون",
    "intent.FIND_ELEMENT": "تحديد على الشاشة",
    "intent.MULTIMODAL_CLICK_TARGET": "نقر الهدف المُشار إليه",
    "intent.MULTIMODAL_OPEN_TARGET": "فتح الهدف المُشار إليه",
    "intent.EXECUTE_MACRO": "تشغيل ماكرو",
    "intent.COMPOUND_PLAN": "خطة مركّبة",

    # ---------------- Log table & Toasts (AR) ----------------
    "col.time": "الوقت",
    "col.command": "الأمر",
    "col.intent": "القصد",
    "col.confidence": "الدقة",
    "col.risk": "الخطورة",
    "col.result": "النتيجة",
    "log.search_placeholder": "🔍 بحث في السجل...",
    "log.export_csv": "تصدير CSV",
    "toast.screenshot_saved": "تم حفظ لقطة الشاشة ✓",
    "toast.csv_exported": "تم تصدير السجل بصيغة CSV ✓",
    "toast.action_executed": "تم تنفيذ {action} ✓",
    "main.eco_mode": "الوضع الاقتصادي",
    "toast.eco_activated": "تم تفعيل الوضع الاقتصادي (المعالج > 80%)",

    # ---------------- App Profiles (AR) ----------------
    "profile.browser": "متصفح الويب",
    "profile.media": "مشغّل الوسائط",
    "profile.document": "مستند وعرض",
    "profile.desktop": "سطح المكتب",
    "profile.active_label": "الملف النشط: {profile}",
    "profile.action.browser_back": "رجوع (السجل)",
    "profile.action.browser_forward": "تقدم (السجل)",
    "profile.action.media_seek_back": "تأخير 10 ثوانٍ",
    "profile.action.media_seek_forward": "تقديم 10 ثوانٍ",
    "profile.action.media_play_pause": "تشغيل / إيقاف مؤقت",
    "profile.action.doc_page_prev": "الصفحة السابقة",
    "profile.action.doc_page_next": "الصفحة التالية",
    "profile.action.click": "نقرة يسار",

    # ---------------- Macros (AR) ----------------
    "macro.title": "ماكرو الأتمتة المخصصة",
    "macro.heading": "سلاسل أتمتة مخصصة متعددة الخطوات",
    "macro.saved": "الماكرو المحفوظ",
    "macro.preview": "الخطوات ومفاتيح التشغيل",
    "macro.run": "تشغيل الماكرو",
    "macro.new": "+ ماكرو جديد",
    "macro.empty": "لا توجد سلاسل ماكرو. انقر فوق '+ ماكرو جديد' لإنشاء أول سلسلة أتمتة.",
    "macro.running_title": "تشغيل الماكرو",
    "macro.running_body": "جاري تنفيذ الماكرو: {name}",
    "macro.create_title": "إنشاء ماكرو جديد",
    "macro.name": "اسم الماكرو",
    "macro.name_placeholder": "مثال: إعداد الصباح، وضع البرمجة...",
    "macro.voice_trigger": "المفتاح الصوتي (اختياري)",
    "macro.voice_placeholder": "مثال: افتح مكتبي، ابدأ العمل...",
    "macro.gesture_trigger": "المفتاح الإيمائي (اختياري)",
    "macro.none": "بدون",
    "macro.steps": "خطوات الماكرو",
    "macro.add_step": "+ إضافة خطوة",
    "macro.remove_step": "حذف الخطوة",
    "macro.action": "نوع الإجراء",
    "macro.target": "الهدف / النص / المفتاح",
    "macro.delay": "الانتظار (ثوانٍ)",
    "macro.save": "حفظ الماكرو",
    "macro.step_launch_app": "تشغيل تطبيق",
    "macro.step_type_text": "كتابة نص",
    "macro.step_key_press": "ضغط مفتاح",
    "macro.step_hotkey": "اختصار لوحة المفاتيح (مثال ctrl+c)",
    "macro.step_volume": "تعديل مستوى الصوت (0-100)",
    "macro.step_brightness": "تعديل السطوع (0-100)",
    "macro.step_folder": "فتح مجلد",
    "macro.step_wait": "انتظار (ثوانٍ)",

    # ---------------- Privacy & Safety (AR) ----------------
    "privacy.mode": "وضع الخصوصية",
    "privacy.mode_active": "🛡️ وضع الخصوصية مفعل",
    "privacy.cam_on": "📷 الكاميرا مفعلة",
    "privacy.cam_off": "📷 الكاميرا معطلة",
    "privacy.mic_on": "🎙️ الميكروفون مفعل",
    "privacy.mic_off": "🎙️ الميكروفون معطل",
    "toast.privacy_mode_activated": "تم تفعيل وضع الخصوصية: الكاميرا والميكروفون معطلان ✓",
    "toast.privacy_mode_deactivated": "تم تعطيل وضع الخصوصية: تم استعادة الكاميرا والميكروفون ✓",
    "security.prompt_delete": "هل أنت متأكد من الحذف النهائي لـ: {target}؟",
    "security.prompt_empty_bin": "هل أنت متأكد من إفراغ سلة المحذوفات؟",
    "security.prompt_shutdown": "هل أنت متأكد من إيقاف تشغيل الكمبيوتر؟",
    "security.prompt_restart": "هل أنت متأكد من إعادة تشغيل الكمبيوتر؟",
    "security.prompt_close": "هل أنت متأكد من إغلاق هذا التطبيق؟",
    "security.confirm_btn": "✔ تأكيد",
    "security.cancel_btn": "✖ إلغاء",
    "security.countdown": "إلغاء تلقائي خلال {seconds} ثوانٍ",
    "log.clear": "مسح السجل",
    "log.clear_confirm_title": "مسح سجل الأنشطة",
    "log.clear_confirm_msg": "هل أنت متأكد من حذف سجل الأنشطة بالكامل نهائياً؟",
    "toast.log_cleared": "تم مسح سجل الأنشطة ✓",
}


STRINGS: Dict[str, Dict[str, str]] = {
    "en": _EN,
    "fr": _FR,
    "ar": _AR,
}


# --------------------------------------------------------------------------- #
# Translator
# --------------------------------------------------------------------------- #

def _strip_prefix(token: str) -> str:
    """Removes a Python enum repr such as ``IntentType.`` or ``HandGesture.``."""
    token = str(token).strip()
    if token.startswith(("IntentType.", "HandGesture.", "PerformanceProfile.")):
        token = token.split(".", 1)[1]
    elif ".__" in token:  # <enum 'HandGesture'>
        token = token.rsplit(".", 1)[-1]
    return token


class Translator:
    """Thread-safe holder of the active language and the string catalogue."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._language = FALLBACK_LANGUAGE
        self._listeners: List[Callable[[str], None]] = []
        self.load()

    # -- state -------------------------------------------------------------- #
    def load(self) -> str:
        """Reads the persisted language preference and applies it."""
        try:
            code = SettingsManager().get("language", FALLBACK_LANGUAGE)
        except Exception:
            code = FALLBACK_LANGUAGE
        self.set_language(code, persist=False)
        return self._language

    def set_language(self, code: str, persist: bool = True) -> None:
        code = (code or FALLBACK_LANGUAGE).lower()[:2]
        if code not in STRINGS:
            code = FALLBACK_LANGUAGE
        with self._lock:
            if code == self._language:
                return
            self._language = code
        if persist:
            try:
                SettingsManager().set("language", code)
            except Exception:
                pass
        self._notify()

    @property
    def language(self) -> str:
        return self._language

    @property
    def font_stack(self) -> str:
        return FONT_STACKS.get(self._language, FONT_STACKS[FALLBACK_LANGUAGE])

    @property
    def is_rtl(self) -> bool:
        return self._language in RTL_LANGUAGES

    @staticmethod
    def native_name(code: str) -> str:
        return LANGUAGES.get(code, code.upper())

    @staticmethod
    def available() -> List[str]:
        return list(LANGUAGES.keys())

    # -- lookup ------------------------------------------------------------- #
    def raw(self, key: str) -> str:
        table = STRINGS.get(self._language, {})
        if key in table:
            return table[key]
        fallback = STRINGS[FALLBACK_LANGUAGE]
        return fallback.get(key, key)

    def translate(self, key: str, **kwargs: Any) -> str:
        text = self.raw(key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def translate_enum(self, prefix: str, value: Any, fallback: str = "") -> str:
        """Translates an enum-ish token such as ``PINCH`` or ``VOLUME_UP``."""
        if value is None:
            return fallback
        token = _strip_prefix(value)
        if not token:
            return fallback
        key = f"{prefix}.{token}"
        translated = self.raw(key)
        return fallback if translated == key else translated

    # -- change notification ------------------------------------------------ #
    def add_listener(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(self._language)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[i18n] Listener error: {exc}")


_translator = Translator()


# --------------------------------------------------------------------------- #
# Module-level convenience API
# --------------------------------------------------------------------------- #

def get_translator() -> Translator:
    return _translator


def current_language() -> str:
    return _translator.language


def set_language(code: str, persist: bool = True) -> None:
    _translator.set_language(code, persist=persist)


def is_rtl() -> bool:
    return _translator.is_rtl


def font_stack() -> str:
    return _translator.font_stack


def native_language_name(code: str) -> str:
    return _translator.native_name(code)


def available_languages() -> List[str]:
    return _translator.available()


def on_language_changed(callback: Callable[[str], None]) -> None:
    _translator.add_listener(callback)


def tr(key: str, **kwargs: Any) -> str:
    """Returns the localised string for ``key`` in the active language."""
    return _translator.translate(key, **kwargs)


def tr_gesture(value: Any) -> str:
    return _translator.translate_enum("gesture", value, fallback=str(value or ""))


def tr_intent(value: Any) -> str:
    return _translator.translate_enum("intent", value, fallback=str(value or ""))


def tr_risk(value: Any) -> str:
    return _translator.translate_enum("risk", value, fallback=str(value or ""))


def tr_result(value: Any) -> str:
    return _translator.translate_enum("result", value, fallback=str(value or ""))


def tr_profile(value: Any) -> str:
    return _translator.translate_enum("profile", value, fallback=str(value or ""))
