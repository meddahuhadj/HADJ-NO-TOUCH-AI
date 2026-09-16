"""Desktop UI language engine.

The dashboard translates at build time and live-retranslates on switch;
dialogs rebuild with the current language on their next open. The chosen
language is persisted per user in ``data_dir() / ui_language.json``.

Codes match the web PWA: "en", "fr", "ar".
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import data_dir

LANGUAGES = ["en", "fr", "ar"]
LANGUAGE_NAMES = {"en": "English", "fr": "Français", "ar": "العربية"}
_DEFAULT_LANGUAGE = "en"
_lock = threading.RLock()
_current: str | None = None
_callbacks: list = []


def _language_path() -> Path:
    return data_dir() / "ui_language.json"


def _load() -> str:
    try:
        p = _language_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            lang = data.get("language", "")
            if lang in LANGUAGES:
                return lang
    except Exception:
        pass
    return _DEFAULT_LANGUAGE


def current_language() -> str:
    global _current
    if _current is None:
        _current = _load()
    return _current


def set_language(code: str) -> str:
    global _current
    if code not in LANGUAGES:
        return current_language()
    with _lock:
        changed = code != _current
        _current = code
        try:
            _language_path().write_text(
                json.dumps({"language": code}, indent=2), encoding="utf-8")
        except Exception:
            pass
    if changed:
        for cb in list(_callbacks):
            try:
                cb(code)
            except Exception:
                pass
    return code


def install(callback) -> None:
    if callback not in _callbacks:
        _callbacks.append(callback)


_FR = {
    "Multimodal contactless control — hands, voice & eyes":
        "Contrôle sans contact multimodal — mains, voix et yeux",
    "🔴 REAL": "🔴 RÉEL",
    "🔵 DEMO MODE": "🔵 MODE DÉMO",
    "Camera preview": "Aperçu caméra",
    "Waiting for a gesture…": "En attente d'un geste…",
    "Camera": "Caméra",
    "Hand Tracking": "Suivi des mains",
    "Voice": "Voix",
    "Gaze (optional)": "Regard (optionnel)",
    "Control": "Contrôle",
    "Lighting": "Éclairage",
    "Camera FPS": "FPS caméra",
    "Tracking": "Suivi",
    "Latency": "Latence",
    "CPU": "CPU",
    "RAM": "RAM",
    "Commands": "Commandes",
    "frames / sec": "images / s",
    "FPS": "FPS",
    "ms": "ms",
    "%": "%",
    "MB": "Mo",
    "per minute": "par minute",
    "Mode:": "Mode :",
    "⛔ STOP NO-TOUCH CONTROL": "⛔ ARRÊTER LE CONTRÔLE SANS TOUCHER",
    "▶ Resume": "▶ Reprendre",
    "⏸ Pause": "⏸ Pause",
    "⏸ Resume": "⏸ Reprendre",
    "📷 Camera: On": "📷 Caméra : On",
    "📷 Camera: Off": "📷 Caméra : Off",
    "🎤 Mic: On": "🎤 Micro : On",
    "🎤 Mic: Off": "🎤 Micro : Off",
    "🕶 Privacy Mode": "🕶 Mode confidentialité",
    "🎯 Calibrate": "🎯 Calibrer",
    "⌨ Keyboard": "⌨ Clavier",
    "✋ Teach My Gesture": "✋ Enseigner mon geste",
    "🐞 Debug": "🐞 Débogage",
    "🧩 Macro Studio": "🧩 Studio Macro",
    "🧪 Test Lab": "🧪 Laboratoire de test",
    "⚙ Settings": "⚙ Paramètres",
    "Activity log": "Journal d'activité",
    "Recent actions": "Actions récentes",
    "Lighting: {lighting}": "Éclairage : {lighting}",
    "Camera running": "Caméra active",
    "Camera unavailable": "Caméra indisponible",
    "Tracking paused": "Suivi en pause",
    "Hand model ready": "Modèle main prêt",
    "Loading hand model (MediaPipe)…": "Chargement du modèle main (MediaPipe)…",
    "Gaze tracking disabled": "Suivi du regard désactivé",
    "Face model error: {err}": "Erreur du modèle visage : {err}",
    "Face model loading…": "Chargement du modèle visage…",
    "Gaze active (tracking your eyes)": "Regard actif (suivi de vos yeux)",
    "Gaze ready — face not in view": "Regard prêt — visage hors champ",
    "⛔ EMERGENCY STOP — press Resume or CTRL+ALT+H to re-enable":
        "⛔ ARRÊT D'URGENCE — appuyez sur Reprendre ou CTRL+ALT+H pour réactiver",
    "✓ Control re-enabled": "✓ Contrôle réactivé",
    "👤 Personal": "👤 Personnel",
    "📊 Presentation": "📊 Présentation",
    "🎬 Media": "🎬 Média",
    "⚙️ Industrial": "⚙️ Industriel",
    "🏥 Medical": "🏥 Médical",
    "♿ Accessibility": "♿ Accessibilité",
    "📟 Kiosk": "📟 Kiosque",
    "🌐 Browser": "🌐 Navigateur",
    "📐 CAD": "📐 CAO",
    "📄 PDF": "📄 PDF",
    "🧤 Hands Busy": "🧤 Mains occupées",
    "🤖 AI Copilot": "🤖 Copilote IA",
    "✨ Custom": "✨ Personnalisé",
    "&Control": "&Contrôle",
    "&View": "&Affichage",
    "&Help": "&Aide",
    "Camera On/Off": "Caméra On/Off",
    "Microphone On/Off": "Microphone On/Off",
    "Pause tracking": "Mettre le suivi en pause",
    "Privacy mode": "Mode confidentialité",
    "Emergency stop": "Arrêt d'urgence",
    "Resume control": "Reprendre le contrôle",
    "Calibration wizard": "Assistant de calibration",
    "Virtual keyboard": "Clavier virtuel",
    "Teach my gesture": "Enseigner mon geste",
    "Macro Studio & custom commands": "Studio Macro & commandes personnalisées",
    "Test Lab": "Laboratoire de test",
    "Settings Center": "Centre de paramètres",
    "Debug panel": "Panneau de débogage",
    "Quick start": "Démarrage rapide",
    "Quick guide": "Guide rapide",
    "About": "À propos",
    "Show interface": "Afficher l'interface",
    "Calibrate": "Calibrer",
    "Quit": "Quitter",
    "Confirm action": "Confirmer l'action",
    "Confirm action?": "Confirmer l'action ?",
    "Startup error": "Erreur de démarrage",
    "HADJ NO-TOUCH AI could not start.\n\n{err}\n\nDetails are in the app log file.":
        "HADJ NO-TOUCH AI n'a pas pu démarrer.\n\n{err}\n\nLes détails sont dans le fichier journal de l'application.",
    "Camera": "Caméra",
    "Camera unavailable ({err}).\n\nGestures are offline but voice can still be used.":
        "Caméra indisponible ({err}).\n\nLes gestes sont hors ligne mais la voix reste utilisable.",
    "First run": "Premier lancement",
    "Set up your virtual interaction plane?":
        "Configurer votre plan d'interaction virtuel ?",
    "Calibrate now so the webcam fingertip maps correctly onto your screen. You can recalibrate any time from the dashboard.":
        "Calibrez maintenant pour que le bout du doigt caméra corresponde correctement à votre écran. Vous pouvez recalibrer à tout moment depuis le tableau de bord.",
    "Calibrate now": "Calibrer maintenant",
    "Later": "Plus tard",
    "Still running in the system tray (gestures remain active).":
        "Toujours actif dans la barre d'état système (les gestes restent actifs).",
    "Quick guide": "Guide rapide",
    "POINT → move cursor": "POINT → déplacer le curseur",
    "PINCH (thumb+index) → left click": "PINCE (pouce+index) → clic gauche",
    "Double pinch → double click": "Double pince → double clic",
    "Thumb + middle → right click": "Pouce + majeur → clic droit",
    "Pinch + move → drag": "Pince + déplacement → glisser",
    "Open palm + move vertically → scroll": "Paume ouverte + mouvement vertical → défilement",
    "Swipe → next/previous (slides, pages, tracks, tabs)":
        "Balayage → suivant/précédent (diapositives, pages, pistes, onglets)",
    "Open palm held 1-2 s → pause interaction":
        "Paume ouverte maintenue 1-2 s → pause de l'interaction",
    "Fist held → interaction lock": "Poing maintenu → verrouillage de l'interaction",
    "Voice: 'open chrome', 'next page', 'volume 50 percent', 'close this window', 'take screenshot' — English, French, Arabic.":
        "Voix : « open chrome », « next page », « volume 50 percent », « close this window », « take screenshot » — anglais, français, arabe.",
    "Emergency stop: CTRL + ALT + H": "Arrêt d'urgence : CTRL + ALT + H",
    "HADJ NO-TOUCH AI — a multimodal AI platform for controlling a computer without touching it (hands, voice, optional gaze).\n\nPrivacy-first: camera and microphone processing stays local by default; no frames are uploaded or recorded.\n\nThis is a virtual/contactless interaction layer, not a touchscreen.":
        "HADJ NO-TOUCH AI — plateforme IA multimodale pour contrôler un ordinateur sans le toucher (mains, voix, regard optionnel).\n\nConfidentialité d'abord : le traitement de la caméra et du micro reste local par défaut ; aucune image n'est envoyée ni enregistrée.\n\nC'est une couche d'interaction virtuelle/sans contact, pas un écran tactile.",
    "Macro Studio & Custom Commands": "Studio Macro & commandes personnalisées",
    "Macros (voice / gesture / button)": "Macros (voix / geste / bouton)",
    "Custom voice commands": "Commandes vocales personnalisées",
    "Close": "Fermer",
    "Voice phrase": "Phrase vocale",
    "Gesture": "Geste",
    "Button": "Bouton",
    "e.g. 'go to work' / CIRCLE_CW / quick_action": "ex. « go to work » / CIRCLE_CW / quick_action",
    "One registered action per line, optional key=value params.\nExamples:\n  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50":
        "Une action enregistrée par ligne, paramètres facultatifs clé=valeur.\nExemples :\n  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50",
    "optional description": "description facultative",
    "Name": "Nom",
    "Trigger": "Déclencheur",
    "Value": "Valeur",
    "Actions": "Actions",
    "Description": "Description",
    "New": "Nouveau",
    "Save": "Enregistrer",
    "Delete": "Supprimer",
    "Run now": "Exécuter maintenant",
    "phrase, e.g. 'boost volume'": "phrase, ex. « boost volume »",
    "optional params: app=chrome, percent=50": "paramètres facultatifs : app=chrome, percent=50",
    "Phrase": "Phrase",
    "Action": "Action",
    "Params": "Paramètres",
    "Add": "Ajouter",
    "Remove": "Retirer",
    "Macro Studio": "Studio Macro",
    "A macro needs a name.": "Une macro doit avoir un nom.",
    "Add at least one action line, e.g.  OPEN_APP app=chrome":
        "Ajoutez au moins une ligne d'action, ex. OPEN_APP app=chrome",
    "Custom Commands": "Commandes personnalisées",
    "Enter a phrase and pick an action.": "Saisissez une phrase et choisissez une action.",
    "AI Planner suggestion": "Suggestion du planificateur IA",
    "For: ": "Pour : ",
    "Proposed actions": "Actions proposées",
    "Nothing runs yet — every step still passes the Safety Engine gates.":
        "Rien ne s'exécute encore — chaque étape reste soumise aux portes du moteur de sécurité.",
    "Execute plan": "Exécuter le plan",
    "Cancel": "Annuler",
    "HADJ Test Lab": "Laboratoire de test HADJ",
    "Self-diagnostics (simulated inputs, no hardware needed)":
        "Auto-diagnostics (entrées simulées, aucun matériel requis)",
    "Run all tests": "Lancer tous les tests",
    "Passed {passed} · Skipped {skipped} · Failed {failed}":
        "Réussis {passed} · Ignorés {skipped} · Échoués {failed}",
    "Settings Center": "Centre de paramètres",
    "Safety": "Sécurité",
    "Confirmation level": "Niveau de confirmation",
    "None — run CONFIRM actions freely (CRITICAL still asks)":
        "Aucun — exécuter librement les actions CONFIRM (CRITIQUE demande toujours)",
    "Smart — confirm sensitive actions": "Intelligent — confirmer les actions sensibles",
    "All — confirm every action except emergency/safety toggles":
        "Tout — confirmer chaque action sauf les bascules d'urgence/sécurité",
    "Demo mode blocks every real OS action and simulates it loudly.":
        "Le mode démo bloque toute action réelle sur le système et la simule bruyamment.",
    "Voice recognition": "Reconnaissance vocale",
    "Language": "Langue",
    "Recognized commands switch language (open/next/volume… in EN, FR or AR). Applied on save — the voice engine restarts with the new language.":
        "Les commandes reconnues changent de langue (open/next/volume… en EN, FR ou AR). Appliqué lors de l'enregistrement — le moteur vocal redémarre avec la nouvelle langue.",
    "Head control (FaceMesh)": "Contrôle de la tête (FaceMesh)",
    "Enable head-direction actions": "Activer les actions par direction de la tête",
    "Sensitivity": "Sensibilité",
    "Hold (ms)": "Maintien (ms)",
    "Cooldown (ms)": "Temps de recharge (ms)",
    "Turn left/right → previous/next (slide, page, track). Up/down → volume / zoom depending on context. Hold the direction, release to repeat.":
        "Tourner à gauche/droite → précédent/suivant (diapositive, page, piste). Haut/bas → volume / zoom selon le contexte. Maintenez la direction, relâchez pour répéter.",
    "Gaze tracking (experimental)": "Suivi du regard (expérimental)",
    "Enable gaze estimation (optional)": "Activer l'estimation du regard (optionnel)",
    "Uses iris position (FaceMesh, local). Gaze confirms pinch/click on the thing you look at, and feeds the AI Copilot context.":
        "Utilise la position de l'iris (FaceMesh, local). Le regard confirme la pince/clic sur ce que vous regardez et alimente le contexte du copilote IA.",
    "Demo mode": "Mode démo",
    "Start the app in demo mode": "Démarrer l'application en mode démo",
    "HADJ NO-TOUCH AI — quick start": "HADJ NO-TOUCH AI — démarrage rapide",
    "<b>Hands</b><br>☝️ POINT → move cursor<br>🤏 PINCH (thumb+index) → left click · hold + move → drag<br>✌️ Thumb + middle → right click · double pinch → double click<br>🖐 PALM + move vertically → scroll · swipe → next/previous<br>✊ FIST held → lock · PALM held → pause<br><br><b>Voice</b> (EN / FR / AR)<br>'open chrome' · 'next page' · 'volume 50 percent'<br>'close this window' · 'take screenshot' · 'switch profile'\n\n<b>Safety</b><br>🔴 REAL mode acts on your computer; 🔵 DEMO simulates nothing.<br>Sensitive actions ask for confirmation first.<br>Emergency stop: <b>CTRL + ALT + H</b>":
        "<b>Mains</b><br>☝️ POINT → déplacer le curseur<br>🤏 PINCE (pouce+index) → clic gauche · maintenir + déplacer → glisser<br>✌️ Pouce + majeur → clic droit · double pince → double clic<br>🖐 PAUME + mouvement vertical → défilement · balayage → suivant/précédent<br>✊ POING maintenu → verrou · PAUME maintenue → pause<br><br><b>Voix</b> (EN / FR / AR)<br>« open chrome » · « next page » · « volume 50 percent »<br>« close this window » · « take screenshot » · « switch profile »\n\n<b>Sécurité</b><br>🔴 Le mode RÉEL agit sur votre ordinateur ; 🔵 DÉMO ne simule rien.<br>Les actions sensibles demandent confirmation d'abord.<br>Arrêt d'urgence : <b>CTRL + ALT + H</b>",
    "Got it": "Compris",
    "HADJ — Calibration Wizard": "HADJ — Assistant de calibration",
    "🎯 Virtual Interaction Plane — Calibration": "🎯 Plan d'interaction virtuel — Calibration",
    "A standard webcam provides an estimated spatial mapping — this creates a virtual/contactless interaction plane, not a physical touchscreen.":
        "Une webcam standard fournit une cartographie spatiale estimée — cela crée un plan d'interaction virtuel/sans contact, pas un écran tactile physique.",
    "Starting camera preview…": "Démarrage de l'aperçu caméra…",
    "✔ Confirm point": "✔ Confirmer le point",
    "Skip (estimate)": "Ignorer (estimation)",
    "Calibration": "Calibration",
    "Calibration complete and saved locally.\nMove your fingertip — the cursor should follow. Recalibrate any time from the dashboard.":
        "Calibration terminée et enregistrée localement.\nDéplacez votre bout du doigt — le curseur devrait suivre. Vous pouvez recalibrer à tout moment depuis le tableau de bord.",
    "No camera frame available": "Aucune image caméra disponible",
    "Preview unavailable": "Aperçu indisponible",
    "Mapped — verifying cursor…": "Cartographié — vérification du curseur…",
    "Top-left": "Haut-gauche",
    "Top-right": "Haut-droit",
    "Bottom-right": "Bas-droit",
    "Bottom-left": "Bas-gauche",
    "Center": "Centre",
    "Aim your index fingertip at the TOP-LEFT corner, hold still and pinch (or press “Confirm point”).":
        "Visez le coin HAUT-GAUCHE avec votre index, restez immobile et pincez (ou appuyez sur « Confirmer le point »).",
    "Now the TOP-RIGHT corner — point and pinch.": "Maintenant le coin HAUT-DROIT — pointez et pincez.",
    "Bottom-RIGHT corner — point and pinch.": "Coin BAS-DROIT — pointez et pincez.",
    "Bottom-LEFT corner — point and pinch.": "Coin BAS-GAUCHE — pointez et pincez.",
    "Center verification — point at the middle of the screen and pinch.":
        "Vérification au centre — pointez le milieu de l'écran et pincez.",
    "HADJ Debug Panel": "Panneau de débogage HADJ",
    "Pipeline": "Pipeline",
    "Tracking FPS": "FPS de suivi",
    "Latency (ms)": "Latence (ms)",
    "Camera active": "Caméra active",
    "Hand present": "Main présente",
    "Hand confidence": "Confiance main",
    "Gesture": "Geste",
    "Gesture confidence": "Confiance geste",
    "Fingertip idx (norm)": "Index bout du doigt (norm)",
    "Cursor (px)": "Curseur (px)",
    "Gaze (x,y)": "Regard (x,y)",
    "Gaze match": "Correspondance regard",
    "Voice status": "État voix",
    "Last voice": "Dernière voix",
    "Profile": "Profil",
    "Context": "Contexte",
    "Active app": "Application active",
    "Pinch hold": "Maintien pince",
    "Locked": "Verrouillé",
    "Custom gestures": "Gestes personnalisés",
    "Calibration": "Calibration",
    "Hand model": "Modèle main",
    "Face model": "Modèle visage",
    "Diagnostics": "Diagnostics",
    "Record diagnostics to file": "Enregistrer les diagnostics dans un fichier",
    "Stop diagnostics recording": "Arrêter l'enregistrement des diagnostics",
    "Save log now": "Enregistrer le journal maintenant",
    "Diagnostics saved (text only): {path}": "Diagnostics enregistrés (texte uniquement) : {path}",
    "ready": "prêt",
    "loading…": "chargement…",
    "HADJ — Teach My Gesture": "HADJ — Enseigner mon geste",
    "✋ AI Gesture Trainer": "✋ Entraîneur de gestes IA",
    "Perform the same movement several times while your hand is visible. The pattern is learned from the hand trajectory and stored only on this computer.":
        "Effectuez le même mouvement plusieurs fois pendant que votre main est visible. Le motif est appris à partir de la trajectoire de la main et stocké uniquement sur cet ordinateur.",
    "Gesture name:": "Nom du geste :",
    "e.g. 'Open calculator'": "ex. « Ouvrir la calculatrice »",
    "Action type:": "Type d'action :",
    "Action value:": "Valeur d'action :",
    "e.g. chrome, VOLUME_UP, next page…": "ex. chrome, VOLUME_UP, next page…",
    "Samples": "Échantillons",
    "Record sample (1.2 s)": "Enregistrer un échantillon (1,2 s)",
    "Clear": "Effacer",
    "Saved gestures": "Gestes enregistrés",
    "Delete selected": "Supprimer la sélection",
    "Save gesture": "Enregistrer le geste",
    "Sample {index} ✓": "Échantillon {index} ✓",
    "{count} sample(s) recorded": "{count} échantillon(s) enregistré(s)",
    "Recording… keep your hand visible": "Enregistrement… gardez votre main visible",
    "Launch an application": "Lancer une application",
    "Type text": "Taper du texte",
    "Switch to a profile": "Changer de profil",
    "Open documents folder": "Ouvrir le dossier documents",
    "Take a screenshot": "Prendre une capture d'écran",
    "Custom intent (e.g. VOLUME_UP)": "Intention personnalisée (ex. VOLUME_UP)",
    "Recording": "Enregistrement",
    "No valid hand trajectory captured. Make sure your hand is clearly visible to the webcam.":
        "Aucune trajectoire de main valide capturée. Assurez-vous que votre main est clairement visible par la webcam.",
    "Save": "Enregistrer",
    "Give the gesture a name.": "Donnez un nom au geste.",
    "Record at least 2 samples of the movement so the AI can learn it.":
        "Enregistrez au moins 2 échantillons du mouvement pour que l'IA puisse l'apprendre.",
    "Save failed": "Échec de l'enregistrement",
    "Saved": "Enregistré",
    "Gesture '{name}' saved → {action}.\nPerform it any time while your hand is visible to trigger the action.":
        "Geste « {name} » enregistré → {action}.\nExécutez-le à tout moment, main visible, pour déclencher l'action.",
    "Deleted custom gesture '{name}'": "Geste personnalisé « {name} » supprimé",
    "assigned to dashboard": "assigné au tableau de bord",
    "(unassigned)": "(non assigné)",
}

_AR = {
    "Multimodal contactless control — hands, voice & eyes":
        "تحكم لامسي متعدد الوسائط — يد، صوت وعينان",
    "🔴 REAL": "🔴 حقيقي",
    "🔵 DEMO MODE": "🔵 وضع تجريبي",
    "Camera preview": "معاينة الكاميرا",
    "Waiting for a gesture…": "في انتظار إيماءة…",
    "Camera": "الكاميرا",
    "Hand Tracking": "تتبع اليد",
    "Voice": "الصوت",
    "Gaze (optional)": "النظر (اختياري)",
    "Control": "التحكم",
    "Lighting": "الإضاءة",
    "Camera FPS": "إطارات الكاميرا",
    "Tracking": "التتبع",
    "Latency": "الاستجابة",
    "CPU": "المعالج",
    "RAM": "الذاكرة",
    "Commands": "الأوامر",
    "frames / sec": "إطار / ث",
    "FPS": "إطار/ث",
    "ms": "ملليثانية",
    "%": "٪",
    "MB": "ميغابايت",
    "per minute": "في الدقيقة",
    "Mode:": "الوضع:",
    "⛔ STOP NO-TOUCH CONTROL": "⛔ إيقاف التحكم اللامسي",
    "▶ Resume": "▶ استئناف",
    "⏸ Pause": "⏸ إيقاف مؤقت",
    "⏸ Resume": "⏸ استئناف",
    "📷 Camera: On": "📷 الكاميرا: تعمل",
    "📷 Camera: Off": "📷 الكاميرا: متوقفة",
    "🎤 Mic: On": "🎤 الميكروفون: يعمل",
    "🎤 Mic: Off": "🎤 الميكروفون: متوقف",
    "🕶 Privacy Mode": "🕶 وضع الخصوصية",
    "🎯 Calibrate": "🎯 معايرة",
    "⌨ Keyboard": "⌨ لوحة المفاتيح",
    "✋ Teach My Gesture": "✋ علم إيماءتي",
    "🐞 Debug": "🐞 تصحيح",
    "🧩 Macro Studio": "🧩 استوديو الماكرو",
    "🧪 Test Lab": "🧪 مختبر الاختبار",
    "⚙ Settings": "⚙ الإعدادات",
    "Activity log": "سجل النشاط",
    "Recent actions": "الإجراءات الأخيرة",
    "Lighting: {lighting}": "الإضاءة: {lighting}",
    "Camera running": "الكاميرا تعمل",
    "Camera unavailable": "الكاميرا غير متاحة",
    "Tracking paused": "التتبع متوقف مؤقتًا",
    "Hand model ready": "نموذج اليد جاهز",
    "Loading hand model (MediaPipe)…": "تحميل نموذج اليد (MediaPipe)…",
    "Gaze tracking disabled": "تتبع النظر معطّل",
    "Face model error: {err}": "خطأ نموذج الوجه: {err}",
    "Face model loading…": "تحميل نموذج الوجه…",
    "Gaze active (tracking your eyes)": "النظر نشط (تتبع عينيك)",
    "Gaze ready — face not in view": "النظر جاهز — الوجه خارج الرؤية",
    "⛔ EMERGENCY STOP — press Resume or CTRL+ALT+H to re-enable":
        "⛔ إيقاف طارئ — اضغط استئناف أو CTRL+ALT+H لإعادة التفعيل",
    "✓ Control re-enabled": "✓ أعيد تفعيل التحكم",
    "👤 Personal": "👤 شخصي",
    "📊 Presentation": "📊 عرض",
    "🎬 Media": "🎬 وسائط",
    "⚙️ Industrial": "⚙️ صناعي",
    "🏥 Medical": "🏥 طبي",
    "♿ Accessibility": "♿ إتاحة الوصول",
    "📟 Kiosk": "📟 كشك",
    "🌐 Browser": "🌐 متصفح",
    "📐 CAD": "📐 تصميم",
    "📄 PDF": "📄 PDF",
    "🧤 Hands Busy": "🧤 اليدان مشغولتان",
    "🤖 AI Copilot": "🤖 مساعد ذكاء اصطناعي",
    "✨ Custom": "✨ مخصص",
    "&Control": "&التحكم",
    "&View": "&عرض",
    "&Help": "&مساعدة",
    "Camera On/Off": "تشغيل/إيقاف الكاميرا",
    "Microphone On/Off": "تشغيل/إيقاف الميكروفون",
    "Pause tracking": "إيقاف التتبع مؤقتًا",
    "Privacy mode": "وضع الخصوصية",
    "Emergency stop": "إيقاف طارئ",
    "Resume control": "استئناف التحكم",
    "Calibration wizard": "معالج المعايرة",
    "Virtual keyboard": "لوحة المفاتيح الافتراضية",
    "Teach my gesture": "علم إيماءتي",
    "Macro Studio & custom commands": "استوديو الماكرو والأوامر المخصصة",
    "Test Lab": "مختبر الاختبار",
    "Settings Center": "مركز الإعدادات",
    "Debug panel": "لوحة التصحيح",
    "Quick start": "بداية سريعة",
    "Quick guide": "دليل سريع",
    "About": "حول",
    "Show interface": "إظهار الواجهة",
    "Calibrate": "معايرة",
    "Quit": "خروج",
    "Confirm action": "تأكيد الإجراء",
    "Confirm action?": "تأكيد الإجراء ؟",
    "Startup error": "خطأ بدء التشغيل",
    "HADJ NO-TOUCH AI could not start.\n\n{err}\n\nDetails are in the app log file.":
        "تعذر تشغيل HADJ NO-TOUCH AI.\n\n{err}\n\nالتفاصيل في ملف سجل التطبيق.",
    "Camera": "الكاميرا",
    "Camera unavailable ({err}).\n\nGestures are offline but voice can still be used.":
        "الكاميرا غير متاحة ({err}).\n\nالإيماءات غير متاحة لكن الصوت ما زال يعمل.",
    "First run": "أول تشغيل",
    "Set up your virtual interaction plane?": "تهيئة مستوى التفاعل الافتراضي؟",
    "Calibrate now so the webcam fingertip maps correctly onto your screen. You can recalibrate any time from the dashboard.":
        "عاير الآن لكي يطابق طرف إصبع الكاميرا شاشتك بشكل صحيح. يمكنك إعادة المعايرة في أي وقت من لوحة التحكم.",
    "Calibrate now": "عاير الآن",
    "Later": "لاحقًا",
    "Still running in the system tray (gestures remain active).":
        "ما زال يعمل في علبة النظام (الإيماءات تبقى نشطة).",
    "Quick guide": "دليل سريع",
    "POINT → move cursor": "POINT ← تحريك المؤشر",
    "PINCH (thumb+index) → left click": "قرصة (إبهام+سبابة) ← نقرة يسرى",
    "Double pinch → double click": "قرصة مزدوجة ← نقرة مزدوجة",
    "Thumb + middle → right click": "إبهام + وسطى ← نقرة يمنى",
    "Pinch + move → drag": "قرصة + تحريك ← سحب",
    "Open palm + move vertically → scroll": "كف مفتوح + حركة عمودية ← تمرير",
    "Swipe → next/previous (slides, pages, tracks, tabs)":
        "سحبة ← التالي/السابق (شرائح، صفحات، مقاطع، علامات تبويب)",
    "Open palm held 1-2 s → pause interaction":
        "كف مفتوح لمدة 1-2 ث ← إيقاف التفاعل مؤقتًا",
    "Fist held → interaction lock": "قبضة ممسكة ← قفل التفاعل",
    "Voice: 'open chrome', 'next page', 'volume 50 percent', 'close this window', 'take screenshot' — English, French, Arabic.":
        "الصوت: «open chrome» · «next page» · «volume 50 percent» · «close this window» · «take screenshot» — إنجليزي، فرنسي، عربي.",
    "Emergency stop: CTRL + ALT + H": "إيقاف طارئ: CTRL + ALT + H",
    "HADJ NO-TOUCH AI — a multimodal AI platform for controlling a computer without touching it (hands, voice, optional gaze).\n\nPrivacy-first: camera and microphone processing stays local by default; no frames are uploaded or recorded.\n\nThis is a virtual/contactless interaction layer, not a touchscreen.":
        "HADJ NO-TOUCH AI — منصة ذكاء اصطناعي متعددة الوسائط للتحكم بالحاسوب دون لمسه (يد، صوت، ونظر اختياري).\n\nالخصوصية أولًا: معالجة الكاميرا والميكروفون تبقى محلية افتراضيًا؛ لا تُرفع أي إطارات ولا تُسجل.\n\nهذه طبقة تفاعل افتراضية/لامسية، وليست شاشة لمس.",
    "Macro Studio & Custom Commands": "استوديو الماكرو والأوامر المخصصة",
    "Macros (voice / gesture / button)": "ماكرو (صوت / إيماءة / زر)",
    "Custom voice commands": "أوامر صوتية مخصصة",
    "Close": "إغلاق",
    "Voice phrase": "عبارة صوتية",
    "Gesture": "إيماءة",
    "Button": "زر",
    "e.g. 'go to work' / CIRCLE_CW / quick_action": "مثل «go to work» / CIRCLE_CW / quick_action",
    "One registered action per line, optional key=value params.\nExamples:\n  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50":
        "إجراء مسجل واحد لكل سطر، معاملات اختيارية مفتاح=قيمة.\nأمثلة:\n  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50",
    "optional description": "وصف اختياري",
    "Name": "الاسم",
    "Trigger": "المُطلق",
    "Value": "القيمة",
    "Actions": "الإجراءات",
    "Description": "الوصف",
    "New": "جديد",
    "Save": "حفظ",
    "Delete": "حذف",
    "Run now": "تشغيل الآن",
    "phrase, e.g. 'boost volume'": "عبارة، مثل «boost volume»",
    "optional params: app=chrome, percent=50": "معاملات اختيارية: app=chrome, percent=50",
    "Phrase": "العبارة",
    "Action": "الإجراء",
    "Params": "المعاملات",
    "Add": "إضافة",
    "Remove": "إزالة",
    "Macro Studio": "استوديو الماكرو",
    "A macro needs a name.": "يجب أن تحمل الماكرو اسمًا.",
    "Add at least one action line, e.g.  OPEN_APP app=chrome":
        "أضف سطر إجراء واحدًا على الأقل، مثل OPEN_APP app=chrome",
    "Custom Commands": "الأوامر المخصصة",
    "Enter a phrase and pick an action.": "أدخل عبارة واختر إجراءً.",
    "AI Planner suggestion": "اقتراح المخطط الذكي",
    "For: ": "من أجل: ",
    "Proposed actions": "الإجراءات المقترحة",
    "Nothing runs yet — every step still passes the Safety Engine gates.":
        "لا شيء يعمل بعد — كل خطوة تمر عبر بوابات محرك الأمان.",
    "Execute plan": "تنفيذ الخطة",
    "Cancel": "إلغاء",
    "HADJ Test Lab": "مختبر اختبار HADJ",
    "Self-diagnostics (simulated inputs, no hardware needed)":
        "تشخيص ذاتي (مدخلات محاكاة، بلا حاجة لعتاد)",
    "Run all tests": "تشغيل كل الاختبارات",
    "Passed {passed} · Skipped {skipped} · Failed {failed}":
        "نجح {passed} · تخطّي {skipped} · فشل {failed}",
    "Settings Center": "مركز الإعدادات",
    "Safety": "الأمان",
    "Confirmation level": "مستوى التأكيد",
    "None — run CONFIRM actions freely (CRITICAL still asks)":
        "لا شيء — تنفيذ إجراءات CONFIRM بحرية (CRITICAL يطلب دائمًا)",
    "Smart — confirm sensitive actions": "ذكي — تأكيد الإجراءات الحساسة",
    "All — confirm every action except emergency/safety toggles":
        "الكل — تأكيد كل إجراء عدا مفاتيح الطوارئ/الأمان",
    "Demo mode blocks every real OS action and simulates it loudly.":
        "الوضع التجريبي يحجب كل إجراء حقيقي على النظام ويحاكيه بصورة واضحة.",
    "Voice recognition": "التعرف على الصوت",
    "Language": "اللغة",
    "Recognized commands switch language (open/next/volume… in EN, FR or AR). Applied on save — the voice engine restarts with the new language.":
        "الأوامر المعترف بها تتبدل لغتها (open/next/volume… بالإنجليزية أو الفرنسية أو العربية). يُطبَّق عند الحفظ — يعيد محرك الصوت تشغيله باللغة الجديدة.",
    "Head control (FaceMesh)": "التحكم بالرأس (FaceMesh)",
    "Enable head-direction actions": "تفعيل إجراءات توجيه الرأس",
    "Sensitivity": "الحساسية",
    "Hold (ms)": "الاحتفاظ (ملليثانية)",
    "Cooldown (ms)": "الاستراحة (ملليثانية)",
    "Turn left/right → previous/next (slide, page, track). Up/down → volume / zoom depending on context. Hold the direction, release to repeat.":
        "يسار/يمين ← السابق/التالي (شريحة، صفحة، مقطع). أعلى/أسفل ← الصوت / التقريب حسب السياق. امسك الاتجاه وأفلت للتكرار.",
    "Gaze tracking (experimental)": "تتبع النظر (تجريبي)",
    "Enable gaze estimation (optional)": "تفعيل تقدير النظر (اختياري)",
    "Uses iris position (FaceMesh, local). Gaze confirms pinch/click on the thing you look at, and feeds the AI Copilot context.":
        "يستخدم موضع القزحية (FaceMesh، محلي). النظر يؤكد القرصة/النقرة على ما تنظر إليه، ويغذي سياق المساعد الذكي.",
    "Demo mode": "الوضع التجريبي",
    "Start the app in demo mode": "بدء التطبيق بالوضع التجريبي",
    "HADJ NO-TOUCH AI — quick start": "HADJ NO-TOUCH AI — بداية سريعة",
    "<b>Hands</b><br>☝️ POINT → move cursor<br>🤏 PINCH (thumb+index) → left click · hold + move → drag<br>✌️ Thumb + middle → right click · double pinch → double click<br>🖐 PALM + move vertically → scroll · swipe → next/previous<br>✊ FIST held → lock · PALM held → pause<br><br><b>Voice</b> (EN / FR / AR)<br>'open chrome' · 'next page' · 'volume 50 percent'<br>'close this window' · 'take screenshot' · 'switch profile'\n\n<b>Safety</b><br>🔴 REAL mode acts on your computer; 🔵 DEMO simulates nothing.<br>Sensitive actions ask for confirmation first.<br>Emergency stop: <b>CTRL + ALT + H</b>":
        "<b>اليد</b><br>☝️ POINT ← تحريك المؤشر<br>🤏 قرصة (إبهام+سبابة) ← نقرة يسرى · إمساك + تحريك ← سحب<br>✌️ إبهام + وسطى ← نقرة يمنى · قرصة مزدوجة ← نقرة مزدوجة<br>🖐 كف + حركة عمودية ← تمرير · سحبة ← التالي/السابق<br>✊ قبضة ← قفل · كف ← إيقاف مؤقت<br><br><b>الصوت</b> (EN / FR / AR)<br>«open chrome» · «next page» · «volume 50 percent»<br>«close this window» · «take screenshot» · «switch profile»\n\n<b>الأمان</b><br>🔴 الوضع الحقيقي يتحكم بجهازك؛ 🔵 التجريبي لا يحاكي شيئًا.<br>الإجراءات الحساسة تطلب تأكيدًا أولًا.<br>إيقاف طارئ: <b>CTRL + ALT + H</b>",
    "Got it": "فهمت",
    "HADJ — Calibration Wizard": "HADJ — معالج المعايرة",
    "🎯 Virtual Interaction Plane — Calibration": "🎯 مستوى التفاعل الافتراضي — المعايرة",
    "A standard webcam provides an estimated spatial mapping — this creates a virtual/contactless interaction plane, not a physical touchscreen.":
        "الكاميرا المعتادة توفر تخطيطًا مكانيًا تقديريًا — ينشئ ذلك مستوى تفاعل افتراضيًا/لامسيًا، وليس شاشة لمس فعلية.",
    "Starting camera preview…": "بدء معاينة الكاميرا…",
    "✔ Confirm point": "✔ تأكيد النقطة",
    "Skip (estimate)": "تخطي (تقدير)",
    "Calibration": "المعايرة",
    "Calibration complete and saved locally.\nMove your fingertip — the cursor should follow. Recalibrate any time from the dashboard.":
        "اكتملت المعايرة وحُفظت محليًا.\nحرّك طرف إصبعك — يجب أن يتبع المؤشر. يمكنك إعادة المعايرة وقتما شئت من لوحة التحكم.",
    "No camera frame available": "لا يوجد إطار كاميرا متاح",
    "Preview unavailable": "المعاينة غير متاحة",
    "Mapped — verifying cursor…": "تم التخطيط — جارٍ التحقق من المؤشر…",
    "Top-left": "أعلى يسار",
    "Top-right": "أعلى يمين",
    "Bottom-right": "أسفل يمين",
    "Bottom-left": "أسفل يسار",
    "Center": "المركز",
    "Aim your index fingertip at the TOP-LEFT corner, hold still and pinch (or press “Confirm point”).":
        "وجّه طرف إصبعك السبابة إلى الزاوية العلوية اليسرى، اثبت واقرص (أو اضغط «تأكيد النقطة»).",
    "Now the TOP-RIGHT corner — point and pinch.": "الآن الزاوية العلوية اليمنى — أشر واقرص.",
    "Bottom-RIGHT corner — point and pinch.": "الزاوية السفلية اليمنى — أشر واقرص.",
    "Bottom-LEFT corner — point and pinch.": "الزاوية السفلية اليسرى — أشر واقرص.",
    "Center verification — point at the middle of the screen and pinch.":
        "التحقق المركزي — أشر إلى منتصف الشاشة واقرص.",
    "HADJ Debug Panel": "لوحة تصحيح HADJ",
    "Pipeline": "الخط",
    "Tracking FPS": "إطارات التتبع",
    "Latency (ms)": "الاستجابة (ملليثانية)",
    "Camera active": "كاميرا نشطة",
    "Hand present": "يد حاضرة",
    "Hand confidence": "ثقة اليد",
    "Gesture": "الإيماءة",
    "Gesture confidence": "ثقة الإيماءة",
    "Fingertip idx (norm)": "فهرس طرف الإصبع (معياري)",
    "Cursor (px)": "المؤشر (بكسل)",
    "Gaze (x,y)": "النظر (س،ص)",
    "Gaze match": "مطابقة النظر",
    "Voice status": "حالة الصوت",
    "Last voice": "آخر صوت",
    "Profile": "الملف",
    "Context": "السياق",
    "Active app": "التطبيق النشط",
    "Pinch hold": "إمساك القرصة",
    "Locked": "مقفل",
    "Custom gestures": "إيماءات مخصصة",
    "Calibration": "المعايرة",
    "Hand model": "نموذج اليد",
    "Face model": "نموذج الوجه",
    "Diagnostics": "التشخيص",
    "Record diagnostics to file": "تسجيل التشخيص في ملف",
    "Stop diagnostics recording": "إيقاف تسجيل التشخيص",
    "Save log now": "حفظ السجل الآن",
    "Diagnostics saved (text only): {path}": "حُفظ التشخيص (نص فقط): {path}",
    "ready": "جاهز",
    "loading…": "جارٍ التحميل…",
    "HADJ — Teach My Gesture": "HADJ — علم إيماءتي",
    "✋ AI Gesture Trainer": "✋ مدرب الإيماءات بالذكاء الاصطناعي",
    "Perform the same movement several times while your hand is visible. The pattern is learned from the hand trajectory and stored only on this computer.":
        "نفّذ الحركة نفسها عدة مرات بينما يدك مرئية. يتعلم النظام النمط من مسار اليد ويخزنه على هذا الجهاز فقط.",
    "Gesture name:": "اسم الإيماءة:",
    "e.g. 'Open calculator'": "مثل «فتح الآلة الحاسبة»",
    "Action type:": "نوع الإجراء:",
    "Action value:": "قيمة الإجراء:",
    "e.g. chrome, VOLUME_UP, next page…": "مثل chrome, VOLUME_UP, next page…",
    "Samples": "العينات",
    "Record sample (1.2 s)": "تسجيل عينة (1.2 ث)",
    "Clear": "مسح",
    "Saved gestures": "الإيماءات المحفوظة",
    "Delete selected": "حذف المحدد",
    "Save gesture": "حفظ الإيماءة",
    "Sample {index} ✓": "عينة {index} ✓",
    "{count} sample(s) recorded": "{count} عينة (عينات) مسجلة",
    "Recording… keep your hand visible": "جارٍ التسجيل… أبقِ يدك مرئية",
    "Launch an application": "تشغيل تطبيق",
    "Type text": "كتابة نص",
    "Switch to a profile": "التبديل إلى ملف",
    "Open documents folder": "فتح مجلد المستندات",
    "Take a screenshot": "التقاط لقطة شاشة",
    "Custom intent (e.g. VOLUME_UP)": "نية مخصصة (مثل VOLUME_UP)",
    "Recording": "التسجيل",
    "No valid hand trajectory captured. Make sure your hand is clearly visible to the webcam.":
        "لم تُلتقط مسار يد صالح. تأكد من أن يدك ظاهرة بوضوح للكاميرا.",
    "Save": "حفظ",
    "Give the gesture a name.": "أعطِ الإيماءة اسمًا.",
    "Record at least 2 samples of the movement so the AI can learn it.":
        "سجّل عينتين على الأقل من الحركة كي يتعلمها الذكاء الاصطناعي.",
    "Save failed": "فشل الحفظ",
    "Saved": "تم الحفظ",
    "Gesture '{name}' saved → {action}.\nPerform it any time while your hand is visible to trigger the action.":
        "حُفظت الإيماءة «{name}» ← {action}.\nنفّذها في أي وقت ويدك مرئية لتفعيل الإجراء.",
    "Deleted custom gesture '{name}'": "حُذفت الإيماءة المخصصة «{name}»",
    "assigned to dashboard": "مخصصة للوحة التحكم",
    "(unassigned)": "(غير مخصص)",
}

_DICTS = {"fr": _FR, "ar": _AR}


def tr(key: str) -> str:
    lang = current_language()
    if lang == "en":
        return key
    return _DICTS.get(lang, {}).get(key, key)


def trf(key: str, **kw) -> str:
    s = tr(key)
    if kw:
        try:
            s = s.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return s