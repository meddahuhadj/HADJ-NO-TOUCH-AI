"""نصوص الواجهة بالعربية والإنجليزية."""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "app_name": {"ar": "التحكم بدون لمس", "en": "No-Touch Control"},
    # حالات
    "state_loading": {"ar": "جارٍ تحميل نموذج الصوت…", "en": "Loading speech model…"},
    "state_ready": {"ar": "يستمع لكلمة التنبيه «{wake}»", "en": "Listening for “{wake}”"},
    "state_continuous": {"ar": "استماع مستمر", "en": "Continuous listening"},
    "state_armed": {"ar": "تفضّل… أنا أستمع", "en": "Go ahead… listening"},
    "state_paused": {"ar": "التحكم متوقف. قل «{wake} استأنف»", "en": "Control paused. Say “{wake} resume”"},
    "state_mic_error": {"ar": "خطأ في الميكروفون أو النموذج: {detail}", "en": "Microphone/model error: {detail}"},
    "state_muted": {"ar": "الميكروفون مكتوم", "en": "Microphone muted"},
    # نتائج
    "done": {"ar": "تم", "en": "Done"},
    "not_understood": {"ar": "لم أفهم الأمر", "en": "Command not understood"},
    "no_window": {"ar": "لا توجد نافذة نشطة", "en": "No active window"},
    "app_not_found": {"ar": "لم أجد تطبيقاً باسم «{name}»", "en": "No app named “{name}”"},
    "unknown_action": {"ar": "إجراء غير معروف: {name}", "en": "Unknown action: {name}"},
    "action_failed": {"ar": "فشل التنفيذ", "en": "Action failed"},
    "paused": {"ar": "التحكم متوقف مؤقتاً", "en": "Control is paused"},
    "confirm_prompt": {"ar": "تأكيد «{heard}»؟ قل «نعم» أو «لا»", "en": "Confirm “{heard}”? Say “yes” or “no”"},
    "confirm_cancelled": {"ar": "تم الإلغاء", "en": "Cancelled"},
    "yes": {"ar": "نعم", "en": "Yes"},
    "no": {"ar": "لا", "en": "No"},
    # قائمة الشريط
    "menu_pause": {"ar": "إيقاف التحكم مؤقتاً", "en": "Pause control"},
    "menu_resume": {"ar": "استئناف التحكم", "en": "Resume control"},
    "menu_mute": {"ar": "كتم الميكروفون", "en": "Mute microphone"},
    "menu_continuous": {"ar": "استماع مستمر (بدون كلمة تنبيه)", "en": "Continuous listening (no wake word)"},
    "menu_cmd_lang": {"ar": "لغة الأوامر: {lang} (اضغط للتبديل)", "en": "Command language: {lang} (click to switch)"},
    "menu_camera": {"ar": "الكاميرا (التحكم بالإيماءات)", "en": "Camera (gesture control)"},
    "cam_loading": {"ar": "الكاميرا: جارٍ التشغيل…", "en": "Camera: starting…"},
    "cam_ready": {"ar": "الكاميرا: جاهزة (لا توجد يد)", "en": "Camera: ready (no hand)"},
    "cam_tracking": {"ar": "الكاميرا: اليد مرئية", "en": "Camera: hand visible"},
    "cam_off": {"ar": "الكاميرا: متوقفة", "en": "Camera: off"},
    "cam_error": {"ar": "الكاميرا: خطأ ({detail})", "en": "Camera: error ({detail})"},
    "cam_no_image": {"ar": "الكاميرا لا ترسل صورة: افتح غطاءها أو فعّلها، أو أغلق التطبيق الذي يستخدمها",
                     "en": "Camera sends no image: open its cover/enable it, or close the app using it"},
    "cam_slow": {"ar": "الكاميرا بطيئة ({fps} إطار/ث): أغلق التطبيقات الأخرى التي تستخدمها (المتصفح، الاجتماعات) أو حسّن الإضاءة",
                 "en": "Camera is slow ({fps} fps): close other apps using it (browser, meetings) or improve lighting"},
    "dict_on": {"ar": "🎤 الإملاء: تحدث وسيُكتب كلامك. قل «أوقف الإملاء» للخروج",
                "en": "🎤 Dictation: speak to type. Say “stop dictation” to exit"},
    "dict_loading": {"ar": "جارٍ تحميل نموذج الإملاء… (يمكنك البدء بالكلام)",
                     "en": "Loading dictation model… (you can start speaking)"},
    "dict_pending": {"ar": "جارٍ تحويل {count} جملة…", "en": "Transcribing {count} sentence(s)…"},
    "dict_off": {"ar": "انتهى الإملاء", "en": "Dictation ended"},
    "dict_error": {"ar": "خطأ في نموذج الإملاء: {detail}", "en": "Dictation model error: {detail}"},
    "grid_hint": {"ar": "قل رقماً (1-9)، ثم «انقر» · «رجوع» · «إلغاء»",
                  "en": "Say a number (1-9), then “click” · “back” · “cancel”"},
    # المعايرة
    "menu_calibrate": {"ar": "معايرة الإيماءات…", "en": "Calibrate gestures…"},
    "calib_title": {"ar": "معايرة الإيماءات", "en": "Gesture calibration"},
    "calib_step_open": {"ar": "✋ ارفع يدك مفتوحة أمام الكاميرا", "en": "✋ Raise your open hand in front of the camera"},
    "calib_step_pinch": {"ar": "🤏 المس طرف الإبهام بطرف السبابة وأبقهما متلامسين",
                         "en": "🤏 Touch your thumb tip to your index tip and hold"},
    "calib_step_point": {"ar": "☝️ مدّ السبابة وأبعد الإبهام عنها", "en": "☝️ Point with your index, thumb away"},
    "calib_step_zone": {"ar": "☝️ حرّك سبابتك ببطء إلى الزوايا الأربع للمنطقة المريحة لك",
                        "en": "☝️ Slowly move your index to the four corners of your comfortable area"},
    "calib_hand_ok": {"ar": "🟢 اليد مرئية", "en": "🟢 Hand visible"},
    "calib_hand_missing": {"ar": "🔴 لا أرى يدك: اقترب أو حسّن الإضاءة", "en": "🔴 Hand not visible: move closer or improve lighting"},
    "calib_done_ok": {"ar": "✓ انتهت المعايرة", "en": "✓ Calibration complete"},
    "calib_done_fail": {"ar": "✗ لم تنجح المعايرة. ستبقى الإعدادات الحالية", "en": "✗ Calibration failed. Current settings kept"},
    "calib_detection": {"ar": "ظهور اليد: {pct}%", "en": "Hand visibility: {pct}%"},
    "calib_pinch_ok": {"ar": "عتبة القرص: {enter} / {exit}", "en": "Pinch threshold: {enter} / {exit}"},
    "calib_zone_ok": {"ar": "منطقة التحكم: {w}% × {h}% من الصورة", "en": "Control zone: {w}% × {h}% of the image"},
    "calib_warn_hand_rarely_seen": {"ar": "⚠ اليد لم تظهر معظم الوقت (اقترب من الكاميرا)",
                                    "en": "⚠ Hand was often not visible (move closer)"},
    "calib_warn_too_dark": {"ar": "⚠ الإضاءة ضعيفة: أضف ضوءاً أمامك", "en": "⚠ Lighting is poor: add light in front of you"},
    "calib_warn_pinch_unclear": {"ar": "⚠ القرص غير واضح: بقيت العتبة السابقة", "en": "⚠ Pinch unclear: previous threshold kept"},
    "calib_warn_zone_small": {"ar": "⚠ الحركة صغيرة جداً: بقيت المنطقة السابقة", "en": "⚠ Movement too small: previous zone kept"},
    "calib_saving_in": {"ar": "الحفظ تلقائياً بعد {s} ث…", "en": "Saving automatically in {s}s…"},
    "calib_closing_in": {"ar": "الإغلاق بعد {s} ث…", "en": "Closing in {s}s…"},
    "calib_save": {"ar": "حفظ الآن", "en": "Save now"},
    "calib_cancel": {"ar": "إلغاء", "en": "Cancel"},
    "calib_saved": {"ar": "✓ حُفظت المعايرة. إعادة تشغيل الكاميرا…", "en": "✓ Calibration saved. Restarting camera…"},
    "calib_no_camera": {"ar": "المعايرة تحتاج كاميرا تعمل وترسل صورة", "en": "Calibration needs a working camera"},
    "gesture_done": {"ar": "إيماءة ← {action}", "en": "Gesture → {action}"},
    "menu_refresh_apps": {"ar": "إعادة فهرسة التطبيقات", "en": "Re-index applications"},
    "menu_open_folder": {"ar": "فتح مجلد الإعدادات", "en": "Open settings folder"},
    "menu_quit": {"ar": "خروج", "en": "Quit"},
    "hotkey_hint": {"ar": "اختصار الإيقاف: {hotkey}", "en": "Stop hotkey: {hotkey}"},
    "already_running": {"ar": "التطبيق يعمل بالفعل.", "en": "The application is already running."},
}


