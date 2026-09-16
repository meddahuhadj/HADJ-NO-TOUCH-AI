"""Application context: what is the user currently doing on Windows."""

from __future__ import annotations

from dataclasses import dataclass

from ..logging_setup import get_logger
from ..windows import window_control

log = get_logger("ai.context")

CONTEXT_CATEGORIES = {
    "browser": "Browser",
    "media": "Media player",
    "pdf": "PDF viewer",
    "presentation": "Presentation",
    "office": "Office document",
    "terminal": "Terminal",
    "files": "File explorer",
    "imaging": "Medical / imaging",
    "other": "Other",
}


@dataclass
class ApplicationContext:
    category: str = "other"
    exe: str = ""
    title: str = ""
    name: str = ""

    @property
    def description(self) -> str:
        return CONTEXT_CATEGORIES.get(self.category, self.category)

    @property
    def is_document_like(self) -> bool:
        return self.category in ("pdf", "presentation", "office", "imaging")

    @property
    def is_media_like(self) -> bool:
        return self.category in ("media", "browser")


class ContextEngine:
    def snapshot(self) -> ApplicationContext:
        title, exe = window_control.foreground_window_info()
        cat = window_control.context_category(exe)
        return ApplicationContext(category=cat, exe=exe, title=title)

    def categorize(self, exe: str) -> str:
        return window_control.context_category(exe)