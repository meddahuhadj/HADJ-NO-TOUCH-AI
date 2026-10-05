"""يولّد بيانات صفحة المساعدة المحلية (help/data.js) ورسوم الإيماءات المتحركة (help/gestures/*.svg).

المصدر الوحيد للأوامر هو config/default_commands.yaml، وللإيماءات ui/hand_poses.py:
المساعدة لا تختلف أبداً عمّا يفهمه التطبيق فعلاً. يُشغَّل بعد تعديل الأوامر:

    python src/help/generate.py

الصفحة تعمل بلا إنترنت وبلا خادم: ملفات ثابتة تُفتح مباشرة في المتصفح.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HELP_DIR = Path(__file__).resolve().parent
SRC = HELP_DIR.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402

from ui.hand_poses import FIST, HAND_EDGES, MIDDLE_PINCH, OPEN, PINCH, POINT, TWO, Pose  # noqa: E402

LANGS = ("ar", "fr", "en")
COMMANDS_YAML = SRC / "config" / "default_commands.yaml"

# عناوين أقسام ملف الأوامر بالترتيب (العنوان العربي في الملف ← الترجمات)
SECTIONS = [
    ("الأمان والتحكم بالتطبيق نفسه", "Sécurité et contrôle de l'application", "Safety and app control"),
    ("الإملاء والشبكة", "Dictée et grille", "Dictation and grid"),
    ("التطبيقات والبحث", "Applications et recherche", "Apps and search"),
    ("النوافذ", "Fenêtres", "Windows"),
    ("التحرير", "Édition", "Editing"),
    ("الفأرة والتمرير", "Souris et défilement", "Mouse and scrolling"),
    ("الصوت والنظام", "Son et système", "Sound and system"),
    ("الوسائط والنوافذ المساعدة", "Médias et outils Windows", "Media and Windows tools"),
    ("ترتيب النافذة الحالية", "Disposition de la fenêtre", "Window layout"),
    ("الشاشات", "Écrans", "Displays"),
    ("أسطح المكتب الافتراضية", "Bureaux virtuels", "Virtual desktops"),
    ("السطوع والوضع الداكن", "Luminosité et mode sombre", "Brightness and dark mode"),
    ("الميكروفون", "Microphone", "Microphone"),
    ("أوامر المتصفح والإنترنت", "Navigateur web", "Web browser"),
    ("أوامر الملفات والمجلدات", "Fichiers et dossiers", "Files and folders"),
    ("أدوات النظام المتقدمة", "Outils système avancés", "Advanced system tools"),
]
_SECTION_RE = re.compile(r"^\s*#\s*-{4,}\s*(.+?)\s*-{4,}\s*$")
_ID_RE = re.compile(r"^\s*-\s*id:\s*(\S+)")


def command_sections(path: Path = COMMANDS_YAML) -> list[dict]:
    """الأوامر مجمّعة حسب أقسام ملف YAML (تُقرأ تعليقات الأقسام من النص نفسه)."""
    text = path.read_text(encoding="utf-8")
    specs = {c["id"]: c for c in yaml.safe_load(text)["commands"]}
    titles = {ar: {"ar": ar, "fr": fr, "en": en} for ar, fr, en in SECTIONS}
    sections: list[dict] = []
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            t = m.group(1)
            sections.append({"title": titles.get(t, {"ar": t, "fr": t, "en": t}), "commands": []})
            continue
        m = _ID_RE.match(line)
        if m and sections:
            c = specs[m.group(1)]
            sections[-1]["commands"].append({
                "id": c["id"],
                "phrases": {lang: list(c.get("phrases", {}).get(lang, [])) for lang in LANGS},
                "dangerous": bool(c.get("dangerous")),
                "always": bool(c.get("always")),
            })
    return [s for s in sections if s["commands"]]


# ============================ رسوم الإيماءات ============================
W, H = 240, 170
DUR = 3.2
INK = "#f1f5f9"
ACCENT = "#22d3ee"
OK = "#4ade80"
WARN = "#f59e0b"
FAINT = "#475569"


class Frame:
    """لحظة في الحركة: وضعية + إزاحة. extra = قيم عناصر إضافية في هذه اللحظة."""

    def __init__(self, t: float, pose: Pose, dx: float = 0, dy: float = 0, **extra):
        self.t, self.pose, self.dx, self.dy, self.extra = t, pose, dx, dy, extra


def _pts(pose: Pose, cx: float, cy: float, unit: float, dx: float, dy: float,
         mirror: bool = False) -> list[tuple[float, float]]:
    s = -1 if mirror else 1
    return [(round(cx + s * x * unit + dx, 1), round(cy + (y - 0.4) * unit + dy, 1)) for x, y in pose]


def _anim(attr: str, values: list, times: list[float]) -> str:
    vals = ";".join(str(v) for v in values)
    kt = ";".join(f"{t:.3f}" for t in times)
    splines = ";".join([".42 0 .58 1"] * (len(times) - 1))
    return (f'<animate attributeName="{attr}" values="{vals}" keyTimes="{kt}" dur="{DUR}s" '
            f'repeatCount="indefinite" calcMode="spline" keySplines="{splines}"/>')


def hand_svg(frames: list[Frame], cx: float, cy: float, unit: float, mirror: bool = False,
             width: float = 6.0) -> str:
    times = [f.t for f in frames]
    pts = [_pts(f.pose, cx, cy, unit, f.dx, f.dy, mirror) for f in frames]
    out = [f'<g stroke="{INK}" stroke-width="{width}" stroke-linecap="round" fill="none">']
    for a, b in HAND_EDGES:
        out.append(f'<line x1="{pts[0][a][0]}" y1="{pts[0][a][1]}" x2="{pts[0][b][0]}" y2="{pts[0][b][1]}">'
                   + _anim("x1", [p[a][0] for p in pts], times) + _anim("y1", [p[a][1] for p in pts], times)
                   + _anim("x2", [p[b][0] for p in pts], times) + _anim("y2", [p[b][1] for p in pts], times)
                   + "</line>")
    out.append("</g>")
    return "".join(out)


def tip_track(frames: list[Frame], idx: int, cx: float, cy: float, unit: float) -> tuple[list, list]:
    pts = [_pts(f.pose, cx, cy, unit, f.dx, f.dy)[idx] for f in frames]
    return [p[0] for p in pts], [p[1] for p in pts]


def _svg(body: str, label: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{label}"><rect width="{W}" height="{H}" rx="16" fill="#0f172a"/>{body}</svg>')


def _times(*ts: float) -> list[float]:
    return [t / DUR for t in ts]


def g_move() -> str:
    t = _times(0, 0.8, 1.6, 2.4, 3.2)
    off = [(0, 0), (34, -14), (34, 18), (-30, 12), (0, 0)]
    frames = [Frame(tt, POINT, dx, dy) for tt, (dx, dy) in zip(t, off)]
    # شاشة صغيرة ومؤشر يتبع السبابة
    sx = [168 + dx * 0.5 for dx, _ in off]
    sy = [50 + dy * 0.5 for _, dy in off]
    cursor = (f'<g><path d="M0 0 L0 14 L4 10 L8 17 L10 16 L6 9 L11 9 Z" fill="{ACCENT}">'
              f'<animateTransform attributeName="transform" type="translate" '
              f'values="{";".join(f"{x},{y}" for x, y in zip(sx, sy))}" keyTimes="{";".join(f"{v:.3f}" for v in t)}" '
              f'dur="{DUR}s" repeatCount="indefinite" calcMode="spline" '
              f'keySplines="{";".join([".42 0 .58 1"] * 4)}"/></path></g>')
    screen = f'<rect x="140" y="26" width="84" height="56" rx="6" fill="none" stroke="{FAINT}" stroke-width="2"/>'
    return _svg(screen + cursor + hand_svg(frames, 80, 100, 78), "move")


def _pinch_svg(target: Pose, tip: int, label: str, extra: str = "") -> str:
    t = _times(0, 0.7, 1.1, 1.9, 2.4, 3.2)
    poses = [OPEN, OPEN, target, target, OPEN, OPEN]
    frames = [Frame(tt, p) for tt, p in zip(t, poses)]
    xs, ys = tip_track(frames, tip, 120, 92, 92)
    # حلقة تنبض لحظة التلامس
    ring = (f'<circle cx="{xs[2]}" cy="{ys[2]}" r="6" fill="none" stroke="{OK}" stroke-width="3" opacity="0">'
            f'<animate attributeName="r" values="6;6;22;22" keyTimes="0;{t[2]:.3f};{t[3]:.3f};1" '
            f'dur="{DUR}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;{t[2]:.3f};{t[3]:.3f};1" '
            f'dur="{DUR}s" repeatCount="indefinite"/></circle>')
    return _svg(extra + hand_svg(frames, 120, 92, 92) + ring, label)


def g_click() -> str:
    return _pinch_svg(PINCH, 8, "click")


def g_right_click() -> str:
    t = _times(0, 1.1, 1.2, 2.4, 2.5, 3.2)
    menu = (f'<g opacity="0"><rect x="160" y="30" width="62" height="58" rx="6" fill="#1e293b" '
            f'stroke="{FAINT}"/>' + "".join(
                f'<rect x="168" y="{40 + i * 15}" width="{44 - i * 8}" height="5" rx="2" fill="{FAINT}"/>'
                for i in range(3))
            + f'<animate attributeName="opacity" values="0;0;1;1;0;0" '
              f'keyTimes="{";".join(f"{v:.3f}" for v in t)}" dur="{DUR}s" repeatCount="indefinite"/></g>')
    return _pinch_svg(MIDDLE_PINCH, 12, "right click", menu)


def g_drag() -> str:
    t = _times(0, 0.6, 1.0, 2.2, 2.6, 3.2)
    frames = [Frame(t[0], OPEN, -40), Frame(t[1], OPEN, -40), Frame(t[2], PINCH, -40),
              Frame(t[3], PINCH, 40), Frame(t[4], OPEN, 40), Frame(t[5], OPEN, -40)]
    xs, ys = tip_track(frames, 8, 120, 98, 80)
    # الملف يُسحب مع نقطة القرص فقط بين الإمساك والإفلات
    fx = [xs[2], xs[2], xs[2], xs[3], xs[3], xs[2]]
    fy = [ys[2] - 34] * 6
    file_icon = (f'<rect x="-12" y="-14" width="24" height="28" rx="3" fill="{ACCENT}" opacity=".85">'
                 f'<animate attributeName="x" values="{";".join(str(round(x - 12, 1)) for x in fx)}" '
                 f'keyTimes="{";".join(f"{v:.3f}" for v in t)}" dur="{DUR}s" repeatCount="indefinite" '
                 f'calcMode="spline" keySplines="{";".join([".42 0 .58 1"] * 5)}"/>'
                 f'<animate attributeName="y" values="{";".join(str(round(y - 14, 1)) for y in fy)}" '
                 f'keyTimes="{";".join(f"{v:.3f}" for v in t)}" dur="{DUR}s" repeatCount="indefinite"/></rect>')
    return _svg(file_icon + hand_svg(frames, 120, 98, 80), "drag")


def g_scroll() -> str:
    t = _times(0, 0.8, 1.6, 2.4, 3.2)
    off = [0, -26, 0, 26, 0]
    frames = [Frame(tt, TWO, 0, dy) for tt, dy in zip(t, off)]
    lines = "".join(f'<rect x="168" y="{20 + i * 16}" width="{48 - (i % 3) * 10}" height="6" rx="3" fill="{FAINT}"/>'
                    for i in range(9))
    page = (f'<svg x="160" y="24" width="68" height="122" viewBox="160 24 68 122"><g>{lines}'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{";".join(f"0,{-dy * 0.8}" for dy in off)}" keyTimes="{";".join(f"{v:.3f}" for v in t)}" '
            f'dur="{DUR}s" repeatCount="indefinite" calcMode="spline" '
            f'keySplines="{";".join([".42 0 .58 1"] * 4)}"/></g></svg>'
            f'<rect x="160" y="24" width="68" height="122" rx="6" fill="none" stroke="{FAINT}" stroke-width="2"/>')
    return _svg(page + hand_svg(frames, 84, 92, 80), "scroll")


def _bars(color: str, t_on: float, t_off: float) -> str:
    return (f'<g opacity="0" fill="{color}"><rect x="178" y="58" width="12" height="42" rx="3"/>'
            f'<rect x="198" y="58" width="12" height="42" rx="3"/>'
            f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{t_on:.3f};{t_on + 0.03:.3f};'
            f'{t_off:.3f};1" dur="{DUR}s" repeatCount="indefinite"/></g>')


def _hold_ring(t0: float, t1: float, color: str) -> str:
    """حلقة تمتلئ أثناء مدة الإبقاء المطلوبة."""
    c = 2 * 3.1416 * 22
    return (f'<circle cx="194" cy="79" r="22" fill="none" stroke="{FAINT}" stroke-width="5"/>'
            f'<circle cx="194" cy="79" r="22" fill="none" stroke="{color}" stroke-width="5" '
            f'stroke-dasharray="{c:.1f}" stroke-dashoffset="{c:.1f}" transform="rotate(-90 194 79)">'
            f'<animate attributeName="stroke-dashoffset" values="{c:.1f};{c:.1f};0;0;{c:.1f}" '
            f'keyTimes="0;{t0:.3f};{t1:.3f};0.95;1" dur="{DUR}s" repeatCount="indefinite"/></circle>')


def g_pause() -> str:
    t = _times(0, 0.5, 0.9, 2.6, 3.0, 3.2)
    frames = [Frame(tt, p) for tt, p in zip(t, [OPEN, OPEN, FIST, FIST, OPEN, OPEN])]
    return _svg(_hold_ring(t[2], t[2] + 0.6 / DUR, WARN) + _bars(WARN, t[2] + 0.6 / DUR, t[4])
                + hand_svg(frames, 92, 92, 86), "pause")


def g_resume() -> str:
    t = _times(0, 0.4, 2.8, 3.2)
    frames = [Frame(tt, p) for tt, p in zip(t, [FIST, OPEN, OPEN, FIST])]
    play = (f'<path d="M184 60 L210 79 L184 98 Z" fill="{OK}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{t[1] + 1 / DUR:.3f};'
            f'{t[1] + 1.05 / DUR:.3f};{t[2]:.3f};1" dur="{DUR}s" repeatCount="indefinite"/></path>')
    return _svg(_hold_ring(t[1], t[1] + 1 / DUR, OK) + play + hand_svg(frames, 92, 92, 86), "resume")


def g_desktop() -> str:
    t = _times(0, 0.3, 2.9, 3.2)
    frames = [Frame(tt, p, 0, dy) for tt, p, dy in zip(t, [POINT, OPEN, OPEN, POINT], [0, 0, 0, 0])]
    return _svg(_hold_ring(t[1], t[1] + 2 / DUR, ACCENT) + hand_svg(frames, 92, 92, 86), "show desktop")


def g_swipe() -> str:
    t = _times(0, 0.9, 1.3, 2.1, 2.5, 3.2)
    off = [-50, -50, 50, 50, -50, -50]
    frames = [Frame(tt, OPEN, dx, 8) for tt, dx in zip(t, off)]
    kt = ";".join(f"{v:.3f}" for v in t)
    win = []
    for i, col in enumerate((ACCENT, "#a78bfa")):
        ops = ["1;1;0;0;1;1", "0;0;1;1;0;0"][i]
        win.append(f'<rect x="{150 + i * 6}" y="{14 + i * 6}" width="70" height="44" rx="5" fill="#1e293b" '
                   f'stroke="{col}" stroke-width="2.5" opacity="{1 - i}"><animate attributeName="opacity" '
                   f'values="{ops}" keyTimes="{kt}" dur="{DUR}s" repeatCount="indefinite"/></rect>')
    return _svg("".join(win) + hand_svg(frames, 110, 104, 64, width=5), "swipe")


def g_zoom() -> str:
    t = _times(0, 0.6, 1.0, 2.2, 2.6, 3.2)
    poses = [OPEN, OPEN, PINCH, PINCH, OPEN, OPEN]
    spread = [0, 0, 0, 34, 34, 0]
    right = [Frame(tt, p, s) for tt, p, s in zip(t, poses, spread)]
    left = [Frame(tt, p, -s) for tt, p, s in zip(t, poses, spread)]
    kt = ";".join(f"{v:.3f}" for v in t)
    lens = (f'<g fill="none" stroke="{ACCENT}" stroke-width="3"><circle cx="120" cy="30" r="11">'
            f'<animate attributeName="r" values="9;9;9;15;15;9" keyTimes="{kt}" dur="{DUR}s" '
            f'repeatCount="indefinite"/></circle><path d="M115 30 h10 M120 25 v10"/></g>')
    return _svg(lens + hand_svg(right, 160, 104, 60, width=4.5)
                + hand_svg(left, 80, 104, 60, mirror=True, width=4.5), "zoom")


GESTURES = [
    ("move", g_move,
     {"ar": "تحريك المؤشر", "fr": "Déplacer le curseur", "en": "Move the pointer"},
     {"ar": "مدّ السبابة وحرّك يدك داخل المنطقة أمام الكاميرا. المؤشر يتبع طرف السبابة.",
      "fr": "Tendez l'index et déplacez la main devant la caméra. Le curseur suit le bout de l'index.",
      "en": "Point with your index and move your hand in front of the camera. The pointer follows your fingertip."}),
    ("click", g_click,
     {"ar": "نقر", "fr": "Clic gauche", "en": "Left click"},
     {"ar": "المس طرف السبابة بالإبهام لمسة قصيرة ثم افتحهما.",
      "fr": "Touchez brièvement le bout de l'index avec le pouce, puis relâchez.",
      "en": "Briefly touch your index fingertip with your thumb, then release."}),
    ("right_click", g_right_click,
     {"ar": "نقر يمين", "fr": "Clic droit", "en": "Right click"},
     {"ar": "المس طرف الإصبع الوسطى بالإبهام.",
      "fr": "Touchez le bout du majeur avec le pouce.",
      "en": "Touch your middle fingertip with your thumb."}),
    ("drag", g_drag,
     {"ar": "سحب وإفلات", "fr": "Glisser-déposer", "en": "Drag and drop"},
     {"ar": "اقرص وأبقِ الإصبعين متلامسين (أكثر من 0.4 ث)، حرّك يدك، ثم افتح الإصبعين للإفلات.",
      "fr": "Pincez et gardez les doigts serrés (plus de 0,4 s), déplacez la main, puis ouvrez les doigts pour déposer.",
      "en": "Pinch and keep holding (over 0.4 s), move your hand, then open your fingers to drop."}),
    ("scroll", g_scroll,
     {"ar": "تمرير", "fr": "Défilement", "en": "Scroll"},
     {"ar": "مدّ السبابة والوسطى معاً، ثم ارفع يدك أو اخفضها.",
      "fr": "Tendez l'index et le majeur, puis montez ou descendez la main.",
      "en": "Extend your index and middle fingers, then move your hand up or down."}),
    ("pause", g_pause,
     {"ar": "إيقاف طارئ", "fr": "Arrêt d'urgence", "en": "Emergency stop"},
     {"ar": "أغلق قبضتك نصف ثانية تقريباً: يتوقف كل التحكم فوراً وتُحرَّر أزرار الفأرة.",
      "fr": "Fermez le poing environ une demi-seconde : tout le contrôle s'arrête et les boutons de souris sont relâchés.",
      "en": "Close your fist for about half a second: all control stops and mouse buttons are released."}),
    ("resume", g_resume,
     {"ar": "استئناف", "fr": "Reprendre", "en": "Resume"},
     {"ar": "أثناء الإيقاف: افتح كفك أمام الكاميرا ثانية واحدة.",
      "fr": "Pendant la pause : montrez la paume ouverte à la caméra pendant une seconde.",
      "en": "While paused: show your open palm to the camera for one second."}),
    ("desktop", g_desktop,
     {"ar": "إظهار سطح المكتب", "fr": "Afficher le bureau", "en": "Show desktop"},
     {"ar": "أبقِ كفك مفتوحاً ثابتاً ثانيتين.",
      "fr": "Gardez la paume ouverte, immobile, pendant deux secondes.",
      "en": "Hold your open palm still for two seconds."}),
    ("swipe", g_swipe,
     {"ar": "تبديل النافذة", "fr": "Changer de fenêtre", "en": "Switch window"},
     {"ar": "بيد مفتوحة، اسحب بسرعة إلى اليمين (النافذة التالية) أو اليسار (السابقة).",
      "fr": "Main ouverte, balayez rapidement vers la droite (fenêtre suivante) ou la gauche (précédente).",
      "en": "With an open hand, swipe quickly right (next window) or left (previous)."}),
    ("zoom", g_zoom,
     {"ar": "تكبير وتصغير", "fr": "Zoom", "en": "Zoom"},
     {"ar": "اقرص بكلتا اليدين، ثم باعد بينهما للتكبير أو قرّبهما للتصغير.",
      "fr": "Pincez avec les deux mains, puis écartez-les (zoom avant) ou rapprochez-les (zoom arrière).",
      "en": "Pinch with both hands, then move them apart (zoom in) or together (zoom out)."}),
]


# ============================ نصوص الصفحة ============================
UI = {
    "title": {"ar": "دليل التحكم بدون لمس", "fr": "Guide du contrôle sans contact",
              "en": "No-Touch Control guide"},
    "subtitle": {"ar": "يعمل هذا الدليل بلا إنترنت. لا شيء يغادر جهازك.",
                 "fr": "Ce guide fonctionne sans internet. Rien ne quitte votre ordinateur.",
                 "en": "This guide works offline. Nothing leaves your computer."},
    "nav_start": {"ar": "البداية", "fr": "Démarrage", "en": "Getting started"},
    "nav_safety": {"ar": "الأمان", "fr": "Sécurité", "en": "Safety"},
    "nav_gestures": {"ar": "الإيماءات", "fr": "Gestes", "en": "Gestures"},
    "nav_voice": {"ar": "الصوت", "fr": "Voix", "en": "Voice"},
    "nav_indicator": {"ar": "مؤشر الحالة", "fr": "Indicateur", "en": "Indicator"},
    "nav_commands": {"ar": "كل الأوامر", "fr": "Toutes les commandes", "en": "All commands"},
    "nav_trouble": {"ar": "حل المشكلات", "fr": "Dépannage", "en": "Troubleshooting"},
    "nav_privacy": {"ar": "الخصوصية", "fr": "Confidentialité", "en": "Privacy"},

    "start_h": {"ar": "البداية في ثلاث خطوات", "fr": "Démarrer en trois étapes",
                "en": "Start in three steps"},
    "start_1": {"ar": "شغّل HADJ-NoTouch.bat. تظهر أيقونة قرب الساعة ودائرة الحالة في زاوية الشاشة.",
                "fr": "Lancez HADJ-NoTouch.bat. Une icône apparaît près de l'horloge et le cercle d'état dans un coin de l'écran.",
                "en": "Run HADJ-NoTouch.bat. An icon appears near the clock and the status circle in a corner of the screen."},
    "start_2": {"ar": "قل «معايرة» بعد كلمة التنبيه (نحو 20 ثانية): اجلس على بعد 50 سم والضوء أمامك.",
                "fr": "Dites « calibrage » après le mot d'éveil (environ 20 secondes) : asseyez-vous à 50 cm, la lumière devant vous.",
                "en": "Say “calibrate” after the wake word (about 20 seconds): sit 50 cm away with the light in front of you."},
    "start_3": {"ar": "قل كلمة التنبيه ثم الأمر، مثل: «حاسوب، افتح المفكرة». أو حرّك المؤشر بسبابتك.",
                "fr": "Dites le mot d'éveil puis la commande, par exemple : « Ordinateur, ouvre le bloc-notes ». Ou pilotez le curseur avec l'index.",
                "en": "Say the wake word then the command, for example: “Computer, open notepad”. Or move the pointer with your index finger."},

    "safety_h": {"ar": "الإيقاف الطارئ: ثلاث طرق، تعمل دائماً",
                 "fr": "Arrêt d'urgence : trois moyens, toujours actifs",
                 "en": "Emergency stop: three ways, always on"},
    "safety_fist": {"ar": "✊ قبضة مغلقة نصف ثانية", "fr": "✊ Poing fermé une demi-seconde",
                    "en": "✊ Closed fist for half a second"},
    "safety_voice": {"ar": "🗣 قل «توقف» (لا تحتاج كلمة التنبيه)",
                     "fr": "🗣 Dites « stop » (pas besoin du mot d'éveil)",
                     "en": "🗣 Say “stop” (no wake word needed)"},
    "safety_key": {"ar": "⌨ الاختصار Ctrl+Alt+Shift+P (للمرافق)",
                   "fr": "⌨ Raccourci Ctrl+Alt+Shift+P (pour un accompagnant)",
                   "en": "⌨ Shortcut Ctrl+Alt+Shift+P (for a caregiver)"},
    "safety_resume": {"ar": "للاستئناف: كف مفتوح ثانية، أو «{wake}، استأنف»، أو الاختصار نفسه.",
                      "fr": "Pour reprendre : paume ouverte une seconde, « {wake}, reprends », ou le même raccourci.",
                      "en": "To resume: open palm for one second, “{wake}, resume”, or the same shortcut."},
    "safety_confirm": {"ar": "الأوامر الخطرة (إيقاف التشغيل، حذف، إغلاق بدون حفظ…) تطلب «نعم» أو «لا» قبل التنفيذ.",
                       "fr": "Les commandes risquées (éteindre, supprimer, fermer sans enregistrer…) demandent « oui » ou « non » avant d'agir.",
                       "en": "Risky commands (shut down, delete, close without saving…) ask “yes” or “no” first."},

    "gestures_h": {"ar": "الإيماءات", "fr": "Les gestes", "en": "Gestures"},
    "gestures_tip": {"ar": "يمكن تغيير ما تفعله كل إيماءة من الإعدادات ← الكاميرا.",
                     "fr": "Vous pouvez changer l'action de chaque geste dans Réglages → Caméra.",
                     "en": "You can change what each gesture does in Settings → Camera."},
    "motion_off": {"ar": "الحركة متوقفة (إعداد «تقليل الحركة» في نظامك)",
                   "fr": "Animations en pause (réglage « réduire les animations » de votre système)",
                   "en": "Animations paused (your system's “reduce motion” setting)"},

    "voice_h": {"ar": "الأوامر الصوتية", "fr": "Commandes vocales", "en": "Voice commands"},
    "voice_wake": {"ar": "ابدأ بكلمة التنبيه: «{wake}». بعد أمر ناجح تبقى بضع ثوانٍ لأمر آخر دون تكرارها.",
                   "fr": "Commencez par le mot d'éveil : « {wake} ». Après une commande réussie, vous avez quelques secondes pour en donner une autre sans le répéter.",
                   "en": "Start with the wake word: “{wake}”. After a successful command you have a few seconds for another one without repeating it."},
    "voice_dictation": {"ar": "الإملاء: «ابدأ الإملاء» ثم تكلّم بحرية، و«أوقف الإملاء» للخروج.",
                        "fr": "Dictée : « commence la dictée », parlez librement, puis « arrête la dictée ».",
                        "en": "Dictation: “start dictation”, speak freely, then “stop dictation”."},
    "voice_grid": {"ar": "الشبكة: «اعرض الشبكة» ثم رقماً من 1 إلى 9 للتكبير، ثم «انقر».",
                   "fr": "Grille : « affiche la grille », puis un chiffre de 1 à 9 pour zoomer, puis « clique ».",
                   "en": "Grid: “show grid”, then a number 1 to 9 to zoom in, then “click”."},
    "voice_profile": {"ar": "الملفات الشخصية: «وضع المطبخ»، «وضع العرض التقديمي»، «وضع البث»، «وضع التصفح»، «وضع عادي».",
                      "fr": "Profils : « profil cuisine », « profil présentation », « profil streaming », « profil navigation web », « profil standard ».",
                      "en": "Profiles: “profile kitchen”, “profile presentation”, “profile streaming”, “profile web browsing”, “profile standard”."},
    "voice_macro": {"ar": "الماكرو: الإعدادات ← الماكرو، ثم عبارة من اختيارك ← مفاتيح أو نص أو نقرات. ما يحذف أو يغلق يطلب «نعم» دائماً.",
                    "fr": "Macros : Réglages → Macros, puis une phrase de votre choix → touches, texte ou clics. Ce qui supprime ou ferme demande toujours « oui ».",
                    "en": "Macros: Settings → Macros, then a phrase of your choice → keys, text or clicks. Anything that deletes or closes always asks “yes”."},
    "voice_lang": {"ar": "لغة الأوامر: «العربية» أو «الفرنسية» أو «الإنجليزية».",
                   "fr": "Langue des commandes : dites « français », « anglais » ou « arabe ».",
                   "en": "Command language: say “English”, “French” or “Arabic”."},

    "ind_h": {"ar": "دائرة الحالة", "fr": "Le cercle d'état", "en": "The status circle"},
    "ind_ready": {"ar": "ميكروفون: يستمع لكلمة التنبيه", "fr": "Micro : à l'écoute du mot d'éveil",
                  "en": "Microphone: listening for the wake word"},
    "ind_voice": {"ar": "حلقة خضراء تنبض: يسمع صوتك الآن", "fr": "Anneau vert qui pulse : votre voix est entendue",
                  "en": "Pulsing green ring: your voice is being heard"},
    "ind_hand": {"ar": "هيكل يد: الكاميرا ترى يدك", "fr": "Squelette de main : la caméra voit votre main",
                 "en": "Hand skeleton: the camera sees your hand"},
    "ind_pause": {"ar": "عمودان: التحكم متوقف", "fr": "Deux barres : contrôle en pause",
                  "en": "Two bars: control paused"},
    "ind_error": {"ar": "علامة «!»: خطأ في الميكروفون أو النموذج", "fr": "« ! » : erreur du micro ou du modèle",
                  "en": "“!”: microphone or model error"},
    "ind_badge": {"ar": "النقطة الصغيرة: حالة الكاميرا (أخضر = تتبع، أحمر = لا صورة)",
                  "fr": "Petite pastille : état de la caméra (vert = suivi, rouge = pas d'image)",
                  "en": "Small dot: camera state (green = tracking, red = no image)"},

    "cmd_h": {"ar": "كل الأوامر الصوتية", "fr": "Toutes les commandes vocales", "en": "All voice commands"},
    "cmd_search": {"ar": "ابحث عن أمر…", "fr": "Rechercher une commande…", "en": "Search a command…"},
    "cmd_slot": {"ar": "«…» = أي كلام (اسم تطبيق أو نص)", "fr": "« … » = texte libre (nom d'application, phrase)",
                 "en": "“…” = free text (app name or phrase)"},
    "cmd_danger": {"ar": "يطلب تأكيداً", "fr": "demande confirmation", "en": "asks for confirmation"},
    "cmd_always": {"ar": "دون كلمة التنبيه", "fr": "sans mot d'éveil", "en": "no wake word"},
    "cmd_none": {"ar": "لا نتائج", "fr": "Aucun résultat", "en": "No results"},
    "cmd_other_lang": {"ar": "عرض العبارات بلغة:", "fr": "Phrases en :", "en": "Phrases in:"},

    "tr_h": {"ar": "حل المشكلات", "fr": "Dépannage", "en": "Troubleshooting"},
    "tr_cam_q": {"ar": "الكاميرا لا ترى يدي", "fr": "La caméra ne voit pas ma main",
                 "en": "The camera doesn't see my hand"},
    "tr_cam_a": {"ar": "أغلق التطبيقات الأخرى التي تستخدم الكاميرا (المتصفح، الاجتماعات)، أضف ضوءاً أمامك، ثم أعد المعايرة.",
                 "fr": "Fermez les autres applications qui utilisent la caméra (navigateur, visioconférence), ajoutez de la lumière devant vous, puis refaites le calibrage.",
                 "en": "Close other apps using the camera (browser, video calls), add light in front of you, then calibrate again."},
    "tr_mic_q": {"ar": "لا يفهم أوامري", "fr": "Mes commandes ne sont pas comprises",
                 "en": "My commands aren't understood"},
    "tr_mic_a": {"ar": "تحقق من لغة الأوامر في قائمة الأيقونة، تكلّم بوضوح قرب الميكروفون، واختر الميكروفون الصحيح في الإعدادات ← الصوت.",
                 "fr": "Vérifiez la langue des commandes dans le menu de l'icône, parlez distinctement près du micro, et choisissez le bon micro dans Réglages → Voix.",
                 "en": "Check the command language in the icon menu, speak clearly near the microphone, and pick the right microphone in Settings → Voice."},
    "tr_slow_q": {"ar": "المؤشر بطيء أو يرتجف", "fr": "Le curseur est lent ou tremble",
                  "en": "The pointer is slow or shaky"},
    "tr_slow_a": {"ar": "أغلق البرامج الثقيلة، حسّن الإضاءة، وأعد المعايرة لتصغير منطقة الحركة.",
                  "fr": "Fermez les programmes lourds, améliorez l'éclairage et refaites le calibrage pour réduire la zone de mouvement.",
                  "en": "Close heavy programs, improve the lighting and recalibrate to shrink the movement zone."},
    "tr_lang_q": {"ar": "أريد العربية في النسخة الخفيفة", "fr": "Je veux l'arabe dans la version Lite",
                  "en": "I want Arabic in the Lite edition"},
    "tr_lang_a": {"ar": "نزّل «حزمة العربية» وفك ضغطها داخل مجلد التطبيق (بجانب HADJ-NoTouch.bat)، ثم أعد تشغيله. تظهر العربية تلقائياً.",
                  "fr": "Téléchargez le « pack arabe » et décompressez-le dans le dossier de l'application (à côté de HADJ-NoTouch.bat), puis relancez. L'arabe apparaît tout seul.",
                  "en": "Download the “Arabic pack” and unzip it into the app folder (next to HADJ-NoTouch.bat), then restart. Arabic appears automatically."},
    "tr_stuck_q": {"ar": "التطبيق لا يستجيب", "fr": "L'application ne répond plus",
                   "en": "The app doesn't respond"},
    "tr_stuck_a": {"ar": "اضغط Ctrl+Alt+Shift+P مرتين، أو أغلقه من قائمة الأيقونة قرب الساعة. السجلات في user_data\\logs.",
                   "fr": "Appuyez deux fois sur Ctrl+Alt+Shift+P, ou quittez depuis le menu de l'icône près de l'horloge. Les journaux sont dans user_data\\logs.",
                   "en": "Press Ctrl+Alt+Shift+P twice, or quit from the icon menu near the clock. Logs are in user_data\\logs."},

    "priv_h": {"ar": "الخصوصية", "fr": "Confidentialité", "en": "Privacy"},
    "priv_1": {"ar": "كل المعالجة على جهازك: لا اتصال بالإنترنت ولا حساب.",
               "fr": "Tout est traité sur votre ordinateur : pas d'internet, pas de compte.",
               "en": "Everything runs on your computer: no internet, no account."},
    "priv_2": {"ar": "الصوت والصور تبقى في الذاكرة ولا تُحفظ أبداً.",
               "fr": "Le son et les images restent en mémoire et ne sont jamais enregistrés.",
               "en": "Audio and images stay in memory and are never saved."},
    "priv_3": {"ar": "الإعدادات والسجلات في مجلد user_data بجانب التطبيق: احذفه لإزالة كل أثر.",
               "fr": "Réglages et journaux sont dans le dossier user_data à côté de l'application : supprimez-le pour ne laisser aucune trace.",
               "en": "Settings and logs live in the user_data folder next to the app: delete it to leave no trace."},
    "wake": {"ar": "حاسوب", "fr": "Ordinateur", "en": "Computer"},
}


def build_data() -> dict:
    return {
        "langs": list(LANGS),
        "ui": UI,
        # SVG مضمّن (لا fetch: المتصفحات تمنعه من file://) لكي يمكن إيقاف الحركة عند «تقليل الحركة»
        "gestures": [{"id": gid, "title": title, "how": how, "svg": fn()} for gid, fn, title, how in GESTURES],
        "sections": command_sections(),
    }


def write_all(out_dir: Path = HELP_DIR) -> list[Path]:
    written = []
    gdir = out_dir / "gestures"
    gdir.mkdir(parents=True, exist_ok=True)
    for gid, fn, _t, _h in GESTURES:
        p = gdir / f"{gid}.svg"
        p.write_text(fn(), encoding="utf-8")
        written.append(p)
    data = json.dumps(build_data(), ensure_ascii=False, separators=(",", ":"))
    p = out_dir / "data.js"
    p.write_text("// مولَّد بواسطة help/generate.py — لا تعدّله يدوياً\nwindow.HELP = " + data + ";\n",
                 encoding="utf-8")
    written.append(p)
    # نقاط دخول لكل لغة: ShellExecute يُسقط ?lang= و#lang من روابط الملفات، لذا ملف لكل لغة
    for lang in LANGS:
        p = out_dir / f"{lang}.html"
        p.write_text(f'<!doctype html><meta charset="utf-8"><title>Help</title>'
                     f'<meta http-equiv="refresh" content="0;url=index.html#{lang}">'
                     f'<a href="index.html#{lang}">index.html</a>\n', encoding="utf-8")
        written.append(p)
    return written


if __name__ == "__main__":
    for path in write_all():
        print(path.relative_to(HELP_DIR))