class Tr:
    def __init__(self, lang: str = "ar"):
        self.lang = lang

    @property
    def rtl(self) -> bool:
        return self.lang == "ar"

    def __call__(self, key: str, **values) -> str:
        entry = STRINGS.get(key)
        text = entry.get(self.lang) or entry.get("en") if entry else key
        try:
            return text.format(**values)
        except (KeyError, IndexError):
            return text


# ============================ نافذة الإعدادات ============================
STRINGS.update({
    "menu_settings": {"ar": "الإعدادات…", "en": "Settings…"},
    "set_title": {"ar": "إعدادات التحكم بدون لمس", "en": "No-Touch settings"},
    "tab_general": {"ar": "عام", "en": "General"},
    "tab_speech": {"ar": "الصوت والإملاء", "en": "Speech & dictation"},
    "tab_camera": {"ar": "الكاميرا", "en": "Camera"},
    "tab_gestures": {"ar": "الإيماءات", "en": "Gestures"},
    "tab_safety": {"ar": "الأمان", "en": "Safety"},
    "set_ui_language": {"ar": "لغة الواجهة", "en": "Interface language"},
    "set_cmd_language": {"ar": "لغة الأوامر الصوتية", "en": "Voice command language"},
    "set_wake_ar": {"ar": "كلمة التنبيه (عربي)", "en": "Wake word (Arabic)"},
    "set_wake_en": {"ar": "كلمة التنبيه (إنجليزي)", "en": "Wake word (English)"},
    "set_continuous": {"ar": "استماع مستمر (بدون كلمة تنبيه)", "en": "Continuous listening (no wake word)"},
    "set_sounds": {"ar": "أصوات التأكيد", "en": "Feedback sounds"},
    "set_overlay": {"ar": "إظهار شريط الحالة", "en": "Show status bar"},
    "set_overlay_seconds": {"ar": "مدة ظهور الشريط (ثوانٍ)", "en": "Status bar duration (s)"},
    "set_font_scale": {"ar": "حجم الخط", "en": "Font size"},
    "set_high_contrast": {"ar": "تباين عالٍ", "en": "High contrast"},
    "set_mic": {"ar": "الميكروفون", "en": "Microphone"},
    "set_default_device": {"ar": "الافتراضي", "en": "Default"},
    "set_vad": {"ar": "تجاهل الضوضاء (0-3)", "en": "Noise rejection (0-3)"},
    "set_threshold": {"ar": "دقة مطابقة الأوامر (50-100)", "en": "Command match strictness (50-100)"},
    "set_followup": {"ar": "مهلة الأوامر المتتالية (ثوانٍ)", "en": "Follow-up window (s)"},
    "set_dict_engine": {"ar": "محرك الإملاء", "en": "Dictation engine"},
    "set_dict_model": {"ar": "نموذج Whisper", "en": "Whisper model"},
    "engine_whisper": {"ar": "Whisper (أدق، أبطأ)", "en": "Whisper (accurate, slower)"},
    "engine_vosk": {"ar": "Vosk (فوري، أقل دقة)", "en": "Vosk (instant, less accurate)"},
    "set_cam_enabled": {"ar": "تفعيل التحكم بالإيماءات", "en": "Enable gesture control"},
    "set_cam_index": {"ar": "رقم الكاميرا", "en": "Camera number"},
    "set_preview": {"ar": "نافذة معاينة الكاميرا", "en": "Camera preview window"},
    "set_hand": {"ar": "اليد المتحكمة", "en": "Controlling hand"},
    "hand_any": {"ar": "أي يد", "en": "Any"},
    "hand_right": {"ar": "اليمنى", "en": "Right"},
    "hand_left": {"ar": "اليسرى", "en": "Left"},
    "set_smooth": {"ar": "ثبات المؤشر (أقل = أثبت)", "en": "Pointer steadiness (lower = steadier)"},
    "set_speed": {"ar": "استجابة الحركة السريعة", "en": "Fast-motion response"},
    "set_zone": {"ar": "منطقة التحكم (يسار، أعلى، يمين، أسفل)", "en": "Control zone (left, top, right, bottom)"},
    "set_pinch": {"ar": "عتبة القرص (بدء / انتهاء)", "en": "Pinch threshold (start / end)"},
    "set_scroll_invert": {"ar": "عكس اتجاه التمرير", "en": "Invert scroll direction"},
    "set_calibrate": {"ar": "معايرة تلقائية…", "en": "Auto-calibrate…"},
    "set_hotkey": {"ar": "اختصار الإيقاف الطارئ", "en": "Emergency stop hotkey"},
    "set_confirm": {"ar": "تأكيد قبل الإجراءات الخطرة", "en": "Confirm dangerous actions"},
    "set_confirm_timeout": {"ar": "مهلة التأكيد (ثوانٍ)", "en": "Confirmation timeout (s)"},
    "set_save": {"ar": "حفظ وتطبيق", "en": "Save & apply"},
    "set_cancel": {"ar": "إلغاء", "en": "Cancel"},
    "set_open_folder": {"ar": "فتح مجلد الإعدادات", "en": "Open settings folder"},
    "set_saved": {"ar": "✓ حُفظت الإعدادات", "en": "✓ Settings saved"},
    "set_restart_needed": {"ar": "✓ حُفظت. اللغة والخط والتباين تُطبَّق عند إعادة تشغيل التطبيق",
                           "en": "✓ Saved. Language, font and contrast apply after restarting the app"},
    # الإيماءات
    "g_pinch_tap": {"ar": "🤏 قرص الإبهام والسبابة", "en": "🤏 Thumb–index pinch"},
    "g_middle_pinch_tap": {"ar": "قرص الإبهام والوسطى", "en": "Thumb–middle pinch"},
    "g_fist_hold": {"ar": "✊ قبضة", "en": "✊ Fist"},
    "g_palm_hold_long": {"ar": "✋ كف مفتوح ثانيتين", "en": "✋ Open palm 2 s"},
    "g_two_scroll": {"ar": "✌️ إصبعان + تحريك", "en": "✌️ Two fingers + move"},
    "g_swipe_right": {"ar": "✋ سحب لليمين", "en": "✋ Swipe right"},
    "g_swipe_left": {"ar": "✋ سحب لليسار", "en": "✋ Swipe left"},
    "g_zoom_in": {"ar": "🤏🤏 إبعاد اليدين", "en": "🤏🤏 Hands apart"},
    "g_zoom_out": {"ar": "🤏🤏 تقريب اليدين", "en": "🤏🤏 Hands together"},
    # الإجراءات
    "act_none": {"ar": "— معطّل —", "en": "— disabled —"},
    "act_click": {"ar": "نقرة", "en": "Click"},
    "act_double_click": {"ar": "نقرة مزدوجة", "en": "Double click"},
    "act_right_click": {"ar": "نقرة يمنى", "en": "Right click"},
    "act_middle_click": {"ar": "نقرة وسطى", "en": "Middle click"},
    "act_scroll": {"ar": "تمرير", "en": "Scroll"},
    "act_zoom_in": {"ar": "تكبير", "en": "Zoom in"},
    "act_zoom_out": {"ar": "تصغير", "en": "Zoom out"},
    "act_switch_window": {"ar": "النافذة التالية", "en": "Next window"},
    "act_switch_window_prev": {"ar": "النافذة السابقة", "en": "Previous window"},
    "act_show_desktop": {"ar": "سطح المكتب", "en": "Show desktop"},
    "act_minimize_window": {"ar": "تصغير النافذة", "en": "Minimize window"},
    "act_maximize_window": {"ar": "تكبير النافذة", "en": "Maximize window"},
    "act_app.pause": {"ar": "إيقاف مؤقت للتحكم", "en": "Pause control"},
    "act_app.show_grid": {"ar": "الشبكة الصوتية", "en": "Voice grid"},
    "act_app.start_dictation": {"ar": "بدء الإملاء", "en": "Start dictation"},
    "act_screenshot": {"ar": "لقطة شاشة", "en": "Screenshot"},
    "act_volume_up": {"ar": "رفع الصوت", "en": "Volume up"},
    "act_volume_down": {"ar": "خفض الصوت", "en": "Volume down"},
    "act_mute": {"ar": "كتم الصوت", "en": "Mute"},
    "act_media_play_pause": {"ar": "تشغيل/إيقاف الوسائط", "en": "Play/Pause media"},
    "act_snap_left": {"ar": "محاذاة النافذة لليسار", "en": "Snap window left"},
    "act_snap_right": {"ar": "محاذاة النافذة لليمين", "en": "Snap window right"},
    "act_task_view": {"ar": "عروض المهام (Task View)", "en": "Task View"},
    "act_open_explorer": {"ar": "مستكشف الملفات", "en": "File Explorer"},
    "act_open_task_manager": {"ar": "مدير المهام", "en": "Task Manager"},
})


