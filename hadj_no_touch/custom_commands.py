"""HADJ Custom Commands.

User-defined voice commands: a spoken phrase maps to a registered action
with fixed parameters. Local-only, persisted through the database.
"""

from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass, field


@dataclass
class CustomCommand:
    phrase: str
    action: str
    params: dict = field(default_factory=dict)
    description: str = ""
    language: str = "*"          # "*" matches any detected language
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CustomCommand":
        return cls(
            phrase=str(data.get("phrase", "")),
            action=str(data.get("action", "")),
            params=dict(data.get("params", {}) or {}),
            description=str(data.get("description", "")),
            language=str(data.get("language", "*")),
            enabled=bool(data.get("enabled", True)),
        )


class CustomCommandRegistry:
    def __init__(self):
        self._commands: list[CustomCommand] = []
        self._lock = threading.RLock()

    def add(self, cmd: CustomCommand) -> str | None:
        with self._lock:
            if not cmd.phrase or not cmd.action:
                return "A command needs a phrase and an action."
            if self.get(cmd.phrase) is not None:
                return "A command with that phrase already exists."
            self._commands.append(cmd)
        return None

    def remove(self, phrase: str) -> bool:
        with self._lock:
            for i, c in enumerate(self._commands):
                if c.phrase == phrase:
                    del self._commands[i]
                    return True
        return False

    def get(self, phrase: str) -> CustomCommand | None:
        with self._lock:
            for c in self._commands:
                if c.phrase == phrase:
                    return c
        return None

    def all(self) -> list[CustomCommand]:
        with self._lock:
            return list(self._commands)

    def clear(self) -> None:
        with self._lock:
            self._commands.clear()

    # -- matching -------------------------------------------------------------
    def match(self, phrase: str, language: str = "*") -> CustomCommand | None:
        norm = _norm(phrase)
        if not norm:
            return None
        with self._lock:
            for c in self._commands:
                if not c.enabled:
                    continue
                if c.language != "*" and language.lower() != str(c.language).lower():
                    continue
                if norm == _norm(c.phrase) or _norm(c.phrase) in norm:
                    return c
        return None

    # -- persistence ----------------------------------------------------------
    def to_list(self) -> list[dict]:
        return [c.to_dict() for c in self.all()]

    def load_list(self, data: list[dict]) -> None:
        cmds = []
        for raw in data or []:
            try:
                cmds.append(CustomCommand.from_dict(raw))
            except Exception:
                continue
        with self._lock:
            self._commands = cmds


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()