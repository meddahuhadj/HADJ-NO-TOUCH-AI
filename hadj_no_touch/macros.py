"""HADJ Macro Studio engine.

A macro is a named sequence of registered intents fired by one trigger:

    trigger  = "voice"   -> a spoken phrase
             = "gesture" -> a hand gesture kind (e.g. FIST_LOCK, CIRCLE_CW)
             = "button"  -> a UI quick-action button

Execution goes through the exact same executor the rest of the app uses,
so every step is filtered by the Safety Engine (allowlist + risk levels).
"""

from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass, field


@dataclass
class Macro:
    name: str
    trigger: str                 # voice | gesture | button
    trigger_value: str           # phrase / gesture kind / button id
    actions: list[dict]          # [{action, params}]
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Macro":
        return cls(
            name=str(data.get("name", "")),
            trigger=str(data.get("trigger", "voice")),
            trigger_value=str(data.get("trigger_value", "")),
            actions=list(data.get("actions", []) or []),
            description=str(data.get("description", "")),
            enabled=bool(data.get("enabled", True)),
        )


TRIGGER_VOICE = "voice"
TRIGGER_GESTURE = "gesture"
TRIGGER_BUTTON = "button"


class MacroRunner:
    """Holds the macro set and dispatches matching macros to an executor.

    ``executor`` is a callable accepting an Intent and returning whether it
    ran (used to route every step through the Safety Engine + confirmation).
    """

    def __init__(self, executor=None):
        self._macros: list[Macro] = []
        self._lock = threading.RLock()
        self._executor = executor

    def set_executor(self, executor) -> None:
        with self._lock:
            self._executor = executor

    # -- CRUD ---------------------------------------------------------------
    def add(self, macro: Macro) -> str | None:
        with self._lock:
            if not macro.name or not macro.trigger_value or not macro.actions:
                return "A macro needs a name, a trigger value and at least one action."
            if self.get(macro.name) is not None:
                return "A macro with that name already exists."
            self._macros.append(macro)
        return None

    def update(self, macro: Macro) -> bool:
        with self._lock:
            for i, m in enumerate(self._macros):
                if m.name == macro.name:
                    self._macros[i] = macro
                    return True
        return False

    def remove(self, name: str) -> bool:
        with self._lock:
            for i, m in enumerate(self._macros):
                if m.name == name:
                    del self._macros[i]
                    return True
        return False

    def get(self, name: str) -> Macro | None:
        with self._lock:
            for m in self._macros:
                if m.name == name:
                    return m
        return None

    def all(self) -> list[Macro]:
        with self._lock:
            return list(self._macros)

    def clear(self) -> None:
        with self._lock:
            self._macros.clear()

    # -- matching -------------------------------------------------------------
    def find_voice(self, phrase: str) -> Macro | None:
        norm = _normalize(phrase)
        if not norm:
            return None
        with self._lock:
            for m in self._macros:
                if not m.enabled or m.trigger != TRIGGER_VOICE:
                    continue
                if norm == _normalize(m.trigger_value) or \
                   _normalize(m.trigger_value) in norm:
                    return m
        return None

    def find_gesture(self, gesture_kind: str) -> Macro | None:
        with self._lock:
            for m in self._macros:
                if m.enabled and m.trigger == TRIGGER_GESTURE \
                        and m.trigger_value == gesture_kind:
                    return m
        return None

    @staticmethod
    def names_for_trigger(trigger: str) -> list[str]:
        return []

    # -- persistence ----------------------------------------------------------
    def to_list(self) -> list[dict]:
        return [m.to_dict() for m in self.all()]

    def load_list(self, data: list[dict]) -> None:
        macros = []
        for raw in data or []:
            try:
                macros.append(Macro.from_dict(raw))
            except Exception:
                continue
        with self._lock:
            self._macros = macros

    # -- execution ------------------------------------------------------------
    def run(self, macro: Macro) -> bool:
        if not macro.enabled:
            return False
        return self.run_steps(macro.actions, source="macro")

    def run_by_name(self, name: str) -> bool:
        m = self.get(name)
        return self.run(m) if m else False

    def run_steps(self, actions: list[dict], source: str = "macro") -> bool:
        if not actions:
            return False
        executor = self._executor
        if executor is None:
            return False
        from hadj_no_touch.ai.intent_engine import Intent
        ok = True
        for step in actions:
            action = step.get("action")
            params = dict(step.get("params") or {})
            intent = Intent(action=action, params=params, source=source)
            intent.description = f"Macro step: {action}"
            if not executor(intent):
                ok = False
                break
        return ok


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()