# ============================ لوحة التحكم ============================
STRINGS.update({
    "menu_panel": {"ar": "لوحة التحكم", "en": "Control panel"},
    "panel_pause": {"ar": "⏸ إيقاف مؤقت", "en": "⏸ Pause"},
    "panel_resume": {"ar": "▶ استئناف", "en": "▶ Resume"},
    "panel_dictation": {"ar": "🎤 ابدأ الإملاء", "en": "🎤 Start dictation"},
    "panel_dictation_stop": {"ar": "⏹ أوقف الإملاء", "en": "⏹ Stop dictation"},
    "panel_grid": {"ar": "▦ الشبكة", "en": "▦ Grid"},
    "panel_calibrate": {"ar": "✋ معايرة", "en": "✋ Calibrate"},
    "panel_settings": {"ar": "⚙ الإعدادات", "en": "⚙ Settings"},
    "panel_quit": {"ar": "✕ خروج", "en": "✕ Quit"},
    "panel_heard": {"ar": "آخر ما سُمع:", "en": "Last heard:"},
    "panel_hide": {"ar": "إخفاء اللوحة (التطبيق يبقى يعمل)", "en": "Hide the panel (app keeps running)"},
    "panel_hint": {"ar": "إغلاق هذه النافذة لا يوقف التطبيق: يبقى يعمل من أيقونة الميكروفون بجانب الساعة "
                         "(قد تكون خلف السهم ^). انقر الأيقونة مرتين لإعادة فتحها.",
                   "en": "Closing this window does not stop the app: it keeps running from the microphone icon "
                         "near the clock (maybe behind the ^ arrow). Double-click the icon to reopen it."},
    "panel_still_running": {"ar": "التطبيق ما زال يعمل من شريط النظام", "en": "The app is still running in the tray"},
})


# ============================ الفرنسية ============================
STRINGS.update({
    "set_wake_fr": {"ar": "كلمة التنبيه (فرنسي)", "en": "Wake word (French)"},
    # أسماء اللغات تُكتب بلغتها الأصلية في كل الواجهات
    "lang_ar": {"ar": "العربية", "en": "العربية"},
    "lang_en": {"ar": "English", "en": "English"},
    "lang_fr": {"ar": "Français", "en": "Français"},
})
from ui.i18n_fr import FR as _FR  # noqa: E402

for _k, _v in _FR.items():
    STRINGS.setdefault(_k, {})["fr"] = _v
