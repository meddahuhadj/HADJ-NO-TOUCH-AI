import re
from typing import Optional, List
from intents.intent_definitions import IntentType, IntentResult


class IntentRecognizer:
    """Parses natural language commands in Arabic, French, and English into structured Intents."""

    def __init__(self):
        # Compound command splitters
        self.compound_delimiters = [
            r'\s+ثم\s+',
            r'\s+then\s+',
            r'\s+et\s+ensuite\s+',
            r'\s+puis\s+',
            r'\s+and\s+then\s+',
        ]

    def parse(self, text: str) -> IntentResult:
        """Parses full command text into an IntentResult (single or compound plan)."""
        clean = text.strip()
        if not clean:
            return IntentResult(IntentType.UNKNOWN, confidence=0.0, original_text=text)

        # 1. Check Compound Commands
        for delim in self.compound_delimiters:
            parts = re.split(delim, clean, flags=re.IGNORECASE)
            if len(parts) > 1:
                sub_results = [self._parse_single(p.strip()) for p in parts if p.strip()]
                return IntentResult(
                    intent_type=IntentType.COMPOUND_PLAN,
                    sub_intents=sub_results,
                    confidence=0.92,
                    original_text=clean
                )

        return self._parse_single(clean)

    def _parse_single(self, text: str) -> IntentResult:
        lower = text.lower().strip()

        # ==========================================
        # MULTIMODAL POINT & ACT COMMANDS
        # ==========================================
        if re.search(r'^(اضغط\s+هنا|انقر\s+هنا|click\s+here|clique\s+ici)$', lower):
            return IntentResult(IntentType.MULTIMODAL_CLICK_TARGET, confidence=0.98, original_text=text)

        if re.search(r'^(افتحه|افتح\s+هذا|open\s+this|ouvre\s+ceci|ouvre\s+ça)$', lower):
            return IntentResult(IntentType.MULTIMODAL_OPEN_TARGET, confidence=0.98, original_text=text)

        # ==========================================
        # VISION / SCREEN UNDERSTANDING
        # ==========================================
        if re.search(r'(اين\s+زر\s+الإغلاق|أين\s+زر\s+الاغلاق|أين\s+زر\s+الإغلاق|where\s+is\s+close\s+button|ou\s+est\s+le\s+bouton\s+fermer)', lower):
            return IntentResult(IntentType.FIND_ELEMENT, target="close_button", confidence=0.95, original_text=text)

        # ==========================================
        # CLIPBOARD & EDITING
        # ==========================================
        if re.search(r'^(انسخ|copy|copier)$', lower):
            return IntentResult(IntentType.CLIPBOARD_COPY, confidence=0.98, original_text=text)

        if re.search(r'^(الصق|paste|coller)$', lower):
            return IntentResult(IntentType.CLIPBOARD_PASTE, confidence=0.98, original_text=text)

        if re.search(r'^(قص|cut|couper)$', lower):
            return IntentResult(IntentType.CLIPBOARD_CUT, confidence=0.98, original_text=text)

        if re.search(r'^(حدد\s+الكل|select\s+all|tout\s+sélectionner|tout\s+selectionner)$', lower):
            return IntentResult(IntentType.SELECT_ALL, confidence=0.98, original_text=text)

        if re.search(r'^(تراجع|undo|annuler)$', lower):
            return IntentResult(IntentType.UNDO, confidence=0.98, original_text=text)

        # ==========================================
        # WINDOW CONTROLS
        # ==========================================
        if re.search(r'(اغلق\s+النافذة|أغلق\s+النافذة|close\s+window|ferme\s+la\s+fen[eê]tre)', lower):
            return IntentResult(IntentType.CLOSE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(صغر\s+النافذة|صغّر\s+النافذة|minimize\s+window|minimis(?:er|ée)?\s+la\s+fen[eê]tre|réduire\s+la\s+fen[eê]tre)', lower):
            return IntentResult(IntentType.MINIMIZE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(كبر\s+النافذة|كبّر\s+النافذة|maximize\s+window|agrandir\s+la\s+fen[eê]tre)', lower):
            return IntentResult(IntentType.MAXIMIZE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(بدل\s+التطبيق|بدّل\s+التطبيق|بدل\s+النافذة|switch\s+app|changer\s+d\'application|alt\s+tab)', lower):
            return IntentResult(IntentType.SWITCH_APP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب|show\s+desktop|afficher\s+le\s+bureau)', lower):
            return IntentResult(IntentType.SHOW_DESKTOP, confidence=0.96, original_text=text)

        # Window Snapping
        if re.search(r'(قسم\s+الشاشة\s+لليمين|محاذاة\s+لليمين|snap\s+right|ancrer\s+à\s+droite)', lower):
            return IntentResult(IntentType.SNAP_WINDOW_RIGHT, confidence=0.96, original_text=text)

        if re.search(r'(قسم\s+الشاشة\s+لليسار|محاذاة\s+لليسار|snap\s+left|ancrer\s+à\s+gauche)', lower):
            return IntentResult(IntentType.SNAP_WINDOW_LEFT, confidence=0.96, original_text=text)

        # Virtual Desktops & Task View
        if re.search(r'(عرض\s+المهام|task\s+view|vue\s+des\s+t[aâ]ches)', lower):
            return IntentResult(IntentType.TASK_VIEW, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+مكتب\s+جديد|new\s+desktop|nouveau\s+bureau)', lower):
            return IntentResult(IntentType.NEW_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(اغلق\s+سطح\s+المكتب|أغلق\s+سطح\s+المكتب|close\s+desktop|fermer\s+le\s+bureau)', lower):
            return IntentResult(IntentType.CLOSE_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب\s+التالي|next\s+desktop|bureau\s+suivant)', lower):
            return IntentResult(IntentType.NEXT_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب\s+السابق|prev(?:ious)?\s+desktop|bureau\s+pr[eé]c[eé]dent)', lower):
            return IntentResult(IntentType.PREV_DESKTOP, confidence=0.96, original_text=text)

        # Task Manager & Recycle Bin
        if re.search(r'(مدير\s+المهام|task\s+manager|gestionnaire\s+des\s+t[aâ]ches)', lower):
            return IntentResult(IntentType.OPEN_TASK_MANAGER, confidence=0.96, original_text=text)

        if re.search(r'(افرغ\s+سلة\s+المحذوفات|أفرغ\s+سلة\s+المحذوفات|empty\s+recycle\s+bin|vider\s+la\s+corbeille)', lower):
            return IntentResult(IntentType.EMPTY_RECYCLE_BIN, confidence=0.97, original_text=text)

        # Zoom Controls
        if re.search(r'(تكبير\s+الشاشة|zoom\s+in|agrandir\s+le\s+zoom)', lower):
            return IntentResult(IntentType.ZOOM_IN, confidence=0.96, original_text=text)

        if re.search(r'(تصغير\s+الشاشة|zoom\s+out|diminuer\s+le\s+zoom)', lower):
            return IntentResult(IntentType.ZOOM_OUT, confidence=0.96, original_text=text)

        if re.search(r'(إعادة\s+ضبط\s+الزووم|اعادة\s+ضبط\s+الزووم|reset\s+zoom)', lower):
            return IntentResult(IntentType.ZOOM_RESET, confidence=0.96, original_text=text)

        # Virtual Keyboard Toggle
        if re.search(r'(لوحة\s+المفاتيح|virtual\s+keyboard|clavier\s+virtuel)', lower):
            return IntentResult(IntentType.TOGGLE_KEYBOARD_HUD, confidence=0.96, original_text=text)

        # Screen Refresh
        if re.search(r'(تحديث\s+الشاشة|تحديث|refresh|actualiser)', lower):
            return IntentResult(IntentType.REFRESH_SCREEN, confidence=0.95, original_text=text)

        # ==========================================
        # VOLUME & MEDIA
        # ==========================================
        if re.search(r'(ارفع\s+الصوت|علي\s+الصوت|volume\s+up|monte\s+le\s+son|augmenter\s+le\s+volume)', lower):
            return IntentResult(IntentType.VOLUME_UP, confidence=0.97, original_text=text)

        if re.search(r'(اخفض\s+الصوت|وطي\s+الصوت|volume\s+down|baisse\s+le\s+son|diminuer\s+le\s+volume)', lower):
            return IntentResult(IntentType.VOLUME_DOWN, confidence=0.97, original_text=text)

        if re.search(r'(اكتم\s+الصوت|mute|muet|couper\s+le\s+son)', lower):
            return IntentResult(IntentType.VOLUME_MUTE, confidence=0.97, original_text=text)

        if re.search(r'(شغل\s+الموسيقى|شغّل\s+الموسيقى|اوقف\s+الموسيقى|أوقف\s+الموسيقى|play\s+music|pause\s+music|lecture|pause)', lower):
            return IntentResult(IntentType.MEDIA_PLAY_PAUSE, confidence=0.96, original_text=text)

        if re.search(r'(التالي|next\s+track|musique\s+suivante|suivant)', lower):
            return IntentResult(IntentType.MEDIA_NEXT, confidence=0.95, original_text=text)

        if re.search(r'(السابق|previous\s+track|musique\s+précédente|precedent)', lower):
            return IntentResult(IntentType.MEDIA_PREVIOUS, confidence=0.95, original_text=text)

        # ==========================================
        # BRIGHTNESS & SCREENSHOT
        # ==========================================
        if re.search(r'(ارفع\s+السطوع|زيادة\s+السطوع|brightness\s+up|augmenter\s+luminosité)', lower):
            return IntentResult(IntentType.BRIGHTNESS_UP, confidence=0.96, original_text=text)

        if re.search(r'(اخفض\s+السطوع|تقليل\s+السطوع|brightness\s+down|baisser\s+luminosité)', lower):
            return IntentResult(IntentType.BRIGHTNESS_DOWN, confidence=0.96, original_text=text)

        if re.search(r'(التقط\s+صورة\s+للشاشة|لقطة\s+شاشة|screenshot|capture\s+d\'[eé]cran)', lower):
            return IntentResult(IntentType.SCREENSHOT, confidence=0.98, original_text=text)

        # ==========================================
        # SCROLLING
        # ==========================================
        if re.search(r'(مرر\s+للأعلى|مرر\s+للاعلى|انزل\s+لفوق|scroll\s+up|défiler\s+vers\s+le\s+haut)', lower):
            return IntentResult(IntentType.SCROLL_UP, confidence=0.96, original_text=text)

        if re.search(r'(مرر\s+للأسفل|مرر\s+للاسفل|انزل\s+لتحت|scroll\s+down|défiler\s+vers\s+le\s+bas)', lower):
            return IntentResult(IntentType.SCROLL_DOWN, confidence=0.96, original_text=text)

        # ==========================================
        # BROWSER SPECIFICS
        # ==========================================
        if re.search(r'(تبويب\s+جديد|افتح\s+تبويب\s+جديد|new\s+tab|nouvel\s+onglet)', lower):
            return IntentResult(IntentType.BROWSER_NEW_TAB, confidence=0.97, original_text=text)

        if re.search(r'(اغلق\s+التبويب|أغلق\s+التبويب|close\s+tab|fermer\s+l\'onglet)', lower):
            return IntentResult(IntentType.BROWSER_CLOSE_TAB, confidence=0.97, original_text=text)

        if re.search(r'(التبويب\s+التالي|next\s+tab|onglet\s+suivant)', lower):
            return IntentResult(IntentType.BROWSER_NEXT_TAB, confidence=0.97, original_text=text)

        if re.search(r'^(ارجع|go\s+back|retour|retourner)$', lower):
            return IntentResult(IntentType.NAVIGATE_BACK, confidence=0.96, original_text=text)

        if re.search(r'^(إلى\s+الأمام|الى\s+الامام|forward|avancer)$', lower):
            return IntentResult(IntentType.NAVIGATE_FORWARD, confidence=0.96, original_text=text)

        # Browser search: "ابحث عن ..." / "search for ..."
        search_match = re.match(r'(?:ابحث\s+عن|ابحث\s+في\s+المتصفح\s+عن|search\s+for|cherche)\s+(.*)', lower)
        if search_match:
            query = search_match.group(1).strip()
            return IntentResult(IntentType.BROWSER_SEARCH, target=query, confidence=0.95, original_text=text)

        # ==========================================
        # POWER & SYSTEM LOCK
        # ==========================================
        if re.search(r'(اقفل\s+الكمبيوتر|قفل\s+الشاشة|lock\s+computer|verrouiller)', lower):
            return IntentResult(IntentType.SYSTEM_LOCK, confidence=0.98, original_text=text)

        if re.search(r'(اعد\s+تشغيل\s+الكمبيوتر|أعد\s+تشغيل\s+الكمبيوتر|restart\s+computer|redémarrer)', lower):
            return IntentResult(IntentType.SYSTEM_RESTART, confidence=0.98, original_text=text)

        if re.search(r'(اوقف\s+تشغيل\s+الكمبيوتر|أوقف\s+تشغيل\s+الكمبيوتر|shutdown\s+computer|[eé]teindre)', lower):
            return IntentResult(IntentType.SYSTEM_SHUTDOWN, confidence=0.98, original_text=text)

        # ==========================================
        # FOLDERS & FILES
        # ==========================================
        folder_match = re.match(r'(?:افتح\s+مجلد|افتح\s+دليل|open\s+folder|ouvre\s+le\s+dossier)\s+(.*)', lower)
        if folder_match:
            target_folder = folder_match.group(1).strip()
            return IntentResult(IntentType.OPEN_FOLDER, target=target_folder, confidence=0.96, original_text=text)

        if re.search(r'(افتح\s+التحميلات|افتح\s+التنزيلات|افتح\s+downloads|open\s+downloads|ouvre\s+les\s+t[eé]l[eé]chargements)', lower):
            return IntentResult(IntentType.OPEN_FOLDER, target="downloads", confidence=0.98, original_text=text)

        if re.search(r'(افتح\s+ملفاتي|افتح\s+المستندات|open\s+documents|open\s+my\s+documents|mes\s+documents)', lower):
            return IntentResult(IntentType.OPEN_FOLDER, target="documents", confidence=0.98, original_text=text)

        if re.search(r'(الملف\s+الاخير|الملف\s+الأخير|latest\s+download|dernier\s+fichier)', lower):
            return IntentResult(IntentType.OPEN_RECENT_FILE, confidence=0.95, original_text=text)

        # The name is optional and, in the common "create folder invoices" form,
        # is simply whatever follows the verb. Previously only an explicit
        # "named X" was captured, so every other phrasing silently created a
        # directory called "New Folder".
        create_dir_match = re.match(
            r'(?:انشئ\s+مجلدا\s+جديدا|أنشئ\s+مجلداً\s+جديداً|أنشئ\s+مجلد|create\s+(?:a\s+)?folder|cr[eé]er\s+un\s+dossier)'
            r'(?:\s+(?:اسمه|سمه|named|appel[eé]e))?'
            r'(?:\s+(.+))?$',
            lower
        )
        if create_dir_match:
            name = (create_dir_match.group(1) or "").strip()
            return IntentResult(
                IntentType.CREATE_FOLDER,
                target=name or "New Folder",
                confidence=0.94,
                original_text=text
            )

        delete_file_match = re.match(
            r'(?:احذف\s+هذا\s+الملف|احذف\s+الملف|delete\s+file|supprime\s+le\s+fichier)'
            r'(?:\s+(.+))?$',
            lower
        )
        if delete_file_match:
            # Without a named target the orchestrator has nothing safe to act
            # on, so the target stays None and the action is refused rather
            # than guessed at.
            return IntentResult(
                IntentType.DELETE_FILE,
                target=(delete_file_match.group(1) or "").strip() or None,
                confidence=0.95,
                original_text=text
            )

        # ==========================================
        # APPLICATION LAUNCH / CLOSE
        # ==========================================
        open_app_match = re.match(r'(?:افتح|شغل|شغّل|open|launch|start|lance|ouvre)\s+(.*)', lower)
        if open_app_match:
            app_target = open_app_match.group(1).strip()
            return IntentResult(IntentType.LAUNCH_APP, target=app_target, confidence=0.95, original_text=text)

        close_app_match = re.match(r'(?:اغلق|أغلق|close|quitter|ferme)\s+(.*)', lower)
        if close_app_match:
            app_target = close_app_match.group(1).strip()
            return IntentResult(IntentType.LAUNCH_APP, target=app_target, parameters={"action": "close"}, confidence=0.94, original_text=text)

        # ==========================================
        # MACROS
        # ==========================================
        if "morning setup" in lower:
            return IntentResult(IntentType.EXECUTE_MACRO, target="Morning Setup", confidence=0.98, original_text=text)
        if "coding setup" in lower:
            return IntentResult(IntentType.EXECUTE_MACRO, target="Coding Setup", confidence=0.98, original_text=text)

        return IntentResult(IntentType.UNKNOWN, confidence=0.2, original_text=text)
