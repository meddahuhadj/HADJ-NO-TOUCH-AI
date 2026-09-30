"""الشبكة الصوتية: تقسيم الشاشة إلى 3×3 خانات مرقمة، واختيار رقم يكبّر الخانة ويقسمها مجدداً.

الترقيم مثل لوحة أرقام الهاتف: 1 2 3 في الصف العلوي من اليسار إلى اليمين.
الإحداثيات بالبكسل الفعلي (نفس إحداثيات طبقة النظام).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from commands.text import normalize

Rect = tuple[int, int, int, int]  # left, top, width, height

NUMBER_WORDS = {
    "ar": {
        1: ["واحد", "وحده", "واحده"], 2: ["اثنان", "اثنين", "اتنين", "ثنين"],
        3: ["ثلاثه", "ثلاث", "تلاته", "تلاتة"], 4: ["اربعه", "اربع"],
        5: ["خمسه", "خمس"], 6: ["سته", "ست", "سته"], 7: ["سبعه", "سبع"],
        8: ["ثمانيه", "ثمان", "تمانيه", "ثماني"], 9: ["تسعه", "تسع"],
    },
    "en": {
        1: ["one", "won"], 2: ["two", "to", "too"], 3: ["three", "tree"], 4: ["four", "for", "fore"],
        5: ["five"], 6: ["six", "sex"], 7: ["seven"], 8: ["eight", "ate"], 9: ["nine"],
    },
    "fr": {
        1: ["un", "une", "hein"], 2: ["deux", "de"], 3: ["trois"], 4: ["quatre"], 5: ["cinq", "saint"],
        6: ["six", "cis"], 7: ["sept", "cette", "set"], 8: ["huit"], 9: ["neuf"],
    },
}

GRID_COMMANDS = {
    "click": {"ar": ["انقر", "اضغط", "كليك"], "en": ["click"], "fr": ["clique", "clic"]},
    "double_click": {"ar": ["انقر مرتين", "نقره مزدوجه", "دبل كليك"], "en": ["double click"],
                     "fr": ["double clic", "double clique"]},
    "right_click": {"ar": ["انقر بالزر الايمن", "انقر يمين", "زر ايمن"], "en": ["right click"],
                    "fr": ["clic droit", "clique droit"]},
    "back": {"ar": ["رجوع", "ارجع", "السابق"], "en": ["back", "go back", "undo"], "fr": ["retour", "reviens"]},
    "close": {"ar": ["الغاء", "اخف الشبكه", "اغلق الشبكه", "اخرج"], "en": ["cancel", "hide grid", "close grid"],
              "fr": ["annule", "annuler", "cache la grille", "ferme la grille"]},
    "move": {"ar": ["حرك", "هنا"], "en": ["move", "here"], "fr": ["déplace", "ici"]},
}


def parse_number(text: str, lang: str) -> int | None:
    n = normalize(text)
    if not n:
        return None
    toks = n.split()
    # "رقم خمسه" / "number five" / "numéro cinq"
    if len(toks) == 2 and toks[0] in ("رقم", "number", "numero"):
        n = toks[1]
    elif len(toks) != 1:
        return None
    if n.isdigit() and 1 <= int(n) <= 9:
        return int(n)
    table = {v: [normalize(w) for w in ws] for v, ws in NUMBER_WORDS.get(lang, {}).items()}
    for value, words in table.items():
        if n in words:
            return value
    # تسامح بسيط لأخطاء التعرف في الكلمات الأطول
    best, score = None, 0.0
    for value, words in table.items():
        for w in words:
            if len(w) >= 4:
                s = fuzz.ratio(n, w)
                if s > score:
                    best, score = value, s
    return best if score >= 80 else None


def parse_grid_command(text: str, lang: str) -> str | None:
    n = normalize(text)
    for cmd, table in GRID_COMMANDS.items():   # normalize: "déplace" = "deplace"
        if n in {normalize(p) for p in table.get(lang, [])}:
            return cmd
    return None


def split_rect(rect: Rect, n: int, cols: int = 3, rows: int = 3) -> Rect:
    left, top, w, h = rect
    i = n - 1
    r, c = divmod(i, cols)
    x0 = left + w * c // cols
    x1 = left + w * (c + 1) // cols
    y0 = top + h * r // rows
    y1 = top + h * (r + 1) // rows
    return x0, y0, x1 - x0, y1 - y0


def center(rect: Rect) -> tuple[int, int]:
    left, top, w, h = rect
    return left + w // 2, top + h // 2


@dataclass
class GridState:
    screen: Rect
    stack: list[Rect] = field(default_factory=list)
    min_size: int = 12      # لا تقسيم أصغر من هذا (بكسل)

    @property
    def rect(self) -> Rect:
        return self.stack[-1] if self.stack else self.screen

    @property
    def level(self) -> int:
        return len(self.stack)

    def select(self, n: int) -> bool:
        if not 1 <= n <= 9:
            return False
        new = split_rect(self.rect, n)
        if new[2] < 1 or new[3] < 1:
            return False
        self.stack.append(new)
        return True

    @property
    def can_split(self) -> bool:
        return self.rect[2] >= self.min_size * 3 and self.rect[3] >= self.min_size * 3

    def back(self) -> bool:
        if self.stack:
            self.stack.pop()
            return True
        return False

    @property
    def target(self) -> tuple[int, int]:
        return center(self.rect)
