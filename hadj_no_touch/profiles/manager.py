"""Profile manager: activation, auto-detection from active app, persistence."""

from __future__ import annotations

from ..config import SETTINGS
from ..logging_setup import get_logger
from .base import ALL_PROFILES, Profile
from ..database.database import Database

log = get_logger("profiles.manager")


class ProfileManager:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self.active: Profile = ALL_PROFILES.get(SETTINGS.active_profile, ALL_PROFILES["personal"])()

    def all(self) -> list[Profile]:
        return [ctor() for ctor in ALL_PROFILES.values()]

    def get(self, pid: str) -> Profile:
        ctor = ALL_PROFILES.get(pid)
        if not ctor:
            return ALL_PROFILES["personal"]()
        return ctor()

    def set_active(self, pid: str) -> Profile:
        self.active = self.get(pid)
        SETTINGS.active_profile = pid
        SETTINGS.save()
        self.active.apply()
        log.info("Active profile: %s", self.active.name)
        return self.active

    def detect_for_context(self, exe: str) -> Profile | None:
        if not SETTINGS.auto_switch_profile:
            return None
        for p in self.all():
            if p.matches_app(exe):
                return p
        return None

    def maybe_auto_switch(self, exe: str) -> bool:
        p = self.detect_for_context(exe)
        if p and p.id != self.active.id:
            self.set_active(p.id)
            return True
        return False

    def save_all(self) -> None:
        """Persist custom profile settings (incl. gesture maps)."""
        for p in self.all():
            self.db.save_profile(p)