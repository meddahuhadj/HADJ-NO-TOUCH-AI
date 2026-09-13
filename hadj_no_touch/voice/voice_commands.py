"""Voice command parsing: English, French and Arabic.

Converts recognized speech into a canonical command intent. The executor
(located in the app core) maps intents to real Windows actions. Parsing is
entirely local: no audio or text leaves the machine for this step.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..logging_setup import get_logger

log = get_logger("voice.commands")

NONE_INTENT = "NONE"

# Canonical intents
OPEN_APP = "OPEN_APP"
CLOSE_WINDOW = "CLOSE_WINDOW"
MINIMIZE = "MINIMIZE"
MAXIMIZE = "MAXIMIZE"
SWITCH_APP = "SWITCH_APP"
SHOW_DESKTOP = "SHOW_DESKTOP"
SCROLL_UP = "SCROLL_UP"
SCROLL_DOWN = "SCROLL_DOWN"
PAGE_DOWN = "PAGE_DOWN"
PAGE_UP = "PAGE_UP"
VOLUME_UP = "VOLUME_UP"
VOLUME_DOWN = "VOLUME_DOWN"
VOLUME_SET = "VOLUME_SET"
MUTE = "MUTE"
UNMUTE = "UNMUTE"
PLAY_PAUSE = "PLAY_PAUSE"
NEXT_TRACK = "NEXT_TRACK"
PREV_TRACK = "PREV_TRACK"
STOP_MEDIA = "STOP_MEDIA"
NEXT_SLIDE = "NEXT_SLIDE"
PREV_SLIDE = "PREV_SLIDE"
START_PRESENTATION = "START_PRESENTATION"
END_PRESENTATION = "END_PRESENTATION"
BLACK_SCREEN = "BLACK_SCREEN"
NEXT_PAGE = "NEXT_PAGE"
PREV_PAGE = "PREV_PAGE"
GO_BACK = "GO_BACK"
GO_FORWARD = "GO_FORWARD"
ZOOM_IN = "ZOOM_IN"
ZOOM_OUT = "ZOOM_OUT"
COPY = "COPY"
PASTE = "PASTE"
CUT = "CUT"
UNDO = "UNDO"
SELECT_ALL = "SELECT_ALL"
PRESS_ENTER = "PRESS_ENTER"
TAB_KEY = "TAB_KEY"
TYPE_TEXT = "TYPE_TEXT"
SCREENSHOT = "SCREENSHOT"
NEXT_TAB = "NEXT_TAB"
PREV_TAB = "PREV_TAB"
CLOSE_TAB = "CLOSE_TAB"
NEW_TAB = "NEW_TAB"
REFRESH = "REFRESH"
FIND = "FIND"
OPEN_SETTINGS = "OPEN_SETTINGS"
PAUSE_CONTROL = "PAUSE_CONTROL"
RESUME_CONTROL = "RESUME_CONTROL"
EMERGENCY_STOP = "EMERGENCY_STOP"
HANDS_BUSY_ON = "HANDS_BUSY_ON"
HANDS_BUSY_OFF = "HANDS_BUSY_OFF"
CALIBRATE = "CALIBRATE"
TOGGLE_KEYBOARD = "TOGGLE_KEYBOARD"
SHOW_UI = "SHOW_UI"
HIDE_UI = "HIDE_UI"
HELP = "HELP"
PROFILE = "PROFILE"
COPILOT = "COPILOT"


@dataclass
class VoiceIntent:
    intent: str = NONE_INTENT
    params: dict = field(default_factory=dict)
    confidence: float = 0.0
    language: str = "en"
    raw_text: str = ""


def _ar_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    out = []
    for c in text:
        if unicodedata.combining(c):
            continue
        if c in "أإآ":
            c = "ا"
        elif c == "ة":
            c = "ه"
        elif c == "ى":
            c = "ي"
        elif c == "ـ":
            continue
        out.append(c)
    return "".join(out)


# ---- command catalog -------------------------------------------------------
# Each entry: intent, languages, patterns (per language), param extraction.
COMMANDS: list[dict] = [
    # --- application launching --------------------------------------------
    {"intent": OPEN_APP, "langs": ["en"],
     "patterns": [r"\bopen\s+(?:the\s+|me\s+)?(?P<app>[a-z0-9.\- ]+?)\s*$",
                  r"\blaunch\s+(?:the\s+)?(?P<app>[a-z0-9.\- ]+?)\s*$",
                  r"\bstart\s+(?:the\s+)?(?P<app>[a-z0-9.\- ]+?)\s*$"],
     "param": "app"},
    {"intent": OPEN_APP, "langs": ["fr"],
     "patterns": [r"\bouvre\s+(?:moi\s+|le\s+|la\s+)?(?P<app>[a-z0-9.é\- ]+?)\s*$",
                  r"\blance\s+(?:le\s+|la\s+)?(?P<app>[a-z0-9.\- ]+?)\s*$",
                  r"\bdemarre\s+(?:le\s+|la\s+)?(?P<app>[a-z0-9.\- ]+?)\s*$"],
     "param": "app"},
    {"intent": OPEN_APP, "langs": ["ar"],
     "patterns": [r"افتح\s+(?:لي\s+)?(?P<app>[^ ]+)",
                  r"شغل\s+(?P<app>[^ ]+)",
                  r"فتح\s+(?P<app>[^ ]+)"],
     "param": "app"},
    # --- window actions ------------------------------------------------------
    {"intent": CLOSE_WINDOW, "langs": ["en"],
     "patterns": [r"\bclose\s+this\s+(?:window|app|program)", r"\bclose\s+(?:the\s+)?window",
                  r"\bfeu?me\s+ce",
                  r"\bexit\s+(?:the\s+)?app"]},
    {"intent": CLOSE_WINDOW, "langs": ["fr"],
     "patterns": [r"\bf[eé]rme\s+(?:cette\s+)?fen[eê]tre", r"\bfermer\s+la\s+fen[eê]tre",
                  r"\bquitter\s+ce\s+programme", r"\bclose\s+this"]},
    {"intent": CLOSE_WINDOW, "langs": ["ar"],
     "patterns": [r"اغلق\s+هذه\s+النافذه|اغلق\s+النافذه|اطفئ\s+النافذه"]},
    {"intent": MINIMIZE, "langs": ["en"],
     "patterns": [r"\bminimize(\s+this(\s+window)?)?", r"\bminimise\b"]},
    {"intent": MINIMIZE, "langs": ["fr"],
     "patterns": [r"\br[ée]duire(\s+la\s+fen[eê]tre)?", r"\bminimiser\b"]},
    {"intent": MINIMIZE, "langs": ["ar"], "patterns": [r"تصغير\s+النافذه"]},
    {"intent": MAXIMIZE, "langs": ["en"],
     "patterns": [r"\bmaximize(\s+this(\s+window)?)?", r"\bmaximise\b", r"\bfull[-\s]?screen\b"]},
    {"intent": MAXIMIZE, "langs": ["fr"],
     "patterns": [r"\bagrandir(\s+la\s+fen[eê]tre)?", r"\bmaximiser\b", r"\bplein\s+[ée]cran\b"]},
    {"intent": MAXIMIZE, "langs": ["ar"], "patterns": [r"تكبير\s+النافذه|ملء\s+الشاشه"]},
    {"intent": SWITCH_APP, "langs": ["en"], "patterns": [r"\bswitch\s+(?:to|windows)",
                                                        r"\balt\s*tab"]},
    {"intent": SWITCH_APP, "langs": ["fr"], "patterns": [r"\b(?:basculer|changer)\s+de\s+fen[eê]tre"]},
    {"intent": SWITCH_APP, "langs": ["ar"], "patterns": [r"تبديل\s+النوافذ"]},
    {"intent": SHOW_DESKTOP, "langs": ["en"], "patterns": [r"\bshow\s+desktop\b", r"\bgo\s+to\s+desktop\b"]},
    {"intent": SHOW_DESKTOP, "langs": ["fr"], "patterns": [r"\bbureau\b", r"\bafficher\s+le\s+bureau\b"]},
    {"intent": SHOW_DESKTOP, "langs": ["ar"], "patterns": [r"اظهر\s+سطح\s+المكتب"]},
    # --- scrolling / navigation ---------------------------------------------
    {"intent": SCROLL_DOWN, "langs": ["en"],
     "patterns": [r"\bscroll\s+down\b", r"\bpage\s+down\b", r"\bgo\s+down\b"]},
    {"intent": SCROLL_DOWN, "langs": ["fr"],
     "patterns": [r"\b(?:d[ée]file|fais\s+d[ée]filer).{0,4}bas", r"\bdescend(s|re)?\b", r"\bbas\b"]},
    {"intent": SCROLL_DOWN, "langs": ["ar"],
     "patterns": [r"انزل|اسفل|مرر\s+للاسفل"]},
    {"intent": SCROLL_UP, "langs": ["en"],
     "patterns": [r"\bscroll\s+up\b", r"\bpage\s+up\b", r"\bgo\s+up\b"]},
    {"intent": SCROLL_UP, "langs": ["fr"],
     "patterns": [r"\b(?:d[ée]file|fais\s+d[ée]filer).{0,4}haut", r"\bmonte(r)?\b", r"\bhaut\b"]},
    {"intent": SCROLL_UP, "langs": ["ar"], "patterns": [r"ارتفع|اعلى|مرر\s+لاعلى"]},
    {"intent": NEXT_PAGE, "langs": ["en"],
     "patterns": [r"\bnext\s+page\b", r"\bnext\s+sheet\b", r"\bpage\s+next\b",
                  r"\bturn\s+the\s+page\b"]},
    {"intent": NEXT_PAGE, "langs": ["fr"],
     "patterns": [r"\bpage\s+suivante\b", r"\btourne\s+la\s+page\b", r"\bsuivante\b"]},
    {"intent": NEXT_PAGE, "langs": ["ar"], "patterns": [r"الصفحه\s+التاليه|الصفحه\s+القادمه"]},
    {"intent": PREV_PAGE, "langs": ["en"],
     "patterns": [r"\bprevious\s+page\b", r"\bprev\s+page\b", r"\bgo\s+back\s+a\s+page\b"]},
    {"intent": PREV_PAGE, "langs": ["fr"],
     "patterns": [r"\bpage\s+pr[ée]c[ée]dente\b", r"\bpr[ée]c[ée]dente\b"]},
    {"intent": PREV_PAGE, "langs": ["ar"],
     "patterns": [r"الصفحه\s+السابقه"]},
    {"intent": GO_BACK, "langs": ["en"],
     "patterns": [r"\bgo\s+back\b", r"\bback\s+page\b", r"\bnavigate\s+back\b", r"\bback\b"]},
    {"intent": GO_BACK, "langs": ["fr"],
     "patterns": [r"\brevenir\s+en\s+arri[eê]re\b", r"\bpr[ée]c[ée]dent\b", r"\b retour\b"]},
    {"intent": GO_BACK, "langs": ["ar"], "patterns": [r"رجوع|ارجع|العوده\s+للخلف"]},
    {"intent": GO_FORWARD, "langs": ["en"], "patterns": [r"\bgo\s+forward\b", r"\bforward\b"]},
    {"intent": GO_FORWARD, "langs": ["fr"],
     "patterns": [r"\bavancer\b", r"\bsuivant\b", r"\baller\s+de\s+l'avant\b"]},
    {"intent": GO_FORWARD, "langs": ["ar"], "patterns": [r"تقدم|للأمام"]},
    # --- tabs -----------------------------------------------------------------
    {"intent": NEXT_TAB, "langs": ["en"], "patterns": [r"\bnext\s+tab\b"]},
    {"intent": NEXT_TAB, "langs": ["fr"], "patterns": [r"\bonglet\s+suivant\b"]},
    {"intent": NEXT_TAB, "langs": ["ar"], "patterns": [r"التبويب\s+التالي"]},
    {"intent": PREV_TAB, "langs": ["en"], "patterns": [r"\bprevious\s+tab\b", r"\bprev\s+tab\b"]},
    {"intent": PREV_TAB, "langs": ["fr"], "patterns": [r"\bonglet\s+pr[ée]c[ée]dent\b"]},
    {"intent": PREV_TAB, "langs": ["ar"], "patterns": [r"التبويب\s+السابق"]},
    {"intent": CLOSE_TAB, "langs": ["en"], "patterns": [r"\bclose\s+(?:a\s+)?tab\b"]},
    {"intent": CLOSE_TAB, "langs": ["fr"], "patterns": [r"\bfermer\s+l'onglet\b", r"\bferme\s+let\b"]},
    {"intent": CLOSE_TAB, "langs": ["ar"], "patterns": [r"اغلق\s+التبويب"]},
    {"intent": NEW_TAB, "langs": ["en"], "patterns": [r"\bnew\s+tab\b", r"\bopen\s+a\s+new\s+tab\b"]},
    {"intent": NEW_TAB, "langs": ["fr"], "patterns": [r"\bnouvel(\s+onglet)?\b"]},
    {"intent": NEW_TAB, "langs": ["ar"], "patterns": [r"تبويب\s+جديد"]},
    {"intent": REFRESH, "langs": ["en"], "patterns": [r"\brefresh\b", r"\breload\b"]},
    {"intent": REFRESH, "langs": ["fr"], "patterns": [r"\bactualiser\b", r"\brafra[ïi]chir\b"]},
    {"intent": REFRESH, "langs": ["ar"], "patterns": [r"تحديث"]},
    {"intent": FIND, "langs": ["en"], "patterns": [r"\bfind\b", r"\bsearch\s+for\b"]},
    {"intent": FIND, "langs": ["fr"], "patterns": [r"\brechercher\b", r"\bfind\b"]},
    {"intent": FIND, "langs": ["ar"], "patterns": [r"ابحث|بحث"]},
    # --- zoom -----------------------------------------------------------------
    {"intent": ZOOM_IN, "langs": ["en"],
     "patterns": [r"\bzoom\s+in\b", r"\bmagnify\b", r"\bzoom\s*\+\b"]},
    {"intent": ZOOM_IN, "langs": ["fr"],
     "patterns": [r"\bzoom(er)?\s+(avant|[+]|plus)\b", r"\bagrandir\s+(la\s+)?(vue|image)\b"]},
    {"intent": ZOOM_IN, "langs": ["ar"], "patterns": [r"كبّر|تقريب\s+الرؤيه"]},
    {"intent": ZOOM_OUT, "langs": ["en"],
     "patterns": [r"\bzoom\s+out\b", r"\bzoom\s*-\b"]},
    {"intent": ZOOM_OUT, "langs": ["fr"],
     "patterns": [r"\bzoom(er)?\s+(arri[eê]re|[-]|moins)\b", r"\br[ée]duire\s+(la\s+)?(vue|image)\b"]},
    {"intent": ZOOM_OUT, "langs": ["ar"], "patterns": [r"صغّر|ابعاد\s+الرؤيه"]},
    # --- volume/media -----------------------------------------------------------
    {"intent": VOLUME_SET, "langs": ["en"],
     "patterns": [r"\b(?:set\s+|volume\s+)?volume\s+(?:to\s+)?(?P<percent>\d+(?:\.\d+)?)\s*%?\b",
                  r"\bvolume\s+(?P<percent>[a-z]+)"],
     "param": "percent"},
    {"intent": VOLUME_SET, "langs": ["fr"],
     "patterns": [r"\bvolume\s+(?:[aà]\s+)?(?P<percent>\d+(?:\.\d+)?)\s*%?\b",
                  r"\bmets\s+le\s+volume\s+(?:[aà]\s+)?(?P<percent>\d+)"],
     "param": "percent"},
    {"intent": VOLUME_SET, "langs": ["ar"],
     "patterns": [r"مستوى\s+الصوت\s+(?P<percent>\d+)", r"الصوت\s+(?P<percent>\d+)"],
     "param": "percent"},
    {"intent": VOLUME_UP, "langs": ["en"],
     "patterns": [r"\bvolume\s+up\b", r"\blouder\b", r"\bincrease\s+(?:the\s+)?volume\b"]},
    {"intent": VOLUME_UP, "langs": ["fr"],
     "patterns": [r"\bvolume\s+\+\b", r"\bmonte\s+le\s+volume\b", r"\bplus\s+fort\b"]},
    {"intent": VOLUME_UP, "langs": ["ar"],
     "patterns": [r"ارفع\s+الصوت|الصوت\s+اعلي"]},
    {"intent": VOLUME_DOWN, "langs": ["en"],
     "patterns": [r"\bvolume\s+down\b", r"\bquieter\b", r"\bdecrease\s+(?:the\s+)?volume\b"]},
    {"intent": VOLUME_DOWN, "langs": ["fr"],
     "patterns": [r"\bvolume\s+\-\b", r"\bbaisse\s+le\s+volume\b", r"\bmoins\s+fort\b"]},
    {"intent": VOLUME_DOWN, "langs": ["ar"],
     "patterns": [r"اخفض\s+الصوت|الصوت\s+اقل"]},
    {"intent": MUTE, "langs": ["en"], "patterns": [r"\bmute\b", r"\bsilence\b"]},
    {"intent": MUTE, "langs": ["fr"], "patterns": [r"\bmuet(te)?\b", r"\bcoupe[rs]?\s+le\s+son\b"]},
    {"intent": MUTE, "langs": ["ar"], "patterns": [r"كتم\s+الصوت"]},
    {"intent": UNMUTE, "langs": ["en"], "patterns": [r"\bunmute\b", r"\bsound\s+on\b"]},
    {"intent": UNMUTE, "langs": ["fr"], "patterns": [r"\br[ée]tablis[s]?\s+le\s+son\b"]},
    {"intent": UNMUTE, "langs": ["ar"], "patterns": [r"الغاء\s+كتم\s+الصوت"]},
    {"intent": PLAY_PAUSE, "langs": ["en"],
     "patterns": [r"\b(?:play|pause)\b", r"\bresume\b", r"\bstop\s+the\s+(?:music|video)\b"]},
    {"intent": PLAY_PAUSE, "langs": ["fr"],
     "patterns": [r"\b(?:joue|pause|lecture)\b", r"\bplay\b", r"\barrete\s+le\s*s?on\b"]},
    {"intent": PLAY_PAUSE, "langs": ["ar"], "patterns": [r"تشغيل|ايقاف|الموسيقى"]},
    {"intent": NEXT_TRACK, "langs": ["en"],
     "patterns": [r"\bnext\s+(?:track|song|video|video\s+player)\b",
                  r"\bskip\s+(?:forward|next)\b"]},
    {"intent": NEXT_TRACK, "langs": ["fr"],
     "patterns": [r"\b(?:piste|morceau|chanson)\s+suivant(e)?\b",
                  r"\bsuivant(e)?\s+(?:piste|morceau|chanson)\b"]},
    {"intent": NEXT_TRACK, "langs": ["ar"], "patterns": [r"التالي|الاغنيه\s+التاليه"]},
    {"intent": PREV_TRACK, "langs": ["en"],
     "patterns": [r"\bprevious\s+(?:track|song)\b", r"\bprev\s+(?:track|song)\b",
                  r"\brewind\b"]},
    {"intent": PREV_TRACK, "langs": ["fr"],
     "patterns": [r"\b(?:piste|morceau|chanson)\s+pr[ée]c[ée]dent(e)?\b"]},
    {"intent": PREV_TRACK, "langs": ["ar"], "patterns": [r"السابقه|الاغنيه\s+السابقه"]},
    {"intent": STOP_MEDIA, "langs": ["en"], "patterns": [r"\bstop\s+(?:the\s+)?(?:music|video|media)\b"]},
    {"intent": STOP_MEDIA, "langs": ["fr"], "patterns": [r"\barrete\b"]},
    {"intent": STOP_MEDIA, "langs": ["ar"], "patterns": [r"اوقف\s+الوسائط"]},
    # --- presentation -----------------------------------------------------------
    {"intent": START_PRESENTATION, "langs": ["en"],
     "patterns": [r"\b(start|begin)\s+(?:the\s+)?presentation\b", r"\bf5\b"]},
    {"intent": START_PRESENTATION, "langs": ["fr"],
     "patterns": [r"\b(?:commencer|d[ée]marrer|lancer)\s+(?:la\s+)?pr[ée]sentation\b"]},
    {"intent": START_PRESENTATION, "langs": ["ar"],
     "patterns": [r"ابدأ\s+العرض\s+التقديمي"]},
    {"intent": END_PRESENTATION, "langs": ["en"],
     "patterns": [r"\b(end|exit|stop)\s+(?:the\s+)?presentation\b", r"\bexit\s+slideshow\b"]},
    {"intent": END_PRESENTATION, "langs": ["fr"],
     "patterns": [r"\b(?:finir|terminer|quitter)\s+(?:la\s+)?pr[ée]sentation\b"]},
    {"intent": END_PRESENTATION, "langs": ["ar"],
     "patterns": [r"انهي\s+العرض"]},
    {"intent": NEXT_SLIDE, "langs": ["en"],
     "patterns": [r"\bnext\s+slide\b", r"\bslide\s+next\b", r"\bforward\s+(?:one\s+)?slide\b"]},
    {"intent": NEXT_SLIDE, "langs": ["fr"],
     "patterns": [r"\b(?:diapositive|slide)\s+suivante\b", r"\bslide\s+suivant\b", r"\bdiapo\s+suivante\b"]},
    {"intent": NEXT_SLIDE, "langs": ["ar"],
     "patterns": [r"الشريحه\s+التاليه|الشريحه\s+القادمه"]},
    {"intent": PREV_SLIDE, "langs": ["en"],
     "patterns": [r"\bprevious\s+slide\b", r"\bprev\s+slide\b", r"\bslide\s+previous\b"]},
    {"intent": PREV_SLIDE, "langs": ["fr"],
     "patterns": [r"\b(?:diapositive|slide)\s+pr[ée]c[ée]dente\b"]},
    {"intent": PREV_SLIDE, "langs": ["ar"],
     "patterns": [r"الشريحه\s+السابقه"]},
    {"intent": BLACK_SCREEN, "langs": ["en"],
     "patterns": [r"\bblack\s+screen\b", r"\bblank\s+screen\b"]},
    {"intent": BLACK_SCREEN, "langs": ["fr"],
     "patterns": [r"\b[ée]cran\s+noir\b"]},
    {"intent": BLACK_SCREEN, "langs": ["ar"],
     "patterns": [r"شاشه\s+سوداء"]},
    # --- editing ---------------------------------------------------------------
    {"intent": COPY, "langs": ["en", "fr"], "patterns": [r"\bcopy\b", r"\bcopier\b"]},
    {"intent": COPY, "langs": ["ar"], "patterns": [r"نسخ"]},
    {"intent": PASTE, "langs": ["en", "fr"], "patterns": [r"\bpaste\b", r"\bcolle(r)?\b"]},
    {"intent": PASTE, "langs": ["ar"], "patterns": [r"لصق"]},
    {"intent": CUT, "langs": ["en", "fr"], "patterns": [r"\bcut\b", r"\bcouper\b"]},
    {"intent": CUT, "langs": ["ar"], "patterns": [r"قص"]},
    {"intent": UNDO, "langs": ["en", "fr"], "patterns": [r"\bundo\b", r"\bannuler\b"]},
    {"intent": UNDO, "langs": ["ar"], "patterns": [r"تراجع"]},
    {"intent": SELECT_ALL, "langs": ["en"], "patterns": [r"\bselect\s+all\b", r"\bselect\s+everything\b"]},
    {"intent": SELECT_ALL, "langs": ["fr"], "patterns": [r"\btout\s+s[ée]lectionner\b", r"\bs[ée]lectionner\s+tout\b"]},
    {"intent": SELECT_ALL, "langs": ["ar"], "patterns": [r"تحديد\s+الكل"]},
    {"intent": PRESS_ENTER, "langs": ["en"], "patterns": [r"\bpress\s+enter\b", r"\bhit\s+enter\b",
                                                         r"\benter\s+key\b"]},
    {"intent": PRESS_ENTER, "langs": ["fr"], "patterns": [r"\bappuie\s+sur\s+entr[ée]e\b",
                                                          r"\bvalider\b"]},
    {"intent": PRESS_ENTER, "langs": ["ar"], "patterns": [r"اضغط\s+ادخال"]},
    {"intent": TAB_KEY, "langs": ["en"], "patterns": [r"\bpress\s+tab\b", r"\btab\s+key\b"]},
    {"intent": TAB_KEY, "langs": ["fr"], "patterns": [r"\bappuie\s+sur\s+tab\b"]},
    {"intent": TAB_KEY, "langs": ["ar"], "patterns": [r"اضغط\s+تبويب"]},
    {"intent": TYPE_TEXT, "langs": ["en"],
     "patterns": [r"\btype\s+(?P<text>.+)", r"\bwrite\s+(?P<text>.+)", r"\bdictate\s+(?P<text>.+)"],
     "param": "text"},
    {"intent": TYPE_TEXT, "langs": ["fr"],
     "patterns": [r"\b[ée]cris?\s+(?P<text>.+)", r"\btape\s+(?P<text>.+)", r"\bdicte\s+(?P<text>.+)"],
     "param": "text"},
    {"intent": TYPE_TEXT, "langs": ["ar"],
     "patterns": [r"اكتب\s+(?P<text>.+)"],
     "param": "text"},
    # --- screenshot / settings -------------------------------------------------
    {"intent": SCREENSHOT, "langs": ["en"], "patterns": [r"\btake\s+(?:a\s+)?screenshot\b",
                                                        r"\bscreenshot\b", r"\bcapture\s+(?:the\s+)?screen\b"]},
    {"intent": SCREENSHOT, "langs": ["fr"], "patterns": [r"\bcapture\s+d'[ée]cran\b",
                                                        r"\bscreenshot\b", r"\bimprim[ée]cran\b"]},
    {"intent": SCREENSHOT, "langs": ["ar"], "patterns": [r"لقطه\s+شاشه|تصوير\s+الشاشه"]},
    {"intent": OPEN_SETTINGS, "langs": ["en"],
     "patterns": [r"\bopen\s+(?:the\s+)?(?:windows\s+)?settings\b", r"\bsettings\b"]},
    {"intent": OPEN_SETTINGS, "langs": ["fr"],
     "patterns": [r"\bouvre\s+(?:les\s+)?param[eè]tres\b", r"\bparam[èe]tres\b"]},
    {"intent": OPEN_SETTINGS, "langs": ["ar"],
     "patterns": [r"الاعدادات"]},
    # --- application control --------------------------------------------------
    {"intent": PAUSE_CONTROL, "langs": ["en"],
     "patterns": [r"\bpause\s+(?:no[- ]?touch\s+)?(?:control|tracking)\b",
                  r"\bpause\s+(?:the\s+)?control\b", r"\bpause\s+tracking\b"]},
    {"intent": PAUSE_CONTROL, "langs": ["fr"],
     "patterns": [r"\bpause\s+(?:le\s+)?contr[ôo]le\b", r"\bpause\s+les\s+gestes\b"]},
    {"intent": PAUSE_CONTROL, "langs": ["ar"], "patterns": [r"ايقاف\s+التحكم"]},
    {"intent": RESUME_CONTROL, "langs": ["en"],
     "patterns": [r"\bresume\s+(?:no[- ]?touch\s+)?(?:control|tracking)\b",
                  r"\bresume\s+control\b"]},
    {"intent": RESUME_CONTROL, "langs": ["fr"],
     "patterns": [r"\breprendre\s+(?:le\s+)?contr[ôo]le\b"]},
    {"intent": RESUME_CONTROL, "langs": ["ar"], "patterns": [r"استئناف\s+التحكم"]},
    {"intent": EMERGENCY_STOP, "langs": ["en"],
     "patterns": [r"\bstop\s+(?:all\s+)?(?:no[- ]?touch\s+)?control\b",
                  r"\bemergency\s+stop\b", r"\bdisable\s+the\s+control\b",
                  r"\bstop\s+everything\b"]},
    {"intent": EMERGENCY_STOP, "langs": ["fr"],
     "patterns": [r"\barr[eê]te\s+tout\b", r"\bstop\s+urgent\b", r"\barr[eê]ter\s+le\s+contr[ôo]le\b"]},
    {"intent": EMERGENCY_STOP, "langs": ["ar"],
     "patterns": [r"ايقاف\s+الطوارئ|اوقف\s+الكل"]},
    {"intent": HANDS_BUSY_ON, "langs": ["en"],
     "patterns": [r"\bhands\s+busy\s+(?:mode\s+)?on\b", r"\bswitch\s+to\s+hands\s+busy\b",
                  r"\benable\s+hands\s+busy\b", r"\bhands\s+busy\b"]},
    {"intent": HANDS_BUSY_ON, "langs": ["fr"],
     "patterns": [r"\bmains\s+occup[ée]es\b", r"\bmode\s+mains\s+libres\b"]},
    {"intent": HANDS_BUSY_ON, "langs": ["ar"],
     "patterns": [r"اليدين\s+مشغوله|وضع\s+اليدين\s+مشغوله"]},
    {"intent": HANDS_BUSY_OFF, "langs": ["en"],
     "patterns": [r"\bhands\s+busy\s+off\b", r"\bexit\s+hands\s+busy\b", r"\bhands\s+busy\s+mode\s+off\b"]},
    {"intent": HANDS_BUSY_OFF, "langs": ["fr"],
     "patterns": [r"\bquitter\s+le\s+mode\s+mains\s+libres\b", r"\bmains\s+libres\b"]},
    {"intent": HANDS_BUSY_OFF, "langs": ["ar"],
     "patterns": [r"الغاء\s+وضع\s+اليدين\s+مشغوله"]},
    {"intent": CALIBRATE, "langs": ["en"],
     "patterns": [r"\bcalibrat(e|ion)\b", r"\brecalibrate\b", r"\bstart\s+calibration\b"]},
    {"intent": CALIBRATE, "langs": ["fr"],
     "patterns": [r"\bcalibra(tion|ge)\b"]},
    {"intent": CALIBRATE, "langs": ["ar"],
     "patterns": [r"معايره|المعاياه"]},
    {"intent": TOGGLE_KEYBOARD, "langs": ["en"],
     "patterns": [r"\b(?:open|show|hide|toggle)\s+(?:the\s+)?virtual\s+keyboard\b",
                  r"\bshow\s+(?:the\s+)?keyboard\b"]},
    {"intent": TOGGLE_KEYBOARD, "langs": ["fr"],
     "patterns": [r"\b(?:ouvre|affiche|cache)\s+(?:le\s+)?clavier\s+virtuel\b"]},
    {"intent": TOGGLE_KEYBOARD, "langs": ["ar"],
     "patterns": [r"لوحه\s+المفاتيح"]},
    {"intent": SHOW_UI, "langs": ["en"],
     "patterns": [r"\b(?:show|display|open)\s+(?:the\s+)?(?:main\s+)?interface\b",
                  r"\bshow\s+dashboard\b", r"\bshow\s+the\s+console\b", r"\bopen\s+dashboard\b"]},
    {"intent": SHOW_UI, "langs": ["fr"],
     "patterns": [r"\baffiche\s+l'interface\b", r"\bouvre\s+le\s+tableau\s+de\s+bord\b"]},
    {"intent": SHOW_UI, "langs": ["ar"],
     "patterns": [r"اظهر\s+الواجهه"]},
    {"intent": HIDE_UI, "langs": ["en"],
     "patterns": [r"\b(?:hide|close)\s+(?:the\s+)?(?:main\s+)?interface\b",
                  r"\bhide\s+(?:the\s+)?dashboard\b"]},
    {"intent": HIDE_UI, "langs": ["fr"],
     "patterns": [r"\bcache\s+l'interface\b"]},
    {"intent": HIDE_UI, "langs": ["ar"],
     "patterns": [r"اخفاء\s+الواجهه"]},
    {"intent": HELP, "langs": ["en"],
     "patterns": [r"\b(?:help|what can you do|help me)\b"]},
    {"intent": HELP, "langs": ["fr"],
     "patterns": [r"\baide\b", r"\bque\s+peux\s*[- ]tu\s+faire\b"]},
    {"intent": HELP, "langs": ["ar"],
     "patterns": [r"مساعده|المساعده"]},
    {"intent": PROFILE, "langs": ["en", "fr", "ar"],
     "patterns": [r"\b(?:switch\s+to|activate|enter)\s+(?P<profile>personal|presentation|media|industrial|medical|accessibility|kiosk|browser|cad|pdf)\s+mode\b"],
     "param": "profile"},
    {"intent": PROFILE, "langs": ["en", "fr", "ar"],
     "patterns": [r"\b(?P<profile>browser|presentation|media|hands\s+busy)\s+mode\b"],
     "param": "profile"},
    # --- copilot / generic intent ------------------------------------------
    {"intent": COPILOT, "langs": ["en"],
     "patterns": [r"\bhkajdj? copilot\b", r"\bask\s+copilot\b", r"\bturn\s+off\s+(?:the\s+)?(?:lights|devices)\b"]},
]


def _prep(text: str) -> str:
    return text.strip().lower()


def _ar_prep(text: str) -> str:
    return _ar_normalize(text.strip())


def parse(text: str, language: str = "en") -> VoiceIntent:
    if not text:
        return VoiceIntent(language=language, raw_text=text)
    lang = language.split("-")[0].lower() if "-" in language else language.lower()
    lang = {"en": "en", "fr": "fr", "ar": "ar"}.get(lang, "en")
    prepared = _ar_prep(text) if lang == "ar" else _prep(text)

    best: VoiceIntent | None = None
    best_score = -1.0
    best_generic: VoiceIntent | None = None
    best_generic_score = -1.0
    for cmd in COMMANDS:
        if lang not in cmd["langs"]:
            continue
        # Bare "open/start/type <anything>" commands are intentionally generic;
        # fixed-phrase commands must win over them ("start presentation",
        # "open settings"), so they are ranked in a separate fallback pool.
        generic = cmd.get("param") in ("app", "text")
        for pattern in cmd["patterns"]:
            m = re.search(pattern, prepared)
            if not m:
                continue
            # score: longer patterns are more specific
            score = len(pattern) + (1.0 if m.end() == len(prepared) else 0.2)
            params = {}
            if cmd.get("param"):
                val = m.group(cmd["param"]).strip()
                if cmd["param"] == "percent":
                    try:
                        params["percent"] = float(val)
                    except ValueError:
                        continue
                elif cmd["param"] in ("app", "text"):
                    params[cmd["param"]] = val
                elif cmd["param"] == "profile":
                    label = val.strip().lower().replace(" ", "_")
                    params["profile"] = {"hands_busy": "hands_busy"}.get(label, label)
            candidate = VoiceIntent(intent=cmd["intent"], params=params,
                                    confidence=0.95, language=lang, raw_text=text)
            if generic:
                if score > best_generic_score:
                    best_generic_score = score
                    best_generic = candidate
            elif score > best_score:
                best_score = score
                best = candidate
    if best is None:
        best = best_generic
    if best is None:
        return VoiceIntent(intent=NONE_INTENT, confidence=0.0, language=lang, raw_text=text)
    return best