# HADJ NO-TOUCH AI

A multimodal contactless computer-control platform for Windows 11.

> **Your hands, voice and eyes become the interface.**
> This is a *virtual/contactless interaction layer* — it does **not** turn a
> normal monitor into a touchscreen. No touch frame, no touch hardware.

Control a normal computer without touching the screen, mouse or keyboard using:

- ✋ Hand & finger gestures (air pointer, pinch click, drag, scroll, swipe)
- 🤏 Thumb+index pinch → click, double click, drag
- 👁️ Optional eye/gaze confirmation
- 🎤 Voice commands (English, French, Arabic)
- 🧠 Context-aware AI intent engine ("swipe while a video plays = next video")

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
  → Hand / Face / Gaze tracking (MediaPipe, local)
  → Gesture + Voice recognition
  → Contextual AI Intent Engine (active app + gesture + voice + gaze)
  → Windows Control Layer (real mouse / keyboard / window / media actions)
```

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

## Modes

- **Hands Busy** – operate with gloves / tools, voice-first
- **Industrial** – schematics, manuals, PLC docs, dashboards
- **Medical** – DICOM / imaging viewers (not a clinical device)
- **Presentation** – slide control + laser-pointer navigation
- **Media** – YouTube / VLC / music (swipe, volume, play/pause)
- **Accessibility** – slower cursor, dwell timing, large cursor, high visibility
- **Browser / PDF / CAD / Kiosk / Personal / Custom** + automatic profile
  detection from the active application

## Safety

- `CTRL + ALT + H` **emergency stop** at any time (or:
  “stop all control”)
- Sensitive actions (close window / tab) require confirmation
- Dead zones, jump rejection, cooldowns and an interaction lock
- Big **STOP NO-TOUCH CONTROL** button on the dashboard

## Privacy

Camera and microphone processing is **local by default**. No camera frames
are uploaded or recorded. Toggle camera / mic, pause tracking, enable
privacy mode (blurred preview) or clear all local data from the dashboard.

## Some features marked

- Gaze tracking, custom-gesture recording, Vosk/SAPI offline voice,
  laser-pointer mode are **experimental / optional** but real.
- Smart-home & robot control are reserved future work and shown as
  “Coming Soon” rather than fakes.

## Tests

```powershell
py -3.12 -m pytest tests
```

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