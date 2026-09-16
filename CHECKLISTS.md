# HADJ NO-TOUCH AI — Checklists

## 1. Field test (5–10 people, 1–2 weeks each)

Goal: real-world reliability numbers for the accuracy counters, not feelings.

**Setup**
- [ ] Windows 10/11, Python 3.12 (dev) *or* the packaged `HADJ-NO-TOUCH-AI-Windows.zip`
- [ ] Webcam ≥ 640×480 @ 30 fps; laptop webcam is fine
- [ ] Launch, calibrate (fingertip → screen mapping)
- [ ] First-launch voice chooser: pick engine deliberately (online Google = cloud, Vosk = local)
- [ ] Run **Test Lab → Live accuracy** (dashboard) to confirm counters tick

**Per session (each tester fills one line/session)**
| Field | How |
|------|-----|
| Date, room lighting (bright/dim/backlit, window position) | note it |
| Distance from screen / seating angle | note it |
| Session length | minutes |
| Clicks delivered & click-precision % | Test Lab after session, + screenshot |
| False triggers count | Test Lab |
| Average frame latency / % of session < 30 fps | Test Lab |
| Voice: phrases that worked / failed (3 words, FR + EN) | note exact phrase |
| Emergency stop test (CTRL+ALT+H) during a session | pass/fail |
| Any cursor "hops", shaky-tracking zones, dead zones | describe where on screen |

**After the full period**
- [ ] Collect screenshots + notes into one drive/backlog
- [ ] Read `click_drift_avg`: target < 0.05 normalized for "clean" clicks (CLEAN_DRIFT = 0.12)
- [ ] Read `click_precision`: record baseline; retune sensitivity (low/medium/high) and re-measure — must improve numerically
- [ ] List top 3 failure modes → file as GitHub issues with the numbers
- [ ] Decide: publish v2.1 with proposed gesture/calibration defaults

## 2. Release build

**Pre-build**
- [ ] `py -3.12 -m pytest tests -q` → **180 passed, 4 warnings** (update count if changed)
- [ ] UI import smoke: `py -3.12 -c "from hadj_no_touch.ui.main_window import MainWindow"`
- [ ] Bump version everywhere: `main.py`/about dialog, `web/manifest.webmanifest`, PWA copy
- [ ] Update README counts (tests, sample screenshots, hashes) if changed

**Build**
- [ ] Run `py -3.12 build_app.py` (onedir, windowed, web/ bundled)
- [ ] Smoke-run the built EXE: calibration + one gesture + one voice command + emergency stop
- [ ] Confirm expected size ~ 214,681,053 B (~205 MB) — if size changed, recompute SHA below

**Publish (GitHub release)**
- [ ] Zip: `HADJ-NO-TOUCH-AI-Windows.zip`
- [ ] Compute real hash: `Get-FileHash HADJ-NO-TOUCH-AI-Windows.zip -Algorithm SHA256`
- [ ] Publish the `.sha256` sidecar with the release
- [ ] If the hash differs from the previous release's published value, update **both** places in `web/index.html`
- [ ] Confirm the biggest claim on the PWA: verified hash, size (~205 MB), "Camera stays local"

**PWA deployment paired with release**
- [ ] Version bump in `web/sw.js` (cache bust)
- [ ] `vercel deploy --prod --yes` from `web/` (linked to project `hadj-no-touch-ai`)
- [ ] Verify live: https://web-sooty-eta-59.vercel.app — hash, size, chips, emergency-stop copy
- [ ] Confirm the wrong/stale hash is gone from `web/index.html`

**Honesty gate — final read-through (release must not ship with any of these)**
- [ ] No wrong/hardcoded SHA-256 or size on the landing pages
- [ ] No "100% offline / audio on-device / camera never…" absolutes that ignore engine: Google = cloud is stated; Vosk/SAPI = local is stated
- [ ] No simulated feature presented as real (SAPI, gaze, custom gestures are labelled experimental-unavailable)
- [ ] Dashboard badge matches the actual engine (AUDIO ONLINE · GOOGLE vs AUDIO LOCAL · VOSK)
- [ ] Local engine chosen but unavailable → voice disabled, **never** silent Google fallback

## 3. Signing / distribution (optional, recommended)

- [ ] Decide whether to buy a Windows code-signing cert (removes SmartScreen warning)
- [ ] Sign `HADJ-NO-TOUCH-AI.exe` and re-verify hash after signing
- [ ] If published: update PWA hash/size one last time after signing (signing changes bytes)