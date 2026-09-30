# HADJ NO-TOUCH OFFLINE AI 🖐️🎤👁️⚡

### Complete Touchless Computer Control — Voice + Gesture + Vision + Offline AI
**نظام تحكم متكامل بالكمبيوتر بدون لمس — صوت + إيماءات + رؤية حاسوبية + ذكاء اصطناعي محلي بدون إنترنت**

---

## 1. Overview & Vision / الرؤية العامة

**HADJ NO-TOUCH OFFLINE AI** is a professional, high-performance Windows desktop platform that enables complete, touchless computer interaction. It replaces traditional mice, keyboards, and touchscreens with an intelligent multimodal sensory layer powered by:
- **Offline Voice Recognition & SAPI Synthesis** (Arabic, French, English)
- **Computer Vision & Hand Tracking** via MediaPipe 21-landmark 3D skeletal mesh
- **Virtual Mouse & Gesture Recognizer** (Point, Pinch Click, Double Pinch, Drag, Scroll, Swipe, Thumb Up, Fist)
- **Screen Understanding & Multimodal Fusion** (Point at a screen element and say "اضغط هنا" or "افتحه")
- **Windows System Automation** (Mouse, Keyboard shortcuts, Volume, Brightness, Application Launcher, Explorer)
- **Privacy-First & 100% Offline-First Architecture** (Zero external cloud API dependencies)

---

## 2. System Architecture / بنية النظام

```
USER
  ↓
VOICE / GESTURE / CAMERA SENSORS
  ↓
LOCAL INPUT ENGINE (MediaPipe Hands + Windows Audio SAPI / Vosk)
  ↓
INTENT RECOGNITION (Multilingual Rules + Regex + Local LLM Adapter)
  ↓
COMMAND ORCHESTRATOR & MULTIMODAL FUSION
  ↓
SECURITY ENGINE (Permission Gates: LOW / MEDIUM / HIGH / CRITICAL)
  ↓
WINDOWS AUTOMATION ENGINE (PyAutoGUI + Win32 + Pycaw + SBC)
  ↓
APPLICATIONS / FILES / BROWSER / SYSTEM
  ↓
FEEDBACK (Futuristic PySide6 HUD + Offline SAPI TTS Speech Audio)
```

---

## 3. Gestures & Virtual Mouse / التحكم بالإيماءات

| Gesture / الإيماءة | Physical Hand Action | Triggered Action / الإجراء |
| :--- | :--- | :--- |
| **Index Point** (حركة السبابة) | Index extended, others curled | Smooth Virtual Mouse movement (EMA filtered) |
| **Pinch** (الإبهام + السبابة) | Thumb tip & Index tip contact | Left Click |
| **Double Pinch** | Two quick successive pinches | Double Click |
| **Pinch + Hold** | Pinch contact held > 0.35s | Drag and Drop |
| **Open Palm** (راحة اليد المفتوحة) | All 5 fingers extended | Standby / Pause cursor movement |
| **Two Fingers Up/Down** | Index + Middle extended, move hand | Vertical Smooth Scrolling |
| **Swipe Left** | Rapid horizontal sweep left | Browser / Explorer Previous |
| **Swipe Right** | Rapid horizontal sweep right | Browser / Explorer Next |
| **Thumb Up** (إبهام لأعلى) | Thumb extended up, others curled | Confirm Security Prompt (نعم / Confirm) |
| **Fist** (قبضة اليد) | All fingers tightly curled | Cancel Prompt / Emergency Stop if held 2s |

---

## 4. Voice Commands & Wake Words / التحكم الصوتي

### Wake Words
- **Arabic**: `"يا حاج"` / `"ياحاج"` / `"حاج"`
- **English**: `"Hey Hadj"` / `"Hadj"`
- **French**: `"Bonjour Hadj"`

### Emergency Stop
- `"STOP HADJ"` / `"توقف يا حاج"` / `"قف"` / `"Arrête"`
- Or hold a **Closed Fist** gesture for 2 seconds.

### Multilingual Command Examples
- **Applications**:
  - Arabic: `"افتح Chrome"` / `"افتح Word"` / `"افتح YouTube"` / `"افتح المفكرة"` / `"أغلق Chrome"`
  - French: `"Ouvre Chrome"` / `"Lance Word"` / `"Ferme la fenêtre"`
  - English: `"Open Chrome"` / `"Launch VS Code"` / `"Close window"`
- **Files & Navigation**:
  - Arabic: `"افتح Downloads"` / `"افتح ملفاتي"` / `"سطح المكتب"` / `"أنشئ مجلداً جديداً"`
  - French: `"Ouvre les téléchargements"` / `"Mes documents"` / `"Nouveau dossier"`
  - English: `"Open downloads"` / `"My documents"` / `"Open recent download"`
- **Dictation & Voice Editing**:
  - `"اكتب مرحبا بكم في تطبيقي"` (Unicode-safe direct typing)
  - `"احذف آخر كلمة"` (Delete word)
  - `"احذف الجملة"` (Delete sentence)
  - `"انتقل إلى السطر التالي"` (Enter / Newline)
  - `"ضع فاصلة"` / `"ضع نقطة"`
  - `"انسخ"` / `"الصق"` / `"قص"` / `"حدد الكل"` / `"تراجع"`
- **System & Media**:
  - `"ارفع الصوت"` / `"اخفض الصوت"` / `"اكتم الصوت"`
  - `"شغل الموسيقى"` / `"أوقف الموسيقى"` / `"التالي"` / `"السابق"`
  - `"ارفع السطوع"` / `"اخفض السطوع"`
  - `"التقط صورة للشاشة"` (Saved to Pictures/Screenshots)
