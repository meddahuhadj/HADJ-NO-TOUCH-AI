"""فهرس التطبيقات المثبتة مع مطابقة تقريبية للاسم المنطوق."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from rapidfuzz import fuzz, process

from commands.text import normalize
from os_layer.base import AppEntry

log = logging.getLogger(__name__)


def _looks_like_target(value: str) -> bool:
    v = value.lower()
    return v.endswith((".exe", ".lnk", ".bat", ".cmd", ".msc")) or ":" in v or "\\" in v or "/" in v


class AppIndex:
    def __init__(self, lister, aliases: dict[str, str] | None = None,
                 cache_path: Path | None = None, cutoff: int = 80):
        """lister: دالة ترجع list[AppEntry] (عادةً backend.list_apps)."""
        self._lister = lister
        self.cache_path = cache_path
        self.cutoff = cutoff
        self._lock = threading.Lock()
        self.entries: list[AppEntry] = []
        self._names: list[str] = []
        self.set_aliases(aliases or {})

    def set_aliases(self, aliases: dict[str, str]) -> None:
        self.aliases = {normalize(k): v for k, v in aliases.items() if normalize(k)}

    def set_entries(self, entries: list[AppEntry]) -> None:
        with self._lock:
            self.entries = entries
            self._names = [normalize(e.name) for e in entries]

    def load_cache(self) -> bool:
        if not self.cache_path or not self.cache_path.exists():
            return False
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self.set_entries([AppEntry(**d) for d in data])
            return True
        except (ValueError, TypeError) as e:
            log.warning("ذاكرة التطبيقات تالفة: %s", e)
            return False

    def refresh(self) -> int:
        entries = self._lister()
        self.set_entries(entries)
        if self.cache_path:
            self.cache_path.write_text(
                json.dumps([e.__dict__ for e in entries], ensure_ascii=False, indent=0),
                encoding="utf-8")
        log.info("تمت فهرسة %d تطبيقاً", len(entries))
        return len(entries)

    def refresh_async(self) -> threading.Thread:
        t = threading.Thread(target=self._safe_refresh, daemon=True, name="app-index")
        t.start()
        return t

    def _safe_refresh(self):
        try:
            self.refresh()
        except Exception:  # noqa: BLE001 - الفهرسة يجب ألا توقف التطبيق
            log.exception("فشلت فهرسة التطبيقات")

    # ------------------------------------------------------------------
    def find(self, spoken: str, _depth: int = 0) -> AppEntry | None:
        q = normalize(spoken)
        if not q:
            return None
        # الأدوات الفرنسية: "la calculatrice" = "calculatrice"، "l explorateur" = "explorateur"
        for article in ("le ", "la ", "les ", "l ", "un ", "une "):
            if q.startswith(article) and len(q) > len(article):
                q = q[len(article):]
                break
        # أداة التعريف اختيارية: "مفكرة" = "المفكرة"
        if q not in self.aliases:
            if q.startswith("ال") and q[2:] in self.aliases:
                q = q[2:]
            elif "ال" + q in self.aliases:
                q = "ال" + q
        # 1) الأسماء المستعارة
        alias_key = q if q in self.aliases else None
        if alias_key is None and self.aliases:
            hit = process.extractOne(q, list(self.aliases), scorer=fuzz.ratio, score_cutoff=85)
            alias_key = hit[0] if hit else None
        if alias_key is not None:
            value = self.aliases[alias_key]
            if _looks_like_target(value):
                return AppEntry(name=spoken, target=value, kind="command")
            if _depth == 0:
                found = self._find_indexed(normalize(value))
                if found:
                    return found
        # 2) التطبيقات المفهرسة
        return self._find_indexed(q)

    def _find_indexed(self, q: str) -> AppEntry | None:
        with self._lock:
            if not self._names:
                return None
            if q in self._names:
                return self.entries[self._names.index(q)]
            hit = process.extractOne(q, self._names, scorer=_app_score, score_cutoff=self.cutoff)
            return self.entries[hit[2]] if hit else None


def _app_score(q: str, name: str, **_) -> float:
    """الأفضل بين المطابقة العامة ومطابقة كلمة واحدة من الاسم ("exel" ← "Microsoft Excel")."""
    words = [w for w in name.split() if len(w) >= 3]
    return max([fuzz.WRatio(q, name)] + [fuzz.ratio(q, w) for w in words])
