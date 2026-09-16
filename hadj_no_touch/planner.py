"""HADJ AI Action Planner.

Turns a free-text request ("prepare my presentation", "switch to work setup")
into an explicit, previewable Plan of registered actions. Every step must
exist in the ActionRegistry -- no arbitrary code, no ad-hoc commands. The
user sees the plan and confirms before anything runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hadj_no_touch.ai.intent_engine import Intent
from hadj_no_touch.safety import ActionRegistry


@dataclass
class Plan:
    request: str
    steps: list[Intent] = field(default_factory=list)
    description: str = ""

    def is_empty(self) -> bool:
        return not self.steps

    def as_dict(self) -> dict:
        return {
            "request": self.request,
            "description": self.description,
            "steps": [
                {"action": i.action, "params": i.params, "describe": i.describe()}
                for i in self.steps
            ],
        }


class ActionPlanner:
    """Rule + registered-action controller. No external model required
    (offline first); the vocabulary is deliberately small and honest."""

    def __init__(self, registry: ActionRegistry | None = None):
        self.registry = registry or ActionRegistry()

    # ---- registered actions helper ------------------------------------------
    def _step(self, action: str, params: dict | None = None) -> Intent | None:
        if not self.registry.known(action):
            return None
        intent = Intent(action=action, params=dict(params or {}),
                        source="planner")
        intent.description = f"(AI) {self.registry.describe(action)}"
        return intent

    # ---- planning -----------------------------------------------------------
    def plan(self, request: str) -> Plan:
        text = _normalize(request)
        steps: list[Intent] = []
        desc = ""

        if _contains(text, "present", "slides", "slide show", "powerpoint", "ppt",
                     "présentation", "diaporama",
                     "عرض", "شرائح", "بوربوينت"):
            if s := self._step("PROFILE_SWITCH", {"profile": "presentation"}):
                steps.append(s)
            if s := self._step("OPEN_APP", {"app": "powerpnt"}):
                steps.append(s)
            if s := self._step("START_PRESENTATION"):
                steps.append(s)
            desc = "Prepare presentation: presentation profile, PowerPoint, start slideshow."

        elif _contains(text, "work", "workspace", "work mode", "coding", "develop", "code",
                       "travail", "développement", "développer",
                       "العمل", "بيئة", "تطوير", "كود"):
            if s := self._step("PROFILE_SWITCH", {"profile": "developer"}):
                steps.append(s)
            if s := self._step("OPEN_APP", {"app": "chrome"}):
                steps.append(s)
            if s := self._step("OPEN_APP", {"app": "notepad"}):
                steps.append(s)
            desc = "Work setup: developer profile, browser and editor."

        elif _contains(text, "relax", "movie", "film", "video", "listen", "music", "media",
                       "musique", "vidéo", "film", "écouter",
                       "فيلم", "موسيقى", "أفلام", "استرخاء"):
            if s := self._step("PROFILE_SWITCH", {"profile": "media"}):
                steps.append(s)
            desc = "Media mode: switch to the media profile."

        elif _contains(text, "document", "pdf", "read", "reader", "book",
                       "document", "lecture", "livre",
                       "مستند", "قراءة", "كتاب"):
            if s := self._step("PROFILE_SWITCH", {"profile": "pdf"}):
                steps.append(s)
            desc = "Document mode: switch to the PDF / reading profile."

        elif _contains(text, "health check", "test", "diagnostic", "verify",
                       "test", "diagnostic", "vérifier", "santé",
                       "فحص", "اختبار", "تشخيص"):
            if s := self._step("CALIBRATE"):
                steps.append(s)
            desc = "Diagnostics: run a full calibration & self-check."

        elif _contains(text, "quiet", "not now", "pause", "stop control", "sleep mode",
                       "calme", "pause", "arrêter", "repos",
                       "هادئ", "توقف", "إيقاف"):
            if s := self._step("PAUSE_CONTROL"):
                steps.append(s)
            desc = "Pause control until you resume."

        elif _contains(text, "help", "usage", "what can",
                       "aide", "aider",
                       "مساعدة"):
            if s := self._step("HELP"):
                steps.append(s)
            desc = "Open the quick help / onboarding."

        return Plan(request=request, steps=steps, description=desc)


def _normalize(text: str) -> str:
    # Keep unicode letters (accented French, Arabic) — only punctuation vanishes.
    return re.sub(r"[^\w\s]+", " ", str(text or ""), flags=re.UNICODE).lower()


def _contains(text: str, *tokens: str) -> bool:
    return any(tok in text for tok in tokens)