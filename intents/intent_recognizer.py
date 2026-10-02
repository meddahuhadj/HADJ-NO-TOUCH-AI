import re
from typing import Optional, List, Tuple
from intents.intent_definitions import IntentType, IntentResult


def normalize_arabic(text: str) -> str:
    """
    Normalizes Arabic orthographic and dialectal variations:
    - Strips tashkeel (diacritics: fatha, damma, kasra, sukun, shadda, tanween)
    - Strips tatweel (ـ)
    - Normalizes alif forms (أ, إ, آ, ٱ -> ا)
    - Normalizes ta marbuta (ة -> ه)
    - Normalizes alif maqsura (ى -> ي)
    - Normalizes common dialect prefixes/suffixes
    """
    if not text:
        return ""
    # Strip Tashkeel & Tatweel
    tashkeel = re.compile(r'[\u0617-\u061A\u064B-\u0652\u0670\u0640]')
    t = tashkeel.sub('', text)
    # Normalize Alifs
    t = re.sub(r'[إأآٱ]', 'ا', t)
    # Normalize Taa Marbuta
    t = re.sub(r'ة', 'ه', t)
    # Normalize Alif Maqsura
    t = re.sub(r'ى', 'ي', t)
    # Normalize multiple spaces
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


class IntentRecognizer:
    """
    Parses natural language commands in Arabic (Fusha, Darija/Maghrebi, Egyptian, Gulf/Levantine),
    French, and English into structured Intents with phonetic normalization and fuzzy noise tolerance.
    """

    def __init__(self):
        # Compound command splitters
        self.compound_delimiters = [
            r'\s+ثم\s+',
            r'\s+ومن\s+بعد\s+',
            r'\s+وبعدين\s+',
            r'\s+then\s+',
            r'\s+et\s+ensuite\s+',
            r'\s+puis\s+',
            r'\s+and\s+then\s+',
        ]

        # Canonical commands for fuzzy matching when regex does not match
        self.canonical_commands: List[Tuple[str, IntentType, Optional[str]]] = [
            ("التقط صوره للشاشه", IntentType.SCREENSHOT, None),
            ("دير لقطه شاشه", IntentType.SCREENSHOT, None),
            ("لقطه شاشه", IntentType.SCREENSHOT, None),
            ("صور الشاشه", IntentType.SCREENSHOT, None),
            ("ارفع الصوت", IntentType.VOLUME_UP, None),
            ("زيد الصوت", IntentType.VOLUME_UP, None),
            ("علي الصوت", IntentType.VOLUME_UP, None),
            ("اخفض الصوت", IntentType.VOLUME_DOWN, None),
            ("نقص الصوت", IntentType.VOLUME_DOWN, None),
            ("وطي الصوت", IntentType.VOLUME_DOWN, None),
            ("اكتم الصوت", IntentType.VOLUME_MUTE, None),
            ("اغلق النافذه", IntentType.CLOSE_WINDOW, None),
            ("بلع النافذه", IntentType.CLOSE_WINDOW, None),
            ("سد النافذه", IntentType.CLOSE_WINDOW, None),
            ("صك النافذه", IntentType.CLOSE_WINDOW, None),
            ("صغر النافذه", IntentType.MINIMIZE_WINDOW, None),
            ("كبر النافذه", IntentType.MAXIMIZE_WINDOW, None),
            ("سطح المكتب", IntentType.SHOW_DESKTOP, None),
            ("لوحه المفاتيح", IntentType.TOGGLE_KEYBOARD_HUD, None),
            ("مدير المهام", IntentType.OPEN_TASK_MANAGER, None),
            ("افرغ سله المحذوفات", IntentType.EMPTY_RECYCLE_BIN, None),
            ("قفل الشاشه", IntentType.SYSTEM_LOCK, None),
            ("مرر للاعلي", IntentType.SCROLL_UP, None),
            ("مرر للاسفل", IntentType.SCROLL_DOWN, None),
            ("تبويب جديد", IntentType.BROWSER_NEW_TAB, None),
            ("اغلق التبويب", IntentType.BROWSER_CLOSE_TAB, None),
            ("تراجع", IntentType.UNDO, None),
            ("انسخ", IntentType.CLIPBOARD_COPY, None),
            ("الصق", IntentType.CLIPBOARD_PASTE, None),
            ("حدد الكل", IntentType.SELECT_ALL, None),
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
        raw_lower = text.lower().strip()
        norm_ar = normalize_arabic(text).lower().strip()

        # ==========================================
        # MULTIMODAL POINT & ACT COMMANDS
        # ==========================================
        if re.search(r'^(اضغط\s+هنا|انقر\s+هنا|كليكي\s+هنا|click\s+here|clique\s+ici)$', norm_ar):
            return IntentResult(IntentType.MULTIMODAL_CLICK_TARGET, confidence=0.98, original_text=text)

        if re.search(r'^(افتحه|افتح\s+هذا|حله|حل\s+هذا|فكه|فك\s+هذا|open\s+this|ouvre\s+ceci|ouvre\s+ça)$', norm_ar):
            return IntentResult(IntentType.MULTIMODAL_OPEN_TARGET, confidence=0.98, original_text=text)

        # ==========================================
        # VISION / SCREEN UNDERSTANDING
        # ==========================================
        if re.search(r'(اين|وين|فاين|فين)\s+زر\s+(الاغلاق|التسكير|القفل|البلع|الصد|الفيرميتور)|where\s+is\s+close\s+button|ou\s+est\s+le\s+bouton\s+fermer', norm_ar):
            return IntentResult(IntentType.FIND_ELEMENT, target="close_button", confidence=0.95, original_text=text)

        # ==========================================
        # CLIPBOARD & EDITING
        # ==========================================
        if re.search(r'^(انسخ|كوبي|copy|copier)$', norm_ar):
            return IntentResult(IntentType.CLIPBOARD_COPY, confidence=0.98, original_text=text)

        if re.search(r'^(الصق|كولي|paste|coller)$', norm_ar):
            return IntentResult(IntentType.CLIPBOARD_PASTE, confidence=0.98, original_text=text)

        if re.search(r'^(قص|كوبي\s+كولي|cut|couper)$', norm_ar):
            return IntentResult(IntentType.CLIPBOARD_CUT, confidence=0.98, original_text=text)

        if re.search(r'^(حدد\s+الكل|سيلكسيوني\s+كلش|select\s+all|tout\s+sélectionner|tout\s+selectionner)$', norm_ar):
            return IntentResult(IntentType.SELECT_ALL, confidence=0.98, original_text=text)

        if re.search(r'^(تراجع|رجع|اون\s+دو|undo|annuler)$', norm_ar):
            return IntentResult(IntentType.UNDO, confidence=0.98, original_text=text)

        # ==========================================
        # WINDOW CONTROLS (Fusha + Darija + Egyptian + Gulf)
        # ==========================================
        if re.search(r'(اغلق|اقفل|بلع|سد|صك|سكر|فيرمي|قفل)\s+(النافذه|النافذة|الفنتر|الشباك)|close\s+window|ferme\s+la\s+fen[eê]tre', norm_ar):
            return IntentResult(IntentType.CLOSE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(صغر|صغّر|هبط|نزل|قلل|مينيمايز)\s+(النافذه|النافذة)|minimize\s+window|minimis(?:er|ée)?\s+la\s+fen[eê]tre|réduire\s+la\s+fen[eê]tre', norm_ar):
            return IntentResult(IntentType.MINIMIZE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(كبر|كبّر|طلع|ماكسيمايز)\s+(النافذه|النافذة)|maximize\s+window|agrandir\s+la\s+fen[eê]tre', norm_ar):
            return IntentResult(IntentType.MAXIMIZE_WINDOW, confidence=0.97, original_text=text)

        if re.search(r'(بدل|بدّل|قلب|غير|سويتش)\s+(التطبيق|البرنامج|النافذه|النافذة)|switch\s+app|changer\s+d\'application|alt\s+tab', norm_ar):
            return IntentResult(IntentType.SWITCH_APP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب|البيرو|الديسكتوب|شاو\s+ديسكتوب|show\s+desktop|afficher\s+le\s+bureau)', norm_ar):
            return IntentResult(IntentType.SHOW_DESKTOP, confidence=0.96, original_text=text)

        # Window Snapping
        if re.search(r'(قسم\s+الشاشه\s+لليمين|محاذاه\s+لليمين|دير\s+لليمن|حط\s+عاليمين|snap\s+right|ancrer\s+à\s+droite|ancrer\s+a\s+droite)', norm_ar):
            return IntentResult(IntentType.SNAP_WINDOW_RIGHT, confidence=0.96, original_text=text)

        if re.search(r'(قسم\s+الشاشه\s+لليسار|محاذاه\s+لليسار|دير\s+لليسر|حط\s+عاليسار|snap\s+left|ancrer\s+à\s+gauche|ancrer\s+a\s+gauche)', norm_ar):
            return IntentResult(IntentType.SNAP_WINDOW_LEFT, confidence=0.96, original_text=text)

        # Virtual Desktops & Task View
        if re.search(r'(عرض\s+المهام|task\s+view|vue\s+des\s+t[aâ]ches)', norm_ar):
            return IntentResult(IntentType.TASK_VIEW, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+مكتب\s+جديد|بيرو\s+جديد|new\s+desktop|nouveau\s+bureau)', norm_ar):
            return IntentResult(IntentType.NEW_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(اغلق\s+سطح\s+المكتب|بلع\s+البيرو|سد\s+البيرو|صك\s+سطح\s+المكتب|close\s+desktop|fermer\s+le\s+bureau)', norm_ar):
            return IntentResult(IntentType.CLOSE_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب\s+التالي|البيرو\s+الجاي|next\s+desktop|bureau\s+suivant)', norm_ar):
            return IntentResult(IntentType.NEXT_DESKTOP, confidence=0.96, original_text=text)

        if re.search(r'(سطح\s+المكتب\s+السابق|البيرو\s+اللي\s+فات|prev(?:ious)?\s+desktop|bureau\s+pr[eé]c[eé]dent)', norm_ar):
            return IntentResult(IntentType.PREV_DESKTOP, confidence=0.96, original_text=text)

        # Task Manager & Recycle Bin
        if re.search(r'(مدير\s+المهام|task\s+manager|gestionnaire\s+des\s+t[aâ]ches)', norm_ar):
            return IntentResult(IntentType.OPEN_TASK_MANAGER, confidence=0.96, original_text=text)

        if re.search(r'(افرغ\s+سله\s+المحذوفات|خوي\s+الكورباي|نظف\s+سله\s+المحذوفات|empty\s+recycle\s+bin|vider\s+la\s+corbeille)', norm_ar):
            return IntentResult(IntentType.EMPTY_RECYCLE_BIN, confidence=0.97, original_text=text)

        # Zoom Controls
        if re.search(r'(تكبير\s+الشاشه|كبر\s+الزووم|zoom\s+in|agrandir\s+le\s+zoom)', norm_ar):
            return IntentResult(IntentType.ZOOM_IN, confidence=0.96, original_text=text)

        if re.search(r'(تصغير\s+الشاشه|صغر\s+الزووم|zoom\s+out|diminuer\s+le\s+zoom)', norm_ar):
            return IntentResult(IntentType.ZOOM_OUT, confidence=0.96, original_text=text)

        if re.search(r'(اعاده\s+ضبط\s+الزووم|رجع\s+الزووم|reset\s+zoom)', norm_ar):
            return IntentResult(IntentType.ZOOM_RESET, confidence=0.96, original_text=text)

        # Virtual Keyboard Toggle
        if re.search(r'(لوحه\s+المفاتيح|الكلافي|كلافيي|virtual\s+keyboard|clavier\s+virtuel)', norm_ar):
            return IntentResult(IntentType.TOGGLE_KEYBOARD_HUD, confidence=0.96, original_text=text)

        # Screen Refresh
        if re.search(r'(تحديث\s+الشاشه|تحديث|ريفريش|refresh|actualiser)', norm_ar):
            return IntentResult(IntentType.REFRESH_SCREEN, confidence=0.95, original_text=text)

        # ==========================================
        # VOLUME & MEDIA (Fusha + Darija + Egyptian + Gulf)
        # ==========================================
        if re.search(r'(اخفض|وطي|وطّي|نقص|هبط|قصر\s+علي|قصر\s+على)\s+(الصوت|في\s+الصوت)|volume\s+down|baisse\s+le\s+son|diminuer\s+le\s+volume', norm_ar):
            return IntentResult(IntentType.VOLUME_DOWN, confidence=0.97, original_text=text)

        if re.search(r'(ارفع|علي|علّي|زيد|طلع|طول\s+علي|طول\s+على|قوي)\s+(الصوت|في\s+الصوت)|volume\s+up|monte\s+le\s+son|augmenter\s+le\s+volume', norm_ar):
            return IntentResult(IntentType.VOLUME_UP, confidence=0.97, original_text=text)

        if re.search(r'(اكتم\s+الصوت|سكت\s+الصوت|اقطع\s+الصوت|كوبي\s+الصوت|صامت|ميوت|mute|muet|couper\s+le\s+son)', norm_ar):
            return IntentResult(IntentType.VOLUME_MUTE, confidence=0.97, original_text=text)

        if re.search(r'(شغل|شغّل|اوقف|اوقّف|حبس|دير\s+بلاي)\s+(الموسيقي|الموسيقى|الصوت|الفيديو|الغنيه|الغنية)|play\s+music|pause\s+music|lecture|pause', norm_ar):
            return IntentResult(IntentType.MEDIA_PLAY_PAUSE, confidence=0.96, original_text=text)

        if re.search(r'(التالي|اللي\s+بعدو|next\s+track|musique\s+suivante|suivant)', norm_ar):
            return IntentResult(IntentType.MEDIA_NEXT, confidence=0.95, original_text=text)

        if re.search(r'(السابق|اللي\s+فات|previous\s+track|musique\s+précédente|precedent)', norm_ar):
            return IntentResult(IntentType.MEDIA_PREVIOUS, confidence=0.95, original_text=text)

        # ==========================================
        # BRIGHTNESS & SCREENSHOT (Fusha + Dialects)
        # ==========================================
        if re.search(r'(ارفع|زياده|علي|زيد|طلع)\s+(السطوع|الاضاءه|الضو)|brightness\s+up|augmenter\s+luminosité|augmenter\s+luminosite', norm_ar):
            return IntentResult(IntentType.BRIGHTNESS_UP, confidence=0.96, original_text=text)

        if re.search(r'(اخفض|تقليل|وطي|نقص|هبط)\s+(السطوع|الاضاءه|الضو)|brightness\s+down|baisser\s+luminosité|baisser\s+luminosite', norm_ar):
            return IntentResult(IntentType.BRIGHTNESS_DOWN, confidence=0.96, original_text=text)

        if re.search(r'(التقط\s+صوره\s+للشاشه|التقط\s+صورة\s+للشاشة|لقطه\s+شاشه|لقطة\s+شاشة|دير\s+كابتير|دير\s+لقطه|صور\s+الشاشه|صور\s+ليكرون|كابتيري|سكرين\s+شوت|screenshot|capture\s+d\'[eé]cran)', norm_ar):
            return IntentResult(IntentType.SCREENSHOT, confidence=0.98, original_text=text)

        # ==========================================
        # SCROLLING (Fusha + Dialects)
        # ==========================================
        if re.search(r'(مرر\s+للاعلى|مرر\s+للأعلى|اطلع\s+لفوق|طلع\s+للفوق|اصعد\s+فوق|سكروولي\s+فوق|طلع)\b|scroll\s+up|défiler\s+vers\s+le\s+haut|defiler\s+vers\s+le\s+haut', norm_ar):
            return IntentResult(IntentType.SCROLL_UP, confidence=0.96, original_text=text)

        if re.search(r'(مرر\s+للاسفل|مرر\s+للأسفل|انزل\s+لتحت|هبط\s+لتحت|انزل\s+تحت|سكروولي\s+تحت|هبط)\b|scroll\s+down|défiler\s+vers\s+le\s+bas|defiler\s+vers\s+le\s+bas', norm_ar):
            return IntentResult(IntentType.SCROLL_DOWN, confidence=0.96, original_text=text)

        # ==========================================
        # BROWSER SPECIFICS
        # ==========================================
        if re.search(r'(تبويب\s+جديد|افتح\s+تبويب|حل\s+تبويب|افتح\s+تاب|حل\s+تاب|new\s+tab|nouvel\s+onglet)', norm_ar):
            return IntentResult(IntentType.BROWSER_NEW_TAB, confidence=0.97, original_text=text)

        if re.search(r'(اغلق\s+التبويب|بلع\s+التبويب|سد\s+التبويب|صك\s+التبويب|close\s+tab|fermer\s+l\'onglet)', norm_ar):
            return IntentResult(IntentType.BROWSER_CLOSE_TAB, confidence=0.97, original_text=text)

        if re.search(r'(التبويب\s+التالي|التاب\s+الجاي|next\s+tab|onglet\s+suivant)', norm_ar):
            return IntentResult(IntentType.BROWSER_NEXT_TAB, confidence=0.97, original_text=text)

        if re.search(r'^(ارجع|ولي|go\s+back|retour|retourner)$', norm_ar):
            return IntentResult(IntentType.NAVIGATE_BACK, confidence=0.96, original_text=text)

        if re.search(r'^(الي\s+الامام|إلى\s+الأمام|زيد\s+للقدام|forward|avancer)$', norm_ar):
            return IntentResult(IntentType.NAVIGATE_FORWARD, confidence=0.96, original_text=text)

        # Browser search: "ابحث عن ..." / "حوس على ..." / "دور على ..." / "search for ..."
        search_match = re.match(r'(?:ابحث\s+عن|ابحث\s+في\s+المتصفح\s+عن|حوس\s+على|حوس\s+علي|دور\s+على|دور\s+علي|سيرشي\s+على|search\s+for|cherche)\s+(.*)', norm_ar)
        if search_match:
            query = search_match.group(1).strip()
            return IntentResult(IntentType.BROWSER_SEARCH, target=query, confidence=0.95, original_text=text)

        # ==========================================
        # POWER & SYSTEM LOCK (Fusha + Dialects)
        # ==========================================
        if re.search(r'(اقفل\s+الكمبيوتر|سد\s+البيسي|صك\s+الجهاز|قفل\s+الشاشه|lock\s+computer|verrouiller)', norm_ar):
            return IntentResult(IntentType.SYSTEM_LOCK, confidence=0.98, original_text=text)

        if re.search(r'(اعد\s+تشغيل|اعمل\s+ريستارت|روديماغي|restart\s+computer|redémarrer|redemarrer)', norm_ar):
            return IntentResult(IntentType.SYSTEM_RESTART, confidence=0.98, original_text=text)

        if re.search(r'(اوقف\s+تشغيل|طفي\s+الكمبيوتر|طفي\s+البيسي|طفي\s+الجهاز|shutdown\s+computer|[eé]teindre)', norm_ar):
            return IntentResult(IntentType.SYSTEM_SHUTDOWN, confidence=0.98, original_text=text)

        # ==========================================
        # FOLDERS & FILES
        # ==========================================
        folder_match = re.match(r'(?:افتح\s+مجلد|حل\s+دوسيي|open\s+folder|ouvre\s+le\s+dossier)\s+(.*)', norm_ar)
        if folder_match:
            target_folder = folder_match.group(1).strip()
            return IntentResult(IntentType.OPEN_FOLDER, target=target_folder, confidence=0.96, original_text=text)

        if re.search(r'(?:افتح|حل|open|ouvre)\s+(?:les\s+)?(?:التحميلات|التيليشارجومون|downloads|t[eé]l[eé]chargements)', norm_ar):
            return IntentResult(IntentType.OPEN_FOLDER, target="downloads", confidence=0.98, original_text=text)

        if re.search(r'(?:افتح|حل|open|ouvre)\s+(?:mes\s+)?(?:ملفاتي|المستندات|documents)', norm_ar):
            return IntentResult(IntentType.OPEN_FOLDER, target="documents", confidence=0.98, original_text=text)

        if re.search(r'(الملف\s+الاخير|الملف\s+الأخير|latest\s+download|dernier\s+fichier)', norm_ar):
            return IntentResult(IntentType.OPEN_RECENT_FILE, confidence=0.95, original_text=text)

        create_dir_match = re.match(
            r'(?:انشئ\s+مجلدا|انشئ\s+مجلد|دير\s+دوسيي|كريي\s+دوسيي|create\s+(?:a\s+)?folder|cr[eé]er\s+un\s+dossier)'
            r'(?:\s+(?:اسمه|سمه|named|appel[eé]e))?'
            r'(?:\s+(.+))?$',
            norm_ar
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
            r'(?:احذف\s+هذا\s+الملف|احذف\s+الملف|مسح\s+الملف|delete\s+file|supprime\s+le\s+fichier)'
            r'(?:\s+(.+))?$',
            norm_ar
        )
        if delete_file_match:
            return IntentResult(
                IntentType.DELETE_FILE,
                target=(delete_file_match.group(1) or "").strip() or None,
                confidence=0.95,
                original_text=text
            )

        # ==========================================
        # APPLICATION LAUNCH / CLOSE (Fusha + Darija: حل/بلع + Egyptian + Gulf)
        # ==========================================
        open_app_match = re.match(r'(?:افتح|شغل|شغّل|حل|دير|دور|بطل|open|launch|start|lance|ouvre)\s+(.*)', norm_ar)
        if open_app_match:
            app_target = open_app_match.group(1).strip()
            return IntentResult(IntentType.LAUNCH_APP, target=app_target, confidence=0.95, original_text=text)

        close_app_match = re.match(r'(?:اغلق|أغلق|اقفل|بلع|سد|صك|سكر|فيرمي|close|quitter|ferme)\s+(.*)', norm_ar)
        if close_app_match:
            app_target = close_app_match.group(1).strip()
            return IntentResult(IntentType.LAUNCH_APP, target=app_target, parameters={"action": "close"}, confidence=0.94, original_text=text)

        # ==========================================
        # MACROS
        # ==========================================
        if "morning setup" in raw_lower:
            return IntentResult(IntentType.EXECUTE_MACRO, target="Morning Setup", confidence=0.98, original_text=text)
        if "coding setup" in raw_lower:
            return IntentResult(IntentType.EXECUTE_MACRO, target="Coding Setup", confidence=0.98, original_text=text)

        # ==========================================
        # PHONETIC / LEVENSHTEIN FUZZY MATCHING FALLBACK
        # ==========================================
        # If words were slightly misheard or deformed due to microphone noise
        best_match = None
        min_dist = 999
        for canonical, intent_t, target_val in self.canonical_commands:
            dist = levenshtein_distance(norm_ar, canonical)
            # Accept if edit distance is 1 or 2 relative to phrase length
            max_allowed = 1 if len(canonical) <= 6 else 2
            if dist <= max_allowed and dist < min_dist:
                min_dist = dist
                best_match = (intent_t, target_val)

        if best_match:
            return IntentResult(best_match[0], target=best_match[1], confidence=0.86, original_text=text)

        return IntentResult(IntentType.UNKNOWN, confidence=0.2, original_text=text)
