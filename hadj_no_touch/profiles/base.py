"""Profile definition: gestures, voice mapping, sensitivity and context triggers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Settings, SETTINGS


@dataclass
class Profile:
    id: str
    name: str
    description: str = ""
    icon: str = "🖥️"
    # Explicit gesture override. Key = gesture event kind, value = action name.
    gesture_map: dict = field(default_factory=dict)
    # Voice intent extra overrides: VoiceIntent.intent -> action name.
    voice_map: dict = field(default_factory=dict)
    # Sensitivity overrides applied to the core settings.
    sensitivity: dict = field(default_factory=dict)
    # EXEs that should auto-activate this profile.
    auto_apps: list = field(default_factory=list)
    cursor_behavior: dict = field(default_factory=dict)

    def apply(self, settings: Settings = SETTINGS) -> None:
        """Apply this profile's sensitivity to the running settings."""
        for key, value in self.sensitivity.items():
            if hasattr(settings.cursor, key):
                setattr(settings.cursor, key, value)
            elif hasattr(settings.gestures, key):
                setattr(settings.gestures, key, value)

    def matches_app(self, exe: str) -> bool:
        return (exe or "").lower() in [a.lower() for a in self.auto_apps]


Personal = lambda: Profile(
    id="personal", name="Personal", icon="👤",
    description="Daily desktop use: air pointer, pinch click, swipe navigation.",
    sensitivity={"smoothing": 0.4, "speed": 1.0, "scroll_gesture_cooldown_ms": 60},
)

Presentation = lambda: Profile(
    id="presentation", name="Presentation", icon="📊",
    description="Control slides and presentations without touching the computer.",
    auto_apps=["powerpnt.exe", "wps.exe", "soffice.bin", "keynote.exe"],
    sensitivity={"smoothing": 0.5, "gesture_cooldown_ms": 400},
)

Media = lambda: Profile(
    id="media", name="Media", icon="🎬",
    description="YouTube / VLC / music players: swipe, vertical volume, pinch play.",
    auto_apps=["vlc.exe", "wmplayer.exe", "potplayer.exe", "spotify.exe", "mpc-hc.exe"],
    sensitivity={"smoothing": 0.45, "scroll_gesture_cooldown_ms": 40},
)

Industrial = lambda: Profile(
    id="industrial", name="Industrial", icon="⚙️",
    description="No-touch control for technicians: manuals, schematics, PLC docs, dashboards.",
    voice_map={"next_manual_page": "NEXT_PAGE"},
)

Medical = lambda: Profile(
    id="medical", name="Medical", icon="🏥",
    description="Contactless imaging viewers (DICOM, 3D, anatomy). Not a clinical device.",
    auto_apps=["slicer.exe", "3dslicer", "dicomviewer.exe"],
    sensitivity={"smoothing": 0.5},
)

Accessibility = lambda: Profile(
    id="accessibility", name="Accessibility", icon="♿",
    description="Slower cursor, longer dwell, high visibility and voice-first interaction.",
    sensitivity={"smoothing": 0.55, "speed": 0.7,
                 "pinch_dwell_click_ms": 380, "gesture_cooldown_ms": 500},
    cursor_behavior={"large_cursor": True, "click_delay": 0.4},
)

Kiosk = lambda: Profile(
    id="kiosk", name="Kiosk", icon="📟",
    description="Locked-down public interface: navigation only, no desktop escape.",
    sensitivity={"gesture_cooldown_ms": 500},
)

Browser = lambda: Profile(
    id="browser", name="Browser", icon="🌐",
    description="Swipe to navigate, two-finger to scroll, close tab voice command.",
    auto_apps=["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"],
    sensitivity={"smoothing": 0.4},
)

CAD = lambda: Profile(
    id="cad", name="CAD", icon="📐",
    description="Drafting software: zoom, pan, rotate with air gestures.",
    auto_apps=["autocad.exe", "inventor", "fusion360", "solidworks.exe", "sketchup.exe"],
    voice_map={"next_view": "NEXT_VIEW"},
)

PDF = lambda: Profile(
    id="pdf", name="PDF", icon="📄",
    description="Document readers: page up/down, zoom, search.",
    auto_apps=["acrord32.exe", "adobe.exe", "foxitreader.exe", "sumatrapdf.exe"],
)

HandsBusy = lambda: Profile(
    id="hands_busy", name="Hands Busy", icon="🧤",
    description="Operate while wearing gloves or holding tools: voice-first optimization.",
    voice_map={"hbt_speak": "VOICE_ONLY"},
)

Copilot = lambda: Profile(
    id="copilot", name="AI Copilot", icon="🤖",
    description="Context-aware assistance: AI interprets gestures + voice + context.",
    sensitivity={"smoothing": 0.45},
)

Custom = lambda: Profile(
    id="custom", name="Custom", icon="✨",
    description="Your personal profile: taught gestures and custom actions.",
)

ALL_PROFILES = {
    "personal": Personal, "presentation": Presentation, "media": Media,
    "industrial": Industrial, "medical": Medical, "accessibility": Accessibility,
    "kiosk": Kiosk, "browser": Browser, "cad": CAD, "pdf": PDF,
    "hands_busy": HandsBusy, "copilot": Copilot, "custom": Custom,
}