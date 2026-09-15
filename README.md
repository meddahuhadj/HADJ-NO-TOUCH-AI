# HADJ NO-TOUCH AI v2.0

A multimodal, safety-first, contactless computer-control platform for Windows 11.

> **Your hands, voice and eyes become the interface.**
> This is a *virtual/contactless interaction layer* — it does **not** turn a
> normal monitor into a touchscreen. No touch frame, no touch hardware.

Control a normal computer without touching the screen, mouse or keyboard using:

- ✋ Hand & finger gestures (air pointer, pinch click, drag, scroll, swipe)
- 🤏 Thumb+index pinch → click, double click, drag
- 👁️ Optional eye/gaze confirmation + 🧭 real head-direction control
- 🎤 Voice commands (English, French, Arabic)
- 🧠 Context-aware AI intent engine ("swipe while a video plays = next video")
- 🗂️ Broad, keyword-based **AI Action Planner** (preview → confirm → run)
- 🧩 **Macro Studio** — chain registered actions to a voice phrase, gesture or button
- ⛑️ **Safety Engine** — action registry, risk levels, confirmations, audit log
- 🔵 **Demo Mode** — simulate every action loudly, touch nothing
- 🧪 **Test Lab** — self-diagnostics with simulated inputs

## Quick start

Python 3.10–3.12 is required (MediaPipe does not support 3.13 yet).

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 main.py
```

On first launch the calibration wizard maps your webcam fingertip onto the
screen. Recalibrate any time from the dashboard or tray.

## Pipeline

```
Webcam + Microphone
  → Hand / Face / Gaze / Head tracking (MediaPipe, local)
  → Gesture + Voice recognition
  → Contextual AI Intent Engine (active app + gesture + voice + gaze + head)
  → Safety Engine gate (registry · risk level · confirmation prompt)
  → Windows Control Layer (real mouse / keyboard / window / media actions)
```

Everything that touches the OS passes through the action registry. An AI plan
or macro can only emit actions that already exist in the registry — never
arbitrary code.

## Gestures

| Gesture                 | Action                            |
|-------------------------|-----------------------------------|
| Move index finger        | Move cursor                       |
| Pinch (thumb+index)      | Left click                        |
| Double pinch             | Double click                      |
| Thumb + middle           | Right click                       |
| Hold pinch + move        | Drag                              |
| Open palm + move vertically | Scroll                        |
| Swipe left/right         | Previous / next                   |
| Open palm held 1–2 s     | Pause interaction                 |
| Fist held                | Interaction lock                  |

All gestures are filtered by confidence, debounce, cooldown, minimum
duration and jump rejection to avoid accidents.

## Voice (EN / FR / AR)

`open chrome` · `close this window` · `scroll down` · `go back` ·
`next page` · `volume up` · `mute` · `take screenshot` ·
`start presentation` · `pause` · `copy` · `paste` · `next slide` …
On hands-busy mode, voice becomes the primary channel.

Phrases you define yourself can be added in **Settings → Macro Studio &
custom commands** and are matched before anything else ("boost volume" →
`VOLUME_UP`).

## Modes

- **Hands Busy** – operate with gloves / tools, voice-first
- **Industrial** – schematics, manuals, PLC docs, dashboards
- **Medical** – DICOM / imaging viewers (not a clinical device)
- **Presentation** – slide control + laser-pointer navigation
- **Media** – YouTube / VLC / music (swipe, volume, play/pause)
- **Accessibility** – slower cursor, dwell timing, large cursor, high visibility
- **Browser / PDF / CAD / Kiosk / Personal / Custom** + automatic profile
  detection from the active application

## Head control

Optional, off by default (Settings Center). Turned left/right → previous/next
(slide, page, track); up/down → volume or zoom depending on context. The
direction must be *held* for a short time before it fires, and a cooldown
stops it hammering the system. It is a real FaceMesh-based estimate.

## Demo vs. Real

The dashboard always shows a **🔴 REAL** or **🔵 DEMO MODE** badge.

- **REAL** — actions touch your computer; sensitive ones ask first.
- **DEMO** — every action that would touch the OS is shown as
  `[DEMO] ...` in the toasts and history and nothing is executed. Pure safety
  toggles (emergency stop, pause, profile switch) stay fully functional so you
  always keep control.

## Safety

- **Action registry**: `safety.py` classifies every action as
  `safe` · `confirm` · `critical` (close window / tab = confirm; shutdown /
  restart reserved = critical).
- **Confirmation levels** (Settings Center): `none` / `smart` / `all`.
  `critical` actions always ask, no matter the level; emergency & pause
  toggles never get blocked by a prompt.
- `CTRL + ALT + H` **emergency stop** at any time (or: “stop all control”).
- Dead zones, jump rejection, cooldowns and an interaction lock.
- Big **STOP NO-TOUCH CONTROL** button on the dashboard.
- A local audit trail of every action + decision is kept in memory.

## Macro Studio

Create "work mode", "next document", "movie time"... as a sequence of
registered actions triggered by:

- a **voice phrase** ("go to work mode"),
- a **gesture** (`CIRCLE_CW`, `FIST_LOCK`, …), or
- a **button** (dashboard quick action).

Each step still passes the Safety Engine, so a macro can never bypass the
risk rules. Macros persist locally through the database.

## AI Plan suggestions

When a spoken or typed phrase isn't a built-in command, the planner may
suggest a plan ("prepare my presentation" → presentation profile + PowerPoint
+ start slideshow). The plan is shown *before* anything runs; you execute or
decline it, and each approved step still goes through the Safety Engine.

## Privacy

Camera and microphone processing is **local by default**. No camera frames
are uploaded or recorded. Toggle camera / mic, pause tracking, enable
privacy mode (blurred preview) or clear all local data from the dashboard.

## Some features marked

- Gaze tracking, custom-gesture recording, Vosk/SAPI offline voice,
  laser-pointer mode are **experimental / optional** but real; SAPI is
  reported honestly as unavailable on this build rather than faked.
- Smart-home & robot control are reserved future work and shown as
  “Coming Soon” rather than fakes.

## Tests & Test Lab

```powershell
py -3.12 -m pytest tests
```

The in-app **Test Lab** (dashboard → 🧪 Test Lab) runs the same simulated-input
checks live: gesture classifier, gesture engine, Safety registry, demo mode,
macros, planner, custom commands, head control, history — and reports
hardware-dependent tests (camera, models, voice engine) as honestly
**skipped** when the machine can't provide them.

## Web / PWA

A single-page **PWA** (offline, installable) markets the product and lets you
try the interaction live in the browser — your mouse stands in for the
air-pointer (pinch-click on hold, palm mode, scroll):

- Source: [`web/`](web) → live demo at <https://web-sooty-eta-59.vercel.app>
- Deploy/regenerate icons: see [`web/README.md`](web/README.md)
- `vercel.json` ships `sw.js` cache-first with `no-store` so updates land
  immediately

## Note

`requirements.txt` lists the production stack. `pycaw`, `vosk` and
`pytest` are optional by design — remove them if you need a leaner build.

Webcam-based spatial mapping is an *estimate*. This platform does not and
cannot claim clinical validation or physical touch detection.