- **Window Snapping & Desktops**:
  - Arabic: `"قسم الشاشة لليمين"` / `"قسم الشاشة لليسار"` / `"سطح مكتب جديد"` / `"عرض المهام"` / `"مدير المهام"`
  - French: `"Ancrer à droite"` / `"Ancrer à gauche"` / `"Nouveau bureau"` / `"Vue des tâches"` / `"Gestionnaire des tâches"`
  - English: `"Snap right"` / `"Snap left"` / `"New desktop"` / `"Task view"` / `"Task manager"`
- **Zoom & Screen Tools**:
  - `"تكبير الشاشة"` (Zoom In) / `"تصغير الشاشة"` (Zoom Out) / `"إعادة ضبط الزووم"` (Reset Zoom)
  - `"تحديث الشاشة"` (Refresh / F5)
  - `"أفرغ سلة المحذوفات"` (Empty Recycle Bin with Safety Gate)
  - `"لوحة المفاتيح"` (Toggle On-Screen Touchless Virtual Keyboard)
- **Audio Chimes & Visual Overlays**:
  - **Native Windows Audio Chimes**: Dual-frequency chimes for Wake Word, command execution, safety prompts, and emergency halt.
  - **Glowing Cursor Ring Overlay**: Floating on-screen neon crosshair that pulses on pinch click and follows virtual cursor.
  - **Floating Transparent HUD**: Persistent topmost status banner showing listening state and gestures above all apps.
- **Local Companion REST API**:
  - Runs on `http://127.0.0.1:8766` to bridge with external companion dashboards or web apps.

---

## 5. Security & Risk Engine / محرك الأمان

Every command is evaluated against strict safety tiers:
- **LOW Risk**: Volume, brightness, launching apps, switching tabs (Executed automatically).
- **MEDIUM Risk**: Closing windows, deleting single files (Configurable confirmation).
- **HIGH Risk**: Deleting directories, restarting or shutting down PC (Mandatory confirmation).
- **CRITICAL Risk**: Formatting drives, disk operations (Mandatory dual confirmation).

Confirmation can be given hands-free via:
- Voice: Say `"نعم"` or `"Yes"` or `"Oui"`
- Gesture: Show `THUMB_UP` 👍

---

## 6. Performance Profiles / أنماط الأداء

- **ECO**: 15 FPS — Ultra-low CPU footprint for energy-saving or older hardware.
- **BALANCED**: 22 FPS — Optimal balance of responsiveness and low CPU overhead.
- **PERFORMANCE**: 30 FPS — Ultra-fluid virtual cursor tracking.
- **AI MAX**: 30 FPS + Screen Vision + Local AI Intent Analysis.

---

## 7. Automatic Calibration / المعايرة التلقائية

The suite ships with no hard-coded gesture thresholds. Open **Settings → Calibration**
(or the wizard from the toolbar) and follow the eight steps:

| Step | What it measures | Result written to |
|------|------------------|-------------------|
| Devices | Enumerates cameras and microphones, greys out any that deliver no frames | `calibration.*` |
| Camera | Sustained frame rate and read→dispatch latency | `calibration.measured_fps`, `latency_ms` |
| Microphone | Ambient noise floor, speech threshold (3.5× floor, bounded) | `audio.noise_floor`, `audio.speech_threshold` |
| Hand | Confirms tracking, shows skeleton and reach overlay | — |
| Pinch | Three deliberate pinches; splits the distance histogram with Otsu | `gestures.pinch_click_threshold` |
| Reach | A 5-second sweep, padded into a forgiving active box | `gestures.active_box` |
| Adaptive | Live re-tuning window, toggled on or off | `calibration.adaptive_tuning` |
| Summary | Every value with its confidence before anything is applied | `gestures.calibrated` |

**The active box is the important one.** A camera rarely frames your whole range of
motion, so the cursor remaps the measured rectangle onto the full display. Without
it, the usable area is whatever the lens happens to see, and the edges are dead.

### Continuous learning

With `calibration.adaptive_tuning` enabled, an `AdaptiveTuner` watches a rolling
window of frames and re-tunes the pinch threshold, tremor dead zone and smoothing
factor in the background. Three properties keep it from misbehaving:

- **Rolling percentiles, not means** — one bad frame cannot move the value.
- **Hysteresis** — a candidate outside the band must persist for N consecutive
  windows before it is written, which is what stops 0.03 ⇄ 0.04 oscillation.
- **Holds its current values** — a window with too few samples, or one where the
  user never pinched, changes nothing.

A skipped or incomplete step also writes nothing: the previous value is kept.

`CalibrationSession` can be attached to a live `CameraStream` as
`camera.calibration_session`, in which case actual cursor movement is suppressed
while measuring so the calibration cannot move the pointer it is calibrating.

---

## 8. How to Launch & Run / التشغيل

### Launch on Windows:
Double click `launch.bat` or run:
```cmd
launch.bat
```

Or run directly with Python 3.12:
```powershell
& "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe" main.py
```

### Run Unit Tests:
```powershell
& "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover tests
```

---

## 9. Privacy Guarantee / ضمان الخصوصية
- **100% Offline-First**: No data leaves your machine.
- **Zero Cloud Recording**: Audio streams and camera frames are processed in volatile memory and immediately discarded.
- **Local JSONL Audit Log**: Only text metadata (command, timestamp, intent, risk level, success) is kept locally for user audit.
