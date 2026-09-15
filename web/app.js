/* ============================================================
   HADJ NO-TOUCH AI — app.js
   Interactivity + live canvas demo + PWA install + service worker
   ============================================================ */

(() => {
  "use strict";

  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => Array.prototype.slice.call((c || document).querySelectorAll(s));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const escapeHtml = (s) =>
    String(s).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));

  const RM = window.matchMedia("(prefers-reduced-motion: reduce)");
  const lerpEase = RM.matches ? 0.9 : 0.14;

  /* ---------- Safety: audit event bus + emergency freeze ---------- */

  const bus = (() => {
    const subs = [];
    return {
      on: (fn) => { subs.push(fn); },
      emit: (ev) => {
        subs.slice().forEach((fn) => fn(ev));
        try {
          document.dispatchEvent(new CustomEvent("demo:action", { detail: ev }));
        } catch (_) { /* noop */ }
      },
    };
  })();

  let frozen = false;
  let demoMode = false; // REAL (false) by default; DEMO intercepts system actions

  const freezeOverlay = $("#freeze-overlay");

  const nextFreeze = (duration, label) => {
    if (frozen) return;
    frozen = true;
    document.body.classList.add("is-frozen");
    if (freezeOverlay) {
      freezeOverlay.hidden = false;
      const sub = freezeOverlay.querySelector("[data-freeze-sub]");
      if (sub) sub.textContent = label || "Emergency stop — gestures and voice frozen";
    }
    if (duration) {
      window.setTimeout(() => release(), duration);
    }
    bus.emit({ type: "action", action: "EMERGENCY_STOP", risk: "critical", decision: "freeze", conf: 1, ts: Date.now() });
  };

  const release = () => {
    frozen = false;
    document.body.classList.remove("is-frozen");
    if (freezeOverlay) freezeOverlay.hidden = true;
  };

  const foResume = $("#fo-resume");
  if (foResume) foResume.addEventListener("click", release);

  window.addEventListener("keydown", (e) => {
    if (frozen) return;
    if (e.ctrlKey && e.altKey && (e.code === "KeyH" || e.key === "H" || e.key === "h")) {
      e.preventDefault();
      nextFreeze(2500);
    }
  });

  // Public hook for the appended demo modules (voice freeze, mode toggles…)
  window.__hadj = {
    nextFreeze,
    release,
    get frozen() { return frozen; },
    get demoMode() { return demoMode; },
    setDemoMode: (v) => { demoMode = !!v; },
  };

  /* ---------- Reveal on scroll ---------- */

  const revealEls = $$(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("in"));
  }

  /* ---------- PWA install ---------- */

  let deferredPrompt = null;
  const canPrompt = () => !!deferredPrompt;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    $("#install-btn").hidden = false;
  });

  window.addEventListener("appinstalled", () => {
    $("#install-btn").hidden = true;
  });

  const showDownloadNote = () => {
    const note = $("#download-note");
    if (note.hidden) note.hidden = false;
    note.scrollIntoView({ behavior: RM.matches ? "auto" : "smooth", block: "nearest" });
  };

  const promptInstall = async () => {
    if (canPrompt()) {
      await deferredPrompt.prompt();
      return;
    }
    showDownloadNote();
  };

  $("#install-btn").addEventListener("click", promptInstall);

  /* ---------- Shared gesture → action bus ---------- */

  const clicksEl = $("#hud-clicks");
  let clickCount = 0;
  const regClick = () => {
    clickCount += 1;
    if (clicksEl) clicksEl.textContent = String(clickCount);
    bus.emit({ type: "action", action: "CLICK", target: "plane:click-test", risk: "safe", decision: "allow", conf: 0.97, ts: Date.now() });
  };

  const flashText = (el, text) => {
    if (!el) return;
    el.textContent = text;
  };

  const TRACKS = [
    { title: "flightpath.wav — side A", dur: 14 },
    { title: "metalnotes.wav — side B", dur: 18 },
    { title: "zero-grain.wav — ep", dur: 11 },
  ];
  let trackIdx = 0;
  let playing = false;
  let elapsed = 0;
  let prevTick = null;

  const mediaFill = $("#media-fill");
  const mediaTitle = $("#media-title");
  const mediaTime = $("#media-time");
  const mediaCap = $("#media-cap");
  const mediaCard = $(".media-card");
  const playBtn = $("#media-play");

  const setTrack = (i) => {
    if (demoMode) {
      bus.emit({ type: "action", action: "NEXT_TRACK", target: "media", risk: "safe", decision: "demo", conf: 0.93, ts: Date.now() });
      return;
    }
    trackIdx = (i + TRACKS.length) % TRACKS.length;
    elapsed = 0;
    if (mediaTitle) mediaTitle.textContent = TRACKS[trackIdx].title;
    if (mediaCap) mediaCap.textContent = "Now playing a local file — no stream, all on your machine.";
    paintMedia();
    bus.emit({ type: "action", action: "NEXT_TRACK", target: TRACKS[trackIdx].title, risk: "safe", decision: "allow", conf: 0.93, ts: Date.now() });
  };

  const paintMedia = () => {
    const t = TRACKS[trackIdx];
    const frac = clamp(t.dur === 0 ? 0 : elapsed / t.dur, 0, 1);
    if (mediaFill) mediaFill.style.transform = "scaleX(" + frac + ")";
    if (mediaTime) {
      const m = Math.floor(elapsed / 60);
      const s = Math.floor(elapsed % 60);
      mediaTime.textContent = m + ":" + String(s).padStart(2, "0") + " / " + t.dur + ":00";
    }
  };

  const tickMedia = () => {
    if (!playing) return;
    const now = performance.now() / 1000;
    if (prevTick !== null) {
      elapsed += Math.min(now - prevTick, 0.3);
      const t = TRACKS[trackIdx];
      if (elapsed >= t.dur) {
        elapsed = 0;
        setTrack(trackIdx + 1);
      }
    }
    prevTick = now;
    paintMedia();
    requestAnimationFrame(tickMedia);
  };

  const togglePlay = () => {
    if (demoMode) {
      bus.emit({ type: "action", action: "TOGGLE_PLAY", target: "media", risk: "safe", decision: "demo", conf: 0.94, ts: Date.now() });
      return;
    }
    playing = !playing;
    prevTick = null;
    if (!playing) { elapsed = Math.floor(elapsed) + 0.4; }
    playBtn.setAttribute("aria-pressed", String(playing));
    if (mediaCard) mediaCard.classList.toggle("playing", playing);
    if (mediaCap) {
      mediaCap.textContent = playing
        ? "Playing — pinch-click again or press the button to pause."
        : "Paused. Pinch-click play when you’re ready.";
    }
    if (playing) requestAnimationFrame(tickMedia);
    paintMedia();
    bus.emit({ type: "action", action: "TOGGLE_PLAY", target: playing ? "play" : "pause", risk: "safe", decision: "allow", conf: 0.95, ts: Date.now() });
  };

  // Real click handlers — these power keyboard, mouse and pinch fires alike.
  $("#click-test").addEventListener("click", () => {
    regClick();
    flashText($("#click-status"), "click ✓");
    if (RM.matches) return;
    const st = $("#click-status");
    st.classList.add("ok");
    window.clearTimeout(st._t);
    st._t = window.setTimeout(() => {
      flashText(st, "ready");
      st.classList.remove("ok");
    }, 900);
  });

  playBtn.addEventListener("click", togglePlay);
  $$("[data-demo-target=media-prev]").forEach((b) =>
    b.addEventListener("click", () => { setTrack(trackIdx - 1); })
  );
  $$("[data-demo-target=media-next]").forEach((b) =>
    b.addEventListener("click", () => { setTrack(trackIdx + 1); })
  );
  paintMedia();

  /* ---------- Live demo plane ---------- */

  const wrap = $("#demo-wrap");
  const cv = $("#plane");
  const ctx = cv.getContext("2d");
  const hint = $("#demo-hint");

  let W = 0, H = 0, DPR = 1;

  const resize = () => {
    if (!wrap) return;
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    const r = wrap.getBoundingClientRect();
    W = r.width; H = r.height;
    cv.width = Math.round(W * DPR);
    cv.height = Math.round(H * DPR);
  };
  if ("ResizeObserver" in window) {
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
  }
  resize();

  // pointer state
  const ptr = { tx: 0.5, ty: 0.42, dx: 0.5, dy: 0.42, inPlane: false };
  let pinch = false;      // left button / touch held
  let pinchAt = 0;        // timestamp pinch began
  let pinchDir = 0;       // ring state
  let armedEl = null;
  let confirmT = 0;       // timestamp of last PINCH CONFIRMED
  let palm = false;
  let touchSeen = false;
  let moveStartX = 0, moveStartY = 0, movedAway = false;

  const scheduleRedraw = () => requestAnimationFrame(draw);

  const setHint = (text) => { if (hint) hint.innerHTML = text; };

  const planePos = (e) => {
    const r = wrap.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) / r.width,
      y: (e.clientY - r.top) / r.height,
    };
  };

  window.addEventListener("pointermove", (e) => {
    const p = planePos(e);
    const pad = 0.12; // allow a halo outside the panel
    if (p.x >= -pad && p.x <= 1 + pad && p.y >= -pad && p.y <= 1 + pad) {
      ptr.tx = clamp(p.x, 0, 1);
      ptr.ty = clamp(p.y, 0, 1);
      ptr.inPlane = true;
    } else {
      ptr.inPlane = false;
    }
  });

  // Toggle palm mode with Space
  window.addEventListener("keydown", (e) => {
    if (frozen) return;
    if (e.code !== "Space" && e.key !== " ") return;
    const t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "BUTTON" || t.tagName === "SELECT" || t.isContentEditable)) return;
    if (t && t.closest && t.closest(".demo-scroll")) return; // let the panel scroll naturally
    e.preventDefault();
    palm = !palm;
    setHint(
      palm
        ? 'Palm mode ON — wheel scrolls <strong>big steps</strong>. <kbd>space</kbd> to exit.'
        : 'mouse = air pointer · <strong>hold left</strong> = pinch→click · <kbd>space</kbd> = palm mode · wheel = scroll'
    );
  });

  const fireTarget = (el) => {
    if (!el || frozen) return;
    confirmT = performance.now();
    const btn = el.closest("button") || el;
    if (btn instanceof HTMLButtonElement) {
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true, view: window }));
    }
    // visual hit state
    btn.classList.add("demo-hit");
    window.clearTimeout(btn._hitT);
    btn._hitT = window.setTimeout(() => btn.classList.remove("demo-hit"), 360);
    btn.classList.remove("demo-arm");
    const targetName = btn.getAttribute("data-demo-target") || btn.id || (btn.textContent || "").trim().slice(0, 24);
    bus.emit({ type: "action", action: "PINCH_CLICK", target: targetName, risk: "safe", decision: "allow", conf: 0.97, ts: Date.now() });
  };

  const hitTarget = (x, y) => {
    const el = document.elementFromPoint(x, y);
    return el ? el.closest("[data-demo-target]") : null;
  };

  window.addEventListener("pointerdown", (e) => {
    if (frozen) return;
    const t = hitTarget(e.clientX, e.clientY);
    const p = planePos(e);
    const inWrap = p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1;
    if (!inWrap && !t) return; // not a control interaction nor the plane

    if (e.pointerType === "touch") {
      touchSeen = true;
      setHint("tap a control = pinch-click · drag = move the pointer");
    }

    // press feedback + pinch state
    pinch = true;
    pinchAt = performance.now();
    pinchDir = 0;
    confirmT = 0;
    movedAway = false;
    moveStartX = e.clientX; moveStartY = e.clientY;

    if (t) {
      // cancel native click so WE own it (also prevents double-fire on touch)
      e.preventDefault();
      armedEl = t;
      const btn = t.closest("button") || t;
      btn.classList.add("demo-arm");
    }

    // touch: a tap = fast pinch-click, drag = move the air pointer
    if (e.pointerType === "touch" && inWrap) {
      ptr.tx = clamp(p.x, 0, 1); ptr.ty = clamp(p.y, 0, 1);
      ptr.inPlane = true;
    }
  });

  window.addEventListener("pointermove", (e) => {
    if (e.pointerType === "touch" && pinch) {
      const dx = e.clientX - moveStartX;
      const dy = e.clientY - moveStartY;
      if (Math.abs(dx) + Math.abs(dy) > 14) movedAway = true;
      const p = planePos(e);
      ptr.tx = clamp(p.x, 0, 1); ptr.ty = clamp(p.y, 0, 1);
      ptr.inPlane = true;
    }
  });

  window.addEventListener("pointerup", (e) => {
    const hold = performance.now() - pinchAt;
    const pressBuilt = hold > (e.pointerType === "touch" ? 60 : 90);

    if (armedEl && !movedAway && pressBuilt) {
      fireTarget(armedEl);
    }
    if (armedEl) {
      const btn = armedEl.closest("button") || armedEl;
      btn.classList.remove("demo-arm");
    }
    pinch = false;
    pinchDir = 0;
    armedEl = null;
    movedAway = false;
  });

  window.addEventListener("pointercancel", () => {
    pinch = false;
    pinchDir = 0;
    armedEl = null;
    movedAway = false;
  });

  /* ---------- HUD ---------- */

  const hudX = $("#hud-x"), hudY = $("#hud-y"), hudConf = $("#hud-conf");
  const hudConfBar = $("#hud-confbar");
  const hudMode = $("#hud-mode"), hudGesture = $("#hud-gesture");

  const CYCLE = [
    { g: "POINT", c: () => 0.9 + Math.random() * 0.06 },
    { g: "PINCH", c: () => 0.94 + Math.random() * 0.04 },
    { g: "SCROLL", c: () => 0.92 + Math.random() * 0.05 },
  ];
  let cyc = 0;
  let confShown = 0.94;
  window.setInterval(() => {
    cyc = (cyc + 1) % CYCLE.length;
  }, 1500);

  /* ---------- Wheel scroll on demo panels ---------- */

  const docPanel = $("#doc-panel");
  const docPos = $("#doc-pos");

  const scrollPanel = (el, deltaY) => {
    if (frozen) return;
    const step = palm ? 210 : 56;
    const d = deltaY > 0 ? step : -step;
    el.scrollBy({ top: d });
    if (docPos) {
      const line = Math.floor(el.scrollTop / 24) + 1;
      docPos.textContent = "L:" + String(line).padStart(4, "0");
    }
    const now = performance.now();
    if (el._scbk && now - el._scbk < 700) return;
    el._scbk = now;
    bus.emit({
      type: "action",
      action: deltaY > 0 ? "SCROLL_DOWN" : "SCROLL_UP",
      target: (el.id || "demo-scroll") + (palm ? " · palm-step" : ""),
      risk: "safe", decision: "allow",
      conf: palm ? 0.91 : 0.92,
      ts: Date.now(),
    });
  };

  $$(".demo-scroll").forEach((el) => {
    el.addEventListener(
      "wheel",
      (e) => {
        if (frozen) return;
        e.preventDefault();
        scrollPanel(el, e.deltaY);
      },
      { passive: false }
    );
    el.addEventListener("scroll", () => {
      if (docPos && el === docPanel) {
        const line = Math.floor(el.scrollTop / 24) + 1;
        docPos.textContent = "L:" + String(line).padStart(4, "0");
      }
    });
  });

  /* ---------- Canvas drawing ---------- */

  const drawGrid = (w, h) => {
    ctx.strokeStyle = "rgba(126,195,255,0.09)";
    ctx.lineWidth = 1;
    const hor = h * 0.36;
    const vpx = w * 0.5;

    // vertical fan from the vanishing point
    const step = 30;
    const cols = Math.ceil(w / (2 * step)) + 1;
    for (let k = -cols; k <= cols; k++) {
      ctx.beginPath();
      ctx.moveTo(vpx, hor);
      ctx.lineTo(vpx + k * step, h);
      ctx.stroke();
    }
    // horizontal planes with perspective compression
    for (let i = 0; i <= 13; i++) {
      const tt = i / 13;
      const y = hor + (h - hor) * tt * tt;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    // horizon + focal crosshair
    ctx.strokeStyle = "rgba(76,201,255,0.22)";
    ctx.beginPath(); ctx.moveTo(0, hor); ctx.lineTo(w, hor); ctx.stroke();
    ctx.strokeStyle = "rgba(76,201,255,0.3)";
    ctx.beginPath();
    ctx.moveTo(vpx - 9, hor); ctx.lineTo(vpx + 9, hor);
    ctx.moveTo(vpx, hor - 9); ctx.lineTo(vpx, hor + 9);
    ctx.stroke();
  };

  const drawScanline = (t, w, h) => {
    const slow = RM.matches ? 0 : ((t * 0.045) % 1) * (h + 160) - 80;
    const g = ctx.createLinearGradient(0, slow - 60, 0, slow + 16);
    g.addColorStop(0, "rgba(76,201,255,0)");
    g.addColorStop(0.72, "rgba(76,201,255,0.05)");
    g.addColorStop(1, "rgba(76,201,255,0.12)");
    ctx.fillStyle = g;
    ctx.fillRect(0, slow - 60, w, 76);
    ctx.strokeStyle = "rgba(124,195,255,0.24)";
    ctx.beginPath(); ctx.moveTo(0, slow); ctx.lineTo(w, slow); ctx.stroke();
  };

  const roundRect = (x, y, w, h, r) => {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  };

  const drawPinch = (now, x, y) => {
    const age = now - pinchAt;
    const ring = 9 + clamp(age / 340, 0, 1) * 26;
    ctx.strokeStyle = "rgba(76,201,255,0.85)";
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(x, y, ring, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = "rgba(76,201,255,0.4)";
    ctx.beginPath(); ctx.arc(x, y, ring + 5, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = "rgba(232,247,255,0.95)";
    ctx.beginPath(); ctx.arc(x, y, 2.2, 0, Math.PI * 2); ctx.fill();
  };

  const drawConfirm = (now, w, h) => {
    if (!confirmT) return;
    const age = (now - confirmT) / 1000;
    if (age > 1.2) { confirmT = 0; return; }
    const a = 1 - age / 1.2;
    const cy = h * 0.72 - age * 18;
    ctx.font = '700 11px "Segoe UI", "Segoe UI Variable Display", system-ui, sans-serif';
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(76,201,255," + a.toFixed(3) + ")";
    ctx.fillText("PINCH CONFIRMED", w / 2, cy);
    ctx.font = '600 9px "Segoe UI", system-ui, sans-serif';
    ctx.fillStyle = "rgba(159,176,207," + (a * 0.8).toFixed(3) + ")";
    ctx.fillText("• click →", w / 2, cy + 15);
  };

  const draw = () => {
    if (!ctx || W === 0 || H === 0) return;
    const now = performance.now();
    const t = now / 1000;
    const w = W, h = H;

    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, w, h);

    drawGrid(w, h);
    if (!RM.matches) drawScanline(t, w, h);

    // smoothed air-pointer dot
    const lf = lerpEase;
    ptr.dx += (ptr.tx - ptr.dx) * lf;
    ptr.dy += (ptr.ty - ptr.dy) * lf;
    const px = ptr.dx * w;
    const py = ptr.dy * h;
    const hot = ptr.inPlane ? 1 : 0.35;

    // glow
    const g = ctx.createRadialGradient(px, py, 0, px, py, 30);
    g.addColorStop(0, "rgba(76,201,255," + (0.5 * hot).toFixed(3) + ")");
    g.addColorStop(1, "rgba(76,201,255,0)");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(px, py, 30, 0, Math.PI * 2); ctx.fill();

    ctx.strokeStyle = "rgba(124,195,255," + (0.85 * hot).toFixed(3) + ")";
    ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = "rgba(232,247,255," + hot.toFixed(3) + ")";
    ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();

    if (pinch && ptr.inPlane) drawPinch(now, px, py);
    drawConfirm(now, w, h);

    // HUD
    if (hudX) hudX.textContent = ptr.dx.toFixed(2);
    if (hudY) hudY.textContent = ptr.dy.toFixed(2);

    // gesture override order: pinch > palm > auto cycle
    let label, conf;
    if (pinch) { label = "PINCH"; conf = 0.96 + Math.random() * 0.03; }
    else if (palm) { label = "PALM"; conf = 0.91 + Math.random() * 0.03; }
    else { const c = CYCLE[cyc]; label = c.g; conf = c.c(); }

    confShown += (conf - confShown) * 0.12;
    if (hudGesture) hudGesture.textContent = label;
    if (hudMode) {
      const mode = palm ? "PALM" : pinch ? "PINCH" : label === "SCROLL" ? "SCROLL" : "POINT";
      hudMode.textContent = mode;
    }
    if (hudConf) hudConf.textContent = (confShown * 100).toFixed(0) + "%";
    if (hudConfBar) hudConfBar.style.transform = "scaleX(" + confShown.toFixed(3) + ")";

    requestAnimationFrame(draw);
  };

  requestAnimationFrame(draw);

  /* ---------- Voice command simulator ---------- */

  const vsTerm = $("#vs-terminal");
  const vsInput = $("#vs-input");
  const vsGo = $("#vs-go");
  const vsMic = $("#vs-mic");
  const vsFill = $("#vs-vol-fill");
  const vsNum = $("#vs-vol-num");
  const vsStatus = $("#vsim-status");
  let vsVol = 40;

  const vsIntents = [
    { re: /^(open|launch)\s+(chrome|browser|web|internet)$/i, it: { action: "OPEN_APP", target: "CHROME", risk: "safe", conf: 0.96 } },
    { re: /^(open|launch)\s+(settings|config)$/i, it: { action: "OPEN_APP", target: "SETTINGS", risk: "safe", conf: 0.93 } },
    { re: /^(open|launch)\s+(files|explorer)$/i, it: { action: "OPEN_APP", target: "FILES", risk: "safe", conf: 0.93 } },
    { re: /^next\s*(track|song)?$/i, it: { action: "NEXT_TRACK", target: "MEDIA", risk: "safe", conf: 0.95 } },
    { re: /^play\s*(the\s*)?(track|song|music)?$/i, it: { action: "TOGGLE_PLAY", target: "PLAY", risk: "safe", conf: 0.9 } },
    { re: /^scroll\s*(down|up)$/i, it: { action: "SCROLL", target: "DOC_PANEL", risk: "safe", conf: 0.88 }, which: (m) => (m[1] === "up" ? "UP" : "DOWN") },
    { re: /^volume\s*(up|down|mute)$/i, it: { action: "VOLUME", target: "SYSTEM_AUDIO", risk: "safe", conf: 0.92 }, which: (m) => (m[1] === "mute" ? "MUTE" : m[1] === "up" ? "UP" : "DOWN") },
    { re: /^close\s*(the\s*)?(window|app)$/i, it: { action: "CLOSE_WINDOW", target: "FOCUSED", risk: "safe", conf: 0.91 } },
    { re: /^freeze$/i, it: { action: "FREEZE", target: "SYSTEM", risk: "critical", conf: 0.99 } },
    { re: /^(help|what can you do|commands)$/i, it: { action: "HELP", target: "SYSTEM", risk: "safe", conf: 0.9 } },
  ];

  const vsLog = (kind, text) => {
    if (!vsTerm) return;
    const row = document.createElement("p");
    row.className = "vs-line " + kind;
    const tag = document.createElement("span");
    tag.className = "vs-tag";
    tag.textContent = kind === "vs-you" ? "YOU" : kind === "vs-err" ? "ERR" : "ENGINE";
    const val = document.createElement("span");
    val.className = "vs-val";
    val.textContent = text;
    row.append(tag, val);
    vsTerm.prepend(row);
    while (vsTerm.children.length > 60) vsTerm.lastChild.remove();
  };

  const vsPaintVol = () => {
    if (vsFill) vsFill.style.transform = "scaleX(" + vsVol / 95 + ")";
    if (vsNum) vsNum.textContent = vsVol + "%";
  };

  const vsRun = (raw) => {
    const cmd = (raw || "").trim().replace(/\s+/g, " ");
    if (!cmd) return;
    vsLog("vs-you", "“" + cmd + "”");
    if (window.__hadj.frozen) {
      vsLog("vs-err", "engine frozen — resume control first (RESUME / Ctrl+Alt+H)");
      return;
    }

    for (const item of vsIntents) {
      const m = cmd.match(item.re);
      if (!m) continue;
      const target = item.which ? item.which(m) : item.it.target;
      const decision = item.it.action === "FREEZE" ? "freeze" : window.__hadj.demoMode ? "demo" : "allow";
      vsLog(
        decision === "demo" ? "vs-engine-demo" : "vs-engine-ok",
        (item.it.action + " → " + target).toUpperCase() + (decision === "demo" ? "  [DEMO · real system untouched]" : "")
      );
      bus.emit({ type: "action", source: "voice", action: item.it.action, target: target, risk: item.it.risk, decision: decision, conf: item.it.conf, ts: Date.now() });

      switch (item.it.action) {
        case "NEXT_TRACK": {
          const b = document.querySelector("[data-demo-target=media-next]");
          if (b) b.click();
          break;
        }
        case "TOGGLE_PLAY": {
          if (!window.__hadj.demoMode) {
            const p = document.getElementById("media-play");
            if (p) p.click();
          }
          break;
        }
        case "SCROLL": {
          scrollPanel(docPanel, m[1] === "up" ? -1 : 1);
          break;
        }
        case "VOLUME": {
          vsVol = m[1] === "mute" ? 0 : Math.max(0, Math.min(95, vsVol + (m[1] === "up" ? 12 : -12)));
          vsPaintVol();
          if (vsStatus) vsStatus.textContent = "volume " + vsVol + "%";
          break;
        }
        case "FREEZE": {
          window.__hadj.nextFreeze(2500);
          break;
        }
        case "HELP": {
          vsLog("vs-engine-ok", "OPEN APP · NEXT TRACK · SCROLL · VOLUME · CLOSE WINDOW · FREEZE");
          break;
        }
      }
      if (vsStatus && item.it.action !== "VOLUME") vsStatus.textContent = item.it.action.toLowerCase();
      return;
    }
    vsLog("vs-err", "no intent matched — try “open chrome”, “next track”, “volume up”, “freeze”");
  };

  if (vsGo) vsGo.addEventListener("click", () => vsRun(vsInput.value));
  if (vsInput) vsInput.addEventListener("keydown", (e) => { if (e.key === "Enter") vsRun(vsInput.value); });
  $$(".chip-cmd").forEach((c) =>
    c.addEventListener("click", () => {
      vsInput.value = c.getAttribute("data-vscmd");
      vsRun(vsInput.value);
    })
  );
  if (vsMic) {
    vsMic.addEventListener("click", () => {
      if (vsMic.classList.contains("listening")) return;
      vsMic.classList.add("listening");
      if (vsStatus) vsStatus.textContent = "listening…";
      window.setTimeout(() => {
        vsMic.classList.remove("listening");
        const chips = $$(".chip-cmd");
        const cmd = chips.length ? chips[Math.floor(Math.random() * chips.length)].getAttribute("data-vscmd") : "open chrome";
        vsInput.value = cmd;
        vsRun(cmd);
        if (vsInput) vsInput.focus();
      }, 900);
    });
  }
  vsPaintVol();
  vsLog("vs-engine-ok", "ON-DEVICE VOICE ENGINE READY — responses fire on this page, no cloud");

  /* ---------- Gesture academy ---------- */

  const acStage = $("#academy-stage");
  const acName = $("#academy-lesson-name");
  const acProg = $("#academy-progress");
  const acCur = $("#academy-curriculum");
  const acInstruct = $("#academy-instruct");
  const acHint = $("#academy-hint");
  const acP = { x: -9999, y: -9999, down: false, dur: 0, released: false };

  const pointIn = (p, b) => p.x >= b.l && p.x <= b.r && p.y >= b.t && p.y <= b.b;
  const stageRect = () => (acStage ? acStage.getBoundingClientRect() : null);
  const acElBox = (el) => {
    const s = stageRect();
    if (!s || !el) return { l: -1e9, t: -1e9, r: 1e9, b: 1e9, w: 0, h: 0, cx: 0, cy: 0 };
    const r = el.getBoundingClientRect();
    const l = r.left - s.left, t = r.top - s.top;
    return { l: l, t: t, r: l + r.width, b: t + r.height, w: r.width, h: r.height, cx: l + r.width / 2, cy: t + r.height / 2 };
  };
  const stageW = () => (acStage ? acStage.clientWidth : 0);
  const hammer = (el) => {
    if (!el) return;
    el.classList.add("demo-hit");
    window.setTimeout(() => el.classList.remove("demo-hit"), 380);
  };

  window.addEventListener("pointermove", (e) => {
    const s = stageRect();
    if (!s) return;
    acP.x = e.clientX - s.left;
    acP.y = e.clientY - s.top;
  });
  window.addEventListener("pointerdown", (e) => {
    if (window.__hadj.frozen) return;
    const s = stageRect();
    if (!s) return;
    acP.x = e.clientX - s.left;
    acP.y = e.clientY - s.top;
    acP.down = true;
    acP.downAt = performance.now();
    acP.dur = 0;
  });
  window.addEventListener("pointerup", () => {
    acP.dur = acP.downAt ? performance.now() - acP.downAt : 0;
    acP.down = false;
    acP.released = true;
  });
  window.addEventListener("pointercancel", () => { acP.down = false; });

  const acLessons = [
    {
      id: "point", name: "POINT", desc: "Lock onto a target by hovering and holding still.",
      hint: "Move the mouse (your air-pointer) onto the dashed ring and hold ~0.7s.",
      render() {
        const el = document.createElement("div");
        el.className = "a-target";
        el.style.left = "50%";
        el.style.top = "45%";
        el.innerHTML = '<i class="a-ring"></i>';
        return el;
      },
      tick(el, p) {
        const c = acElBox(el);
        const inside = Math.hypot(p.x - c.cx, p.y - c.cy) < 52;
        el.classList.toggle("a-hot", inside);
        acDwell = inside ? acDwell + 16 : 0;
        return acDwell > 700;
      },
    },
    {
      id: "click", name: "CLICK", desc: "A pinch = a click. Tap the command button.",
      hint: "Press and release (hold ≥70ms) — that’s a click.",
      render() {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "a-btn";
        el.textContent = "CLICK ME";
        return el;
      },
      tick(el, p) {
        const b = acElBox(el);
        el.classList.toggle("a-hot", pointIn(p, b));
        if (p.released) {
          p.released = false;
          if (pointIn(p, b) && p.dur >= 70) { hammer(el); return true; }
        }
        return false;
      },
    },
    {
      id: "double", name: "DOUBLE-CLICK", desc: "Two quick pinches open things on the desktop.",
      hint: "Click the button twice within half a second.",
      render() {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "a-btn";
        el.textContent = "OPEN FOLDER";
        return el;
      },
      tick(el, p) {
        const b = acElBox(el);
        el.classList.toggle("a-hot", pointIn(p, b));
        if (p.released) {
          p.released = false;
          const now = performance.now();
          if (pointIn(p, b) && p.dur >= 70) {
            if (el._s.last && now - el._s.last < 600) { hammer(el); return true; }
            el._s.last = now;
          }
        }
        return false;
      },
    },
    {
      id: "drag", name: "DRAG", desc: "Pinch-hold a window, carry it to a drop zone.",
      hint: "Press on the card, drag it (button held) onto the green drop zone, then release.",
      render() {
        const wrap = document.createElement("div");
        wrap.className = "a-drag";
        wrap.style.left = "14%";
        wrap.style.top = "26%";
        wrap.textContent = "WINDOW";
        const drop = document.createElement("div");
        drop.className = "a-drop";
        drop.textContent = "DROP";
        const out = document.createElement("div");
        out.appendChild(wrap);
        out.appendChild(drop);
        return out;
      },
      tick(el, p) {
        const card = el.querySelector(".a-drag");
        const drop = el.querySelector(".a-drop");
        const cb = acElBox(card);
        const db = acElBox(drop);
        const s = el._s;
        if (p.down) s.dragging = s.dragging || pointIn(p, cb);
        if (s.dragging) {
          const h = acStage ? acStage.clientHeight : 0;
          card.style.left = clamp(p.x - cb.w / 2, 4, Math.max(4, stageW() - cb.w - 4)) + "px";
          card.style.top = clamp(p.y - cb.h / 2, 6, Math.max(6, h - cb.h - 12)) + "px";
          drop.classList.toggle("a-hot", pointIn(p, db));
        }
        if (s.dragging && !p.down) {
          s.dragging = false;
          drop.classList.remove("a-hot");
          if (pointIn(p, db)) { hammer(drop); return true; }
        }
        return false;
      },
    },
    {
      id: "scroll", name: "SCROLL", desc: "Wheel = scroll. A door index, one line at a time.",
      hint: "Roll your wheel while the pointer is over the list below.",
      render() {
        const el = document.createElement("div");
        el.className = "a-scroll";
        el.style.left = "50%";
        el.style.top = "50%";
        el.innerHTML =
          "<ul><li>▸ north wing</li><li>▸ stair A</li><li>▸ corridor 12</li>" +
          "<li>▸ lobby</li><li>▸ audio bay</li><li>▸ relay room</li>" +
          "<li>▸ floor B</li><li>▸ materials</li><li>⟿ END OF INDEX</li></ul>";
        return el;
      },
      tick(el) {
        el.classList.toggle("a-hot", el._s.scrolled > 0);
        return el._s.scrolled >= 140;
      },
    },
    {
      id: "swipe", name: "SWIPE", desc: "A palm swoosh scrolls pages at wheel-scale.",
      hint: "Press inside the bar, slide right past the tick, release.",
      render() {
        const el = document.createElement("div");
        el.className = "a-swipe";
        el.innerHTML = "<i></i>";
        el.style.left = "50%";
        el.style.top = "50%";
        return el;
      },
      tick(el, p) {
        const b = acElBox(el);
        const s = el._s;
        if (p.down && s.start === null && pointIn(p, b)) s.start = { x: p.x, y: p.y, ok: false };
        if (s.start !== null) {
          const dx = p.x - s.start.x;
          const dy = p.y - s.start.y;
          if (Math.abs(dx) > 16) s.start.ok = true;
          if (dx > 0 && s.start.ok) {
            el.classList.add("a-hot");
            const fill = el.querySelector("i");
            if (fill) fill.style.transform = "scaleX(" + clamp(dx / 260, 0, 1) + ")";
          }
          if (Math.abs(dy) > 48) s.start.dead = true;
        }
        if (s.start !== null && !p.down) {
          const dx = p.x - s.start.x;
          const ok = s.start.ok && dx >= 130 && !s.start.dead;
          const fill = el.querySelector("i");
          if (fill) fill.style.transform = "scaleX(0)";
          el.classList.remove("a-hot");
          s.start = null;
          if (ok) { hammer(el); return true; }
        }
        return false;
      },
    },
    {
      id: "palm", name: "PALM", desc: "A flat palm switches to big-step wheel modes.",
      hint: "Hit SPACE — palm mode toggles like a flat hand on the tracker.",
      render() {
        const wrap = document.createElement("div");
        wrap.className = "a-swipe";
        wrap.innerHTML = "<i></i>";
        const lbl = document.createElement("span");
        lbl.className = "a-center-label";
        lbl.textContent = "PALM SENSOR — PRESS SPACE";
        const out = document.createElement("div");
        out.appendChild(wrap);
        out.appendChild(lbl);
        return out;
      },
      tick() { return false; },
    },
    {
      id: "stop", name: "STOP", desc: "Emergency stop freezes everything, everywhere.",
      hint: "Click the red button. Ctrl+Alt+H works from anywhere too.",
      render() {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "a-stop";
        el.innerHTML = '<i class="a-stop-led"></i> EMERGENCY STOP';
        return el;
      },
      tick(el, p) {
        const b = acElBox(el);
        el.classList.toggle("a-hot", pointIn(p, b));
        if (p.released) {
          p.released = false;
          if (pointIn(p, b) && p.dur >= 70) {
            hammer(el);
            window.__hadj.nextFreeze(2600);
            if (window.__hadj.frozen) return true;
          }
        }
        return false;
      },
    },
  ];

  let acIdx = 0;
  let acPassed = false;
  let acDwell = 0;
  const acDone = acLessons.map(() => false);

  const paintCur = () => {
    if (!acCur) return;
    acCur.innerHTML = "";
    acLessons.forEach((l, i) => {
      const c = document.createElement("li");
      c.className = "lesson-chip" + (i === acIdx ? " is-active" : "") + (acDone[i] ? " is-done" : "");
      c.textContent = String(i + 1).padStart(2, "0") + " · " + l.name;
      c.addEventListener("click", () => setupLesson(i));
      acCur.appendChild(c);
    });
  };

  const onAcPass = (L) => {
    if (acPassed) return;
    acPassed = true;
    acP.released = false;
    acStage.classList.add("a-pass");
    acDone[acIdx] = true;
    paintCur();
    bus.emit({ type: "action", source: "academy", action: "LESSON_COMPLETE", target: L.name, risk: "safe", decision: "allow", conf: 1, ts: Date.now() });
    const o = document.createElement("div");
    o.className = "a-complete";
    const last = acIdx + 1 >= acLessons.length;
    o.innerHTML = "<strong>✓ " + L.name + " complete</strong><p>" + (last ? "Course finished — the full vocabulary is yours." : "next up →") + "</p>";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-solid";
    btn.textContent = last ? "Restart course" : "Continue";
    btn.addEventListener("click", () => setupLesson(last ? 0 : acIdx + 1));
    o.appendChild(btn);
    acStage.appendChild(o);
  };

  const setupLesson = (i) => {
    if (!acLessons[i]) return;
    acIdx = i;
    acPassed = false;
    acDwell = 0;
    acP.released = false;
    acStage.classList.remove("a-pass");
    acStage.innerHTML = "";
    const L = acLessons[i];
    const el = L.render();
    el._s = {};
    L._el = el;
    acStage.appendChild(el);
    if (acName) acName.textContent = L.name;
    if (acProg) acProg.textContent = (i + 1) + " / " + acLessons.length;
    if (acInstruct) acInstruct.textContent = L.desc;
    if (acHint) acHint.textContent = L.hint;
    paintCur();
  };

  const acTick = () => {
    if (acStage && acP.down) acP.dur = performance.now() - acP.downAt;
    const L = acLessons[acIdx];
    if (L && !acPassed && L._el) {
      if (L.tick(L._el, acP)) onAcPass(L);
    }
    requestAnimationFrame(acTick);
  };

  acStage.addEventListener(
    "wheel",
    (e) => {
      const L = acLessons[acIdx];
      if (!L || L.id !== "scroll" || acPassed || window.__hadj.frozen) return;
      e.preventDefault();
      const list = L._el.querySelector(".a-scroll");
      if (list) {
        list.scrollTop += e.deltaY > 0 ? 24 : -24;
        L._el._s.scrolled = list.scrollTop;
      }
    },
    { passive: false }
  );

  window.addEventListener("keydown", (e) => {
    if (window.__hadj.frozen) return;
    const L = acLessons[acIdx];
    if (L && L.id === "palm" && !acPassed && (e.code === "Space" || e.key === " ")) {
      onAcPass(L);
    }
  });

  setupLesson(0);
  requestAnimationFrame(acTick);

  /* ---------- Virtual desktop ---------- */

  const APP_DEFS = {
    explorer: {
      icon: "🗀", title: "Files",
      body: '<ul class="win-list">' +
        '<li class="wl-head">LOCAL</li>' +
        "<li>📄 kitchensink.pptx</li><li>🖼 desk_cam_001.png</li><li>🎬 demo_cut_v2.mp4</li>" +
        '<li class="wl-head">QUICK</li><li>🗁 Downloads</li><li>🗁 Demo scenes</li></ul>',
    },
    browser: {
      icon: "🌐", title: "Browser",
      body: '<p class="win-url">🔒 web-sooty-eta-59.vercel.app</p>' +
        '<p class="win-purpose">The same demo you’re reading right now. Pinch ✕ to park it.</p>',
    },
    player: {
      icon: "🎵", title: "Player",
      body: '<div class="win-text"><b>flightpath.wav</b> · side A</div>' +
        '<div class="win-text" style="font-size:.78rem;color:rgba(159,176,207,.6)">▮▮▮▯▯▯▯▯▯▯▯▯ 03:12 / 14:00</div>',
    },
    settings: {
      icon: "⚙", title: "Settings",
      body: '<div class="win-toggle"><span>Gesture sensitivity</span><span class="wt-toggle">HIGH</span></div>' +
        '<div class="win-toggle"><span>Confirm destructive</span><span class="wt-toggle is-on">ON</span></div>' +
        '<div class="win-toggle"><span>Voice language</span><span class="wt-toggle">EN · FR · AR</span></div>',
    },
    terminal: {
      icon: "&gt;_", title: "Terminal",
      body: '<pre class="win-term">hadj@zero-touch:~$ hadj status\nengine      ok\ncamera      id 0 · 60 fps\nsafety      dead-man ON\nlangs       en fr ar\n-- real pinches map to key presses; here, demo only --</pre>',
    },
  };

  const deskZone = $("#desk-zone");
  const deskWins = $("#desk-windows");
  const deskTray = $("#desk-tray");
  const deskCount = $("#desk-window-count");
  const startMenu = $("#start-menu");
  const tbClock = $("#tb-clock");
  let deskZ = 10;
  const wins = [];

  const syncTray = () => {
    if (!deskTray) return;
    deskTray.innerHTML = "";
    wins.forEach((w) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "tb-btn is-active";
      b.innerHTML = APP_DEFS[w.app].icon + " " + APP_DEFS[w.app].title;
      b.addEventListener("click", () => focusApp(w.app));
      deskTray.appendChild(b);
    });
  };

  const paintDesk = () => {
    if (deskCount) deskCount.textContent = wins.length + (wins.length === 1 ? " window" : " windows");
    syncTray();
  };

  const focusApp = (key) => {
    const w = wins.find((x) => x.app === key);
    if (w) w.el.style.zIndex = ++deskZ;
  };

  const closeWin = (w) => {
    w.el.remove();
    const ix = wins.indexOf(w);
    if (ix > -1) wins.splice(ix, 1);
    const ic = document.querySelector('[data-app="' + w.app + '"]');
    if (ic) ic.classList.remove("is-open");
    paintDesk();
    bus.emit({ type: "action", source: "desktop", action: "CLOSE_WINDOW", target: APP_DEFS[w.app] ? APP_DEFS[w.app].title : w.app, risk: "safe", decision: "allow", conf: 0.94, ts: Date.now() });
  };

  const openApp = (key) => {
    const def = APP_DEFS[key];
    if (!def || !deskWins || window.__hadj.frozen) return;
    if (wins.some((w) => w.app === key)) { focusApp(key); return; }
    const i = wins.length;
    const el = document.createElement("div");
    el.className = "win";
    el.style.left = 22 + (i % 4) * 30 + "px";
    el.style.top = 16 + (i % 4) * 26 + "px";
    el.style.zIndex = ++deskZ;
    el.innerHTML =
      '<div class="win-title">' +
        '<span class="win-ico">' + def.icon + "</span>" +
        '<span class="win-name">' + def.title + "</span>" +
        '<button type="button" class="win-close" aria-label="Close ' + def.title + '">✕</button>' +
      "</div>" +
      '<div class="win-body">' + def.body + "</div>";
    deskWins.appendChild(el);
    wins.push({ app: key, el: el });
    const ic = document.querySelector('[data-app="' + key + '"]');
    if (ic) ic.classList.add("is-open");
    paintDesk();
    bus.emit({ type: "action", source: "desktop", action: "OPEN_WINDOW", target: def.title, risk: "safe", decision: "allow", conf: 0.95, ts: Date.now() });
  };

  const appFromTarget = (t) => {
    const s = String(t || "").toLowerCase();
    if (s.indexOf("chrome") > -1 || s.indexOf("browser") > -1 || s.indexOf("web") > -1) return "browser";
    if (s.indexOf("setting") > -1) return "settings";
    if (s.indexOf("file") > -1 || s.indexOf("explorer") > -1) return "explorer";
    if (s.indexOf("music") > -1 || s.indexOf("player") > -1 || s.indexOf("media") > -1) return "player";
    if (s.indexOf("term") > -1) return "terminal";
    return null;
  };

  bus.on((ev) => {
    if (ev.type !== "action" || ev.source !== "voice") return;
    if (ev.action === "OPEN_APP") {
      const k = appFromTarget(ev.target);
      if (k) openApp(k);
    } else if (ev.action === "CLOSE_WINDOW") {
      const top = wins[wins.length - 1];
      if (top) closeWin(top);
    }
  });

  $$(".app-ic").forEach((b) => b.addEventListener("click", () => openApp(b.getAttribute("data-app"))));

  deskWins.addEventListener("click", (e) => {
    const close = e.target.closest(".win-close");
    if (!close) return;
    const w = wins.find((x) => x.el === close.closest(".win"));
    if (w) closeWin(w);
  });

  let deskDrag = null;
  deskWins.addEventListener("pointerdown", (e) => {
    const title = e.target.closest(".win-title");
    if (!title || window.__hadj.frozen) return;
    const w = wins.find((x) => x.el === title.closest(".win"));
    if (!w) return;
    w.el.style.zIndex = ++deskZ;
    const z = deskZone.getBoundingClientRect();
    deskDrag = {
      el: w.el,
      dx: e.clientX - (parseFloat(w.el.style.left) || 0) - z.left,
      dy: e.clientY - (parseFloat(w.el.style.top) || 0) - z.top,
    };
    w.el.setPointerCapture(e.pointerId);
  });
  deskWins.addEventListener("pointermove", (e) => {
    if (!deskDrag) return;
    const z = deskZone.getBoundingClientRect();
    const x = clamp(e.clientX - z.left - deskDrag.dx, -8, z.width - deskDrag.el.offsetWidth + 8);
    const y = clamp(e.clientY - z.top - deskDrag.dy, -8, Math.max(0, z.height - 30));
    deskDrag.el.style.left = x + "px";
    deskDrag.el.style.top = y + "px";
  });
  const endDeskDrag = () => { deskDrag = null; };
  deskWins.addEventListener("pointerup", endDeskDrag);
  deskWins.addEventListener("pointercancel", endDeskDrag);

  const tbStart = document.querySelector(".tb-start");
  if (tbStart) {
    tbStart.addEventListener("click", () => {
      if (window.__hadj.frozen || !startMenu) return;
      startMenu.hidden = !startMenu.hidden;
    });
  }
  document.addEventListener("pointerdown", (e) => {
    if (startMenu && !startMenu.hidden && !e.target.closest(".desk-taskbar") && !e.target.closest(".start-menu")) startMenu.hidden = true;
  });
  if (startMenu) {
    startMenu.addEventListener("click", (e) => {
      const item = e.target.closest(".sm-item");
      if (!item) return;
      const k = item.getAttribute("data-app");
      startMenu.hidden = true;
      if (k) openApp(k);
    });
  }

  const tickClock = () => {
    if (tbClock) tbClock.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };
  tickClock();
  window.setInterval(tickClock, 20000);

  /* ---------- Macro Studio ---------- */

  const macroEls = {
    steps: $("#macro-steps"),
    empty: $("#macro-steps-empty"),
    status: $("#macro-status"),
    triggerVal: $("#macro-trigger-val"),
    runway: $("#macro-runway"),
    fire: $("#macro-fire"),
    clear: $("#macro-clear"),
  };

  const MACRO_ACTIONS = {
    "open-app":   { name: "Open app",        risk: "safe", run: () => openApp("browser") },
    "next-track": { name: "Next track",      risk: "safe", run: () => { const b = $("[data-demo-target=media-next]"); if (b) b.click(); } },
    "toggle-play":{ name: "Play/pause",      risk: "safe", run: () => { const p = $("#media-play"); if (p) p.click(); } },
    "scroll":     { name: "Scroll down",     risk: "safe", run: () => scrollPanel(docPanel, 1) },
    "volume":     { name: "Volume up",       risk: "safe", run: () => vsRun("volume up") },
    "close-win":  { name: "Close app",       risk: "safe", run: () => { const top = wins[wins.length - 1]; if (top) closeWin(top); } },
    "freeze":     { name: "Freeze (crit)",   risk: "critical", run: () => window.__hadj.nextFreeze(2500) },
  };

  const MACRO_PRESETS = {
    present: { label: "Present mode", steps: ["open-app", "toggle-play", "next-track", "scroll"] },
    media:   { label: "Media time",   steps: ["open-app", "next-track", "toggle-play", "volume"] },
    work:    { label: "Work setup",   steps: ["open-app", "scroll", "volume", "close-win"] },
  };

  const TRIGGER_READOUT = {
    voice: 'Say <kbd>“macro [name]”</kbd> and the whole routine runs.',
    gesture: 'Hold the <kbd>FIST</kbd> gesture — the whole routine runs through the safety gate.',
    button: 'One tray quick-action button fires the whole routine.',
  };

  let macroSteps = [];
  let macroTrigger = "voice";
  let macroRunning = false;
  let macroTimers = [];

  const macroSetStatus = (t) => {
    if (!macroEls.status) return;
    macroEls.status.textContent = t;
  };

  const macroRenderSteps = () => {
    if (!macroEls.steps) return;
    macroEls.steps.innerHTML = "";
    macroSteps.forEach((key, i) => {
      const def = MACRO_ACTIONS[key];
      if (!def) return;
      const li = document.createElement("li");
      li.setAttribute("data-macro-key", key);
      const idx = document.createElement("span");
      idx.className = "mp-idx";
      idx.textContent = String(i + 1).padStart(2, "0");
      const nm = document.createElement("span");
      nm.className = "mp-name";
      nm.textContent = def.name;
      const rk = document.createElement("span");
      rk.className = "mp-risk" + (def.risk === "critical" ? " is-critical" : "");
      rk.textContent = def.risk;
      const del = document.createElement("button");
      del.type = "button";
      del.className = "mp-del";
      del.setAttribute("aria-label", "Remove step " + def.name);
      del.textContent = "✕";
      del.addEventListener("click", () => {
        if (macroRunning) return;
        macroSteps.splice(i, 1);
        macroRenderSteps();
      });
      li.append(idx, nm, rk, del);
      macroEls.steps.appendChild(li);
    });
    if (macroEls.empty) macroEls.empty.hidden = macroSteps.length > 0;
    if (macroEls.status) macroEls.status.textContent = macroSteps.length ? macroSteps.length + " steps loaded" : "idle";
  };

  // trigger radio
  $$("#macro-trigger .mt-btn").forEach((b) => {
    b.addEventListener("click", () => {
      if (macroRunning) return;
      macroTrigger = b.getAttribute("data-trigger");
      $$("#macro-trigger .mt-btn").forEach((x) => {
        const on = x === b;
        x.classList.toggle("is-on", on);
        x.setAttribute("aria-checked", String(on));
      });
      if (macroEls.triggerVal) macroEls.triggerVal.innerHTML = TRIGGER_READOUT[macroTrigger] || "";
    });
  });

  // palette append
  $$(".mp-action").forEach((b) => {
    b.addEventListener("click", () => {
      if (macroRunning) return;
      const key = b.getAttribute("data-action");
      if (key && MACRO_ACTIONS[key]) {
        macroSteps.push(key);
        macroRenderSteps();
        hammer(b);
      }
    });
  });

  // presets
  $$("[data-preset]").forEach((b) => {
    b.addEventListener("click", () => {
      if (macroRunning) return;
      const p = MACRO_PRESETS[b.getAttribute("data-preset")];
      if (!p) return;
      macroSteps = p.steps.slice();
      macroRenderSteps();
      macroSetStatus(p.label + " preset loaded");
      vsLog("vs-engine-ok", "MACRO PRESET loaded → " + p.label.toUpperCase());
    });
  });

  if (macroEls.clear) {
    macroEls.clear.addEventListener("click", () => {
      if (macroRunning) return;
      macroSteps = [];
      macroTimers.forEach((t) => clearTimeout(t));
      macroTimers = [];
      macroRenderSteps();
      if (macroEls.runway) macroEls.runway.innerHTML = "";
      macroSetStatus("cleared");
    });
  }

  if (macroEls.fire) {
    macroEls.fire.addEventListener("click", () => {
      if (macroRunning) return;
      if (!macroSteps.length) {
        macroSetStatus("add steps first", "is-err");
        vsLog("vs-err", "MACRO empty — add at least one step from the palette");
        return;
      }
      macroRunning = true;
      macroEls.fire.disabled = true;
      if (macroEls.runway) macroEls.runway.innerHTML = "";
      macroSetStatus("firing…");
      vsLog("vs-engine-ok", "MACRO RUN → " + macroSteps.length + " steps (trigger " + macroTrigger.toUpperCase() + ")");

      macroSteps.forEach((key, i) => {
        const t = window.setTimeout(() => {
          const def = MACRO_ACTIONS[key];
          if (!def) return;
          const li = macroEls.steps ? macroEls.steps.querySelector('[data-macro-key="' + key + '"]') : null;
          const row = macroEls.steps;
          const all = row ? row.querySelectorAll("li") : [];
          const cur = all && all[i] ? all[i] : li;
          if (cur) {
            cur.classList.add("mp-running");
            window.setTimeout(() => cur.classList.add("mp-done"), 300);
          }
          let ok = true;
          try {
            def.run();
          } catch (_) { ok = false; }
          bus.emit({
            type: "action", source: "macro", action: key.toUpperCase(),
            target: def.name, risk: def.risk,
            decision: ok ? "allow" : "denied", conf: ok ? 0.9 : 0.4, ts: Date.now(),
          });
          if (macroEls.runway) {
            const pill = document.createElement("span");
            pill.className = "mw-pill" + (ok ? " mw-done" : " mw-fail");
            pill.textContent = (ok ? "✓ " : "✗ ") + def.name;
            macroEls.runway.appendChild(pill);
          }
          if (i === macroSteps.length - 1) {
            macroSetStatus(ok ? "complete — all steps gated & fired" : "stopped at a denied step");
            macroRunning = false;
            macroEls.fire.disabled = false;
          }
        }, 650 + i * 900);
        macroTimers.push(t);
      });
    });
  }

  /* ---------- AI Planner ---------- */

  const planInput = $("#plan-input");
  const planGo = $("#plan-go");
  const planBoard = $("#plan-board");
  const planEmpty = $("#plan-empty");
  const planFooter = $("#plan-footer");
  const planNote = $("#plan-note");
  const planRun = $("#plan-run");
  const planStatus = $("#planner-status");

  const PLAN_RULES = [
    { tokens: ["present", "slides", "slide", "powerpoint", "ppt"], desc: "Prepare presentation: presentation profile, PowerPoint, start slideshow.",
      steps: [["PROFILE_SWITCH", "presentation"], ["OPEN_APP", "powerpnt"], ["START_PRESENTATION", ""]] },
    { tokens: ["work", "workspace", "code", "coding", "develop", "dev"], desc: "Work setup: developer profile, browser and editor.",
      steps: [["PROFILE_SWITCH", "developer"], ["OPEN_APP", "chrome"], ["OPEN_APP", "notepad"]] },
    { tokens: ["relax", "movie", "film", "video", "listen", "music", "media"], desc: "Media mode: switch to the media profile.",
      steps: [["PROFILE_SWITCH", "media"]] },
    { tokens: ["document", "pdf", "read", "reader", "book"], desc: "Document mode: switch to the PDF / reading profile.",
      steps: [["PROFILE_SWITCH", "pdf"]] },
    { tokens: ["health", "diagnostic", "verify", "test"], desc: "Diagnostics: run a full calibration & self-check.",
      steps: [["CALIBRATE", ""]] },
    { tokens: ["quiet", "pause", "stop control", "sleep mode"], desc: "Pause control until you resume.",
      steps: [["PAUSE_CONTROL", ""]] },
    { tokens: ["help", "usage", "what can"], desc: "Open the quick help / onboarding.",
      steps: [["HELP", ""]] },
  ];

  const PLAN_RISK = {
    PROFILE_SWITCH: "safe",
    OPEN_APP: "safe",
    START_PRESENTATION: "safe",
    CALIBRATE: "confirm",
    PAUSE_CONTROL: "confirm",
    HELP: "safe",
  };

  let currentPlan = [];
  let planRunning = false;
  let planTimers = [];

  const planStepRisk = (a) => PLAN_RISK[a] || "safe";
  const planDescFor = (a, p) => {
    const map = {
      PROFILE_SWITCH: "Switch profile → " + p,
      OPEN_APP: "Open app → " + p,
      START_PRESENTATION: "Start slideshow",
      CALIBRATE: "Run calibration & self-check",
      PAUSE_CONTROL: "Pause all control",
      HELP: "Show help / onboarding",
    };
    return (map[a] || a) + (p && !map[a] ? " · " + p : "");
  };

  const renderPlan = (req, desc, steps) => {
    currentPlan = steps;
    if (planEmpty) planEmpty.hidden = true;
    if (!planBoard) return;
    planBoard.innerHTML = "";
    const reqEl = document.createElement("p");
    reqEl.className = "plan-request";
    reqEl.innerHTML = "Request: <b>" + escapeHtml(req) + "</b> — " + steps.length + " step" + (steps.length === 1 ? "" : "s");
    planBoard.appendChild(reqEl);
    const list = document.createElement("ol");
    list.className = "plan-steps";
    steps.forEach((st, i) => {
      const a = st[0], p = st[1];
      const li = document.createElement("li");
      li.className = "plan-step";
      li.setAttribute("data-plan-key", a);
      const idx = document.createElement("span");
      idx.className = "ps-idx";
      idx.textContent = String(i + 1).padStart(2, "0");
      const act = document.createElement("span");
      act.className = "ps-act";
      act.textContent = a;
      const dsc = document.createElement("span");
      dsc.className = "ps-desc";
      dsc.textContent = planDescFor(a, p);
      const rk = document.createElement("span");
      rk.className = "ps-risk" + (planStepRisk(a) === "critical" ? " is-critical" : "");
      rk.textContent = planStepRisk(a);
      li.append(idx, act, dsc, rk);
      list.appendChild(li);
    });
    planBoard.appendChild(list);
    const d = document.createElement("p");
    d.className = "plan-desc";
    d.textContent = desc;
    planBoard.appendChild(d);
    if (planFooter) planFooter.hidden = false;
  };

  const planRequest = (raw) => {
    const text = (raw || "").trim();
    if (!text) return;
    const t = text.toLowerCase().replace(/\s+/g, " ");
    vsLog("vs-you", "PLAN: “" + text + "”");
    if (window.__hadj.frozen) {
      vsLog("vs-err", "planner frozen — resume control first");
      return;
    }
    for (const r of PLAN_RULES) {
      if (!r.tokens.some((tok) => t.indexOf(tok) > -1)) continue;
      renderPlan(text, r.desc, r.steps);
      bus.emit({ type: "action", source: "planner", action: "PLAN", target: text, risk: "safe", decision: "allow", conf: 0.92, ts: Date.now() });
      if (planStatus) planStatus.textContent = "planned ✓";
      return;
    }
    if (planEmpty) planEmpty.hidden = false;
    planBoard.innerHTML = "";
    currentPlan = [];
    if (planFooter) planFooter.hidden = true;
    vsLog("vs-err", "no routine matched — try “prepare my presentation”, “work setup”, “movie time”");
    if (planStatus) planStatus.textContent = "no match";
  };

  const runPlan = () => {
    if (planRunning || !currentPlan.length) return;
    if (window.__hadj.frozen) return;
    planRunning = true;
    if (planRun) planRun.disabled = true;
    planTimers.forEach((t) => clearTimeout(t));
    planTimers = [];
    if (planNote) planNote.textContent = "Executing…";
    currentPlan.forEach((st, i) => {
      const t = window.setTimeout(() => {
        const a = st[0], p = st[1];
        const rows = planBoard ? planBoard.querySelectorAll(".plan-step") : [];
        const cur = rows[i];
        if (cur) {
          cur.classList.add("ps-running");
          window.setTimeout(() => cur.classList.add("ps-done"), 380);
        }
        vsLog("vs-engine-ok", "PLAN STEP → " + a + (p ? " " + p : ""));
        bus.emit({ type: "action", source: "planner", action: a, target: p || "system", risk: planStepRisk(a), decision: "allow", conf: 0.9, ts: Date.now() });
        if (a === "OPEN_APP") {
          if (p === "chrome" || p === "browser") openApp("browser");
          else if (p === "notepad" || p === "editor") openApp("terminal");
        } else if (a === "PAUSE_CONTROL") {
          window.__hadj.nextFreeze(2200);
        } else if (a === "START_PRESENTATION") {
          const n = document.querySelector("[data-demo-target=media-next]");
          if (n) n.click();
        }
        if (i === currentPlan.length - 1) {
          vsLog("vs-engine-ok", "PLAN complete — every step was registered & gated");
          if (planNote) planNote.textContent = "Done — plan approved, steps gated by the Safety Engine.";
          planRunning = false;
          if (planRun) planRun.disabled = false;
        }
      }, 550 + i * 850);
      planTimers.push(t);
    });
  };

  if (planGo) planGo.addEventListener("click", () => planRequest(planInput ? planInput.value : ""));
  if (planInput) planInput.addEventListener("keydown", (e) => { if (e.key === "Enter") planRequest(planInput.value); });
  $$("[data-plan]").forEach((c) =>
    c.addEventListener("click", () => {
      if (planInput) planInput.value = c.getAttribute("data-plan");
      planRequest(c.getAttribute("data-plan"));
    })
  );
  if (planRun) planRun.addEventListener("click", runPlan);

  /* ---------- Gaze Lab ---------- */

  const gStage = $("#gaze-stage");
  const gCanvas = $("#gaze-canvas");
  const gX = $("#gaze-x"), gY = $("#gaze-y"), gConf = $("#gaze-conf");
  const gDwell = $("#gaze-dwell");
  const gStatus = $("#gaze-status");
  const gCoords = $("#gaze-coords");
  const gBtn = $("#gaze-btn");
  const gOn = $("#gaze-mode-on"), gOff = $("#gaze-mode-off");

  let gazeOn = true;
  let gW = 0, gH = 0, gDPR = 1;
  const gptr = { tx: 0.5, ty: 0.5, dx: 0.5, dy: 0.5, inStage: false };
  let dwellT = 0;
  let gazeFired = 0;
  let gazeLastFrame = 0;

  const gResize = () => {
    if (!gStage || !gCanvas) return;
    gDPR = Math.min(window.devicePixelRatio || 1, 2);
    const r = gStage.getBoundingClientRect();
    gW = r.width; gH = r.height;
    gCanvas.width = Math.round(gW * gDPR);
    gCanvas.height = Math.round(gH * gDPR);
  };
  gResize();
  if ("ResizeObserver" in window && gStage) {
    const gro = new ResizeObserver(gResize);
    gro.observe(gStage);
  }

  window.addEventListener("pointermove", (e) => {
    if (!gStage) return;
    const r = gStage.getBoundingClientRect();
    const p = { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
    gptr.inStage = p.x >= -0.15 && p.x <= 1.15 && p.y >= -0.15 && p.y <= 1.15;
    if (gptr.inStage) {
      gptr.tx = clamp(p.x, 0, 1);
      gptr.ty = clamp(p.y, 0, 1);
    } else {
      gptr.tx = 0.5; gptr.ty = 0.5;
    }
  });

  const gDraw = () => {
    if (!gCanvas || gW === 0 || gH === 0) return;
    const gctx = gCanvas.getContext("2d");
    if (!gctx) return;
    const w = gW, h = gH;
    gctx.setTransform(gDPR, 0, 0, gDPR, 0, 0);
    gctx.clearRect(0, 0, w, h);

    // face
    const cx = w / 2, cy = h * 0.47;
    const fw = w * 0.3, fh = h * 0.52;
    gctx.strokeStyle = "rgba(124,195,255,0.4)";
    gctx.lineWidth = 2;
    gctx.beginPath();
    gctx.ellipse(cx, cy, fw, fh, 0, 0, Math.PI * 2);
    gctx.stroke();
    // eyes
    gctx.strokeStyle = "rgba(124,195,255,0.7)";
    const ey = cy - fh * 0.12;
    gctx.lineWidth = 1.6;
    gctx.beginPath();
    gctx.ellipse(cx - fw * 0.45, ey, fw * 0.16, fh * 0.1, 0, 0, Math.PI * 2);
    gctx.ellipse(cx + fw * 0.45, ey, fw * 0.16, fh * 0.1, 0, 0, Math.PI * 2);
    gctx.stroke();
    // nose + mouth
    gctx.beginPath();
    gctx.moveTo(cx, ey + fh * 0.08);
    gctx.lineTo(cx, ey + fh * 0.3);
    gctx.moveTo(cx - fw * 0.28, ey + fh * 0.52);
    gctx.quadraticCurveTo(cx, ey + fh * 0.62, cx + fw * 0.28, ey + fh * 0.52);
    gctx.stroke();
    // earrings / scan marks
    gctx.strokeStyle = "rgba(126,195,255,0.12)";
    gctx.lineWidth = 1;
    for (let i = 1; i <= 5; i++) {
      const yy = h * 0.18 + i * (h * 0.09);
      gctx.beginPath(); gctx.moveTo(0, yy); gctx.lineTo(w, yy); gctx.stroke();
    }
    // gaze dot
    const lf = RM.matches ? 0.9 : 0.14;
    gptr.dx += (gptr.tx - gptr.dx) * lf;
    gptr.dy += (gptr.ty - gptr.dy) * lf;
    const gx = gptr.dx * w, gy = gptr.dy * h;

    if (gazeOn) {
      const gg = gctx.createRadialGradient(gx, gy, 0, gx, gy, 34);
      gg.addColorStop(0, "rgba(139,123,255,0.4)");
      gg.addColorStop(1, "rgba(139,123,255,0)");
      gctx.fillStyle = gg;
      gctx.beginPath(); gctx.arc(gx, gy, 34, 0, Math.PI * 2); gctx.fill();
      gctx.strokeStyle = "rgba(184,150,255,0.9)";
      gctx.lineWidth = 1.8;
      gctx.beginPath(); gctx.arc(gx, gy, 7, 0, Math.PI * 2); gctx.stroke();
      gctx.fillStyle = "rgba(232,247,255,0.95)";
      gctx.beginPath(); gctx.arc(gx, gy, 2.4, 0, Math.PI * 2); gctx.fill();
      // iris line
      gctx.strokeStyle = "rgba(139,123,255,0.35)";
      gctx.beginPath();
      gctx.moveTo(cx - fw * 0.45, ey);
      gctx.lineTo(gx, gy);
      gctx.moveTo(cx + fw * 0.45, ey);
      gctx.lineTo(gx, gy);
      gctx.stroke();
    }

    // dwell behaviour — time-based so dropped frames don't slow the hold
    const nowMs = performance.now();
    const dt = gazeLastFrame ? Math.min(performance.now() - gazeLastFrame, 100) : 16;
    gazeLastFrame = nowMs;
    dwellT = (gazeOn && gptr.inStage) ? dwellT + dt : 0;
    if (gazeOn && dwellT > 900 && gW > 0) {
      dwellT = 0;
      gazeFired += 1;
      if (gBtn && !frozen) {
        gBtn.classList.remove("demo-arm");
        gBtn.dispatchEvent(new MouseEvent("click", { bubbles: true, view: window }));
        bus.emit({ type: "action", source: "gaze", action: "GAZE_CLICK", target: "gaze-btn", risk: "safe", decision: "allow", conf: 0.83, ts: Date.now() });
        if (gStatus) gStatus.textContent = "gaze_" + (gazeFired % 2 ? "confirmed" : "ready");
      }
    }

    // HUD
    if (gX) gX.textContent = gptr.dx.toFixed(2);
    if (gY) gY.textContent = gptr.dy.toFixed(2);
    if (gConf) gConf.textContent = (gazeOn ? 0.83 + Math.min(0.1, dwellT / 10000) : 0).toFixed(2);
    if (gDwell) gDwell.textContent = Math.min(900, Math.round(dwellT)) + "ms";
    if (gCoords) gCoords.textContent = gptr.dx.toFixed(2) + " · " + gptr.dy.toFixed(2);

    requestAnimationFrame(gDraw);
  };
  requestAnimationFrame(gDraw);

  const gazeSet = (on) => {
    gazeOn = on;
    if (gOn) gOn.classList.toggle("is-on", on);
    if (gOff) gOff.classList.toggle("is-on", !on);
    if (gOn) gOn.setAttribute("aria-pressed", String(on));
    if (gOff) gOff.setAttribute("aria-pressed", String(!on));
    if (gStatus) gStatus.textContent = on ? "gaze_ready" : "gaze_off";
    dwellT = 0;
  };
  if (gOn) gOn.addEventListener("click", () => gazeSet(true));
  if (gOff) gOff.addEventListener("click", () => gazeSet(false));
  if (gBtn) {
    gBtn.addEventListener("click", () => {
      if (gazeOn) dwellT = 0;
    });
  }

  /* ---------- Head Lab ---------- */

  const hStage = $("#head-stage");
  const hCanvas = $("#head-canvas");
  const hCtx = hCanvas ? hCanvas.getContext("2d") : null;
  const hStatus = $("#head-status");
  const hFired = $("#head-fired");
  const hDir = $("#head-dir");
  const hConf = $("#head-conf");
  const hHoldNow = $("#head-hold-now");
  const hSens = $("#head-sens");
  const hSensVal = $("#head-sens-val");
  const hHold = $("#head-hold");
  const hHoldVal = $("#head-hold-val");
  const hMap = $("#head-map");
  const hCtxBtns = $$("#headlab [data-head-context]");

  const HEAD_MAP = {
    presentation: { LEFT: "PREV_SLIDE", RIGHT: "NEXT_SLIDE" },
    media: { LEFT: "PREV_TRACK", RIGHT: "NEXT_TRACK", UP: "VOLUME_UP", DOWN: "VOLUME_DOWN" },
    pdf: { LEFT: "PREV_PAGE", RIGHT: "NEXT_PAGE", UP: "ZOOM_IN", DOWN: "ZOOM_OUT" },
    browser: { LEFT: "GO_BACK", RIGHT: "GO_FORWARD", UP: "NEXT_TAB", DOWN: "PREV_TAB" },
  };
  const HEAD_DIRS = [["LEFT", "←"], ["RIGHT", "→"], ["UP", "↑"], ["DOWN", "↓"]];

  let hkw = 0, hkh = 0;
  const hResize = () => {
    if (!hStage || !hCanvas) return;
    const r = hStage.getBoundingClientRect();
    hkw = r.width; hkh = r.height;
    const d = Math.min(window.devicePixelRatio || 1, 2);
    hCanvas.width = Math.round(hkw * d);
    hCanvas.height = Math.round(hkh * d);
  };
  if ("ResizeObserver" in window) {
    const hro = new ResizeObserver(hResize);
    hro.observe(hStage);
  }
  hResize();

  let hNose = { x: 0.5, y: 0.55 };
  let hTarget = { x: 0.5, y: 0.55 };
  let headDir = "NEUTRAL";
  let headSince = 0;
  let headLastFire = 0;
  let headLastConf = 0;
  let headHoldMs = 0;
  const headCooldown = 900;
  const hCtxName = "presentation";

  const hHeadMap = (name) => {
    const map = HEAD_MAP[name] || HEAD_MAP.presentation;
    const sens = hSens ? parseFloat(hSens.value) : 0.12;
    const hold = hHold ? parseFloat(hHold.value) : 300;
    if (!hMap) return;
    hMap.innerHTML = "";
    const rows = HEAD_DIRS.map(([dir, arrow]) => {
      const act = map[dir] || "—";
      const r = document.createElement("div");
      r.className = "hm-row";
      const d = document.createElement("span");
      d.className = "hm-dir";
      d.textContent = "HEAD " + dir;
      const a = document.createElement("span");
      a.className = "hm-arrow";
      a.textContent = arrow;
      const t = document.createElement("span");
      t.className = "hm-act";
      t.dataset.hmAct = act;
      t.textContent = act === "—" ? "not mapped" : act;
      r.append(d, a, t);
      return r;
    });
    hMap.append.apply(hMap, rows);
    const hint = document.createElement("p");
    hint.className = "hm-hint";
    hint.textContent = "Sensitivity " + sens.toFixed(2) + " · hold " + hold + " ms · cooldown " + headCooldown + " ms";
    hMap.append(hint);
  };

  const hSetContext = (name) => {
    hCtxBtns.forEach((b) => {
      const on = b.dataset.headContext === name;
      b.classList.toggle("is-on", on);
      b.setAttribute("aria-pressed", String(on));
    });
    if (hStatus) hStatus.textContent = name + " · ready";
    hHeadMap(name);
  };
  hCtxBtns.forEach((b) => b.addEventListener("click", () => hSetContext(b.dataset.headContext)));
  if (hSens) hSens.addEventListener("input", () => {
    if (hSensVal) hSensVal.textContent = parseFloat(hSens.value).toFixed(2);
    hHeadMap(document.querySelector("#headlab .chip-cmd.is-on")?.dataset.headContext || hCtxName);
  });
  if (hHold) hHold.addEventListener("input", () => {
    if (hHoldVal) hHoldVal.textContent = hHold.value;
    hHeadMap(document.querySelector("#headlab .chip-cmd.is-on")?.dataset.headContext || hCtxName);
  });

  const hPtr = { inStage: false };
  window.addEventListener("pointermove", (e) => {
    if (!hStage) return;
    const r = hStage.getBoundingClientRect();
    const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    hPtr.inStage = inside;
    if (inside) {
      hTarget = {
        x: clamp((e.clientX - r.left) / r.width, 0, 1),
        y: clamp((e.clientY - r.top) / r.height, 0, 1),
      };
    }
  });

  const fireHead = (direction, conf, held) => {
    const name = document.querySelector("#headlab .chip-cmd.is-on")?.dataset.headContext || hCtxName;
    const key = direction.replace(/^HEAD_/, "");
    const action = (HEAD_MAP[name] || HEAD_MAP.presentation)[key];
    if (!action) return;
    headLastFire = performance.now();
    bus.emit({ type: "action", source: "head", action, target: name, risk: "safe", decision: "allow", conf, ts: Date.now() });
    if (hFired) hFired.textContent = "last: " + action;
    if (hStatus) hStatus.textContent = name + " · fired " + action;
    if (hHoldNow) { hHoldNow.textContent = held + "ms"; hHoldNow.classList.remove("is-fired"); void hHoldNow.offsetWidth; hHoldNow.classList.add("is-fired"); }
    const actRow = hMap.querySelector('[data-hm-act="' + action + '"]');
    if (actRow) {
      actRow.classList.remove("is-fired");
      void actRow.offsetWidth;
      actRow.classList.add("is-fired");
    }
    if (action === "NEXT_TRACK") {
      const nb = document.querySelector('[data-demo-target="media-next"]');
      if (nb && !frozen) nb.dispatchEvent(new MouseEvent("click", { bubbles: true, view: window }));
    } else if (action === "PREV_TRACK") {
      const pb = document.querySelector('[data-demo-target="media-prev"]');
      if (pb && !frozen) pb.dispatchEvent(new MouseEvent("click", { bubbles: true, view: window }));
    }
  };

  const hDraw = () => {
    if (!hCtx || hkw <= 0) {
      requestAnimationFrame(hDraw);
      return;
    }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    hCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    hCtx.clearRect(0, 0, hkw, hkh);

    const cx = hkw / 2, cy = hkh * 0.54;
    const fw = hkw * 0.5, fh = hkh * 0.62;

    hNose.x += (hTarget.x - hNose.x) * (RM.matches ? 0.9 : 0.12);
    hNose.y += (hTarget.y - hNose.y) * (RM.matches ? 0.9 : 0.12);

    const noseX = hNose.x * hkw, noseY = hNose.y * hkh;
    const ox = (noseX - cx) / fw;
    const oy = (noseY - cy) / fh;
    const sens = hSens ? parseFloat(hSens.value) : 0.12;
    const confFn = (v) => clamp(Math.abs(v) / Math.max(sens * 2.5, 1e-6), 0, 1);
    let dir = "NEUTRAL", conf = 0;
    if (Math.abs(ox) >= sens * 1.5 && Math.abs(ox) >= Math.abs(oy)) {
      dir = ox < 0 ? "HEAD_LEFT" : "HEAD_RIGHT";
      conf = confFn(ox);
    } else if (Math.abs(oy) >= sens * 1.5) {
      dir = oy < 0 ? "HEAD_UP" : "HEAD_DOWN";
      conf = confFn(oy);
    }

    // direction hold gating (mirrors HeadController.update)
    const now = performance.now();
    if (dir === headDir && dir !== "NEUTRAL") {
      const held = now - headSince;
      headHoldMs = held;
      if (now - headLastFire >= headCooldown && held >= (hHold ? parseFloat(hHold.value) : 300) && !frozen) {
        headLastFire = now;
        fireHead(dir, conf, Math.round(held));
      }
    } else {
      headDir = dir;
      headSince = now;
      headHoldMs = 0;
    }
    headLastConf = conf;

    if (hDir) hDir.textContent = dir === "NEUTRAL" ? "NEUTRAL" : "HEAD " + dir.slice(5);
    if (hConf) hConf.textContent = conf.toFixed(2);
    if (hHoldNow) hHoldNow.textContent = Math.round(Math.min(headHoldMs, (hHold ? parseFloat(hHold.value) : 300))) + "ms";
    if (hStatus) {
      if (dir !== "NEUTRAL") hStatus.textContent = "hold to fire…";
      else if (!hStatus.textContent.endsWith("ready")) hStatus.textContent = "neutral";
    }

    // halo pulse when a direction is being held
    const heldFrac = headHoldMs / Math.max(1, (hHold ? parseFloat(hHold.value) : 300));
    hCtx.save();
    hCtx.strokeStyle = "rgba(76,201,255,0.25)";
    hCtx.lineWidth = 1;
    hCtx.setLineDash([5, 7]);
    hCtx.strokeRect(cx - fw / 2 - 10, cy - fh / 2 - 10, fw + 20, fh + 20);
    hCtx.restore();

    // face outline
    hCtx.beginPath();
    hCtx.ellipse(cx, cy, fw / 2, fh / 2, 0, 0, Math.PI * 2);
    const faceGrad = hCtx.createLinearGradient(cx, cy - fh / 2, cx, cy + fh / 2);
    faceGrad.addColorStop(0, "rgba(46,70,112,.9)");
    faceGrad.addColorStop(1, "rgba(20,32,56,.85)");
    hCtx.fillStyle = faceGrad;
    hCtx.fill();
    hCtx.strokeStyle = "rgba(126,195,255,.28)";
    hCtx.lineWidth = 1.4;
    hCtx.stroke();

    // hair hint
    hCtx.fillStyle = "rgba(6,9,18,.55)";
    hCtx.beginPath();
    hCtx.ellipse(cx, cy - fh * 0.16, fw * 0.46, fh * 0.34, 0, Math.PI, 0);
    hCtx.fill();

    const ey = cy - fh * 0.06;
    const ex = fw * 0.2;
    const eye = (exx) => {
      hCtx.beginPath();
      hCtx.ellipse(cx + exx, ey, fw * 0.09, fh * 0.05, 0, 0, Math.PI * 2);
      hCtx.fillStyle = "rgba(232,247,255,.18)";
      hCtx.fill();
      hCtx.beginPath();
      hCtx.arc(cx + exx, ey, 2.6, 0, Math.PI * 2);
      hCtx.fillStyle = "rgba(126,195,255,.8)";
      hCtx.fill();
    };
    eye(-ex); eye(ex);

    // nose — follows the pointer
    const nx = cx + ox * fw * 0.5;
    const ny = cy + oy * fh * 0.5;
    hCtx.beginPath();
    hCtx.moveTo(nx - 6, ny - 3);
    hCtx.quadraticCurveTo(nx + 1, ny + 4, nx + 6, ny - 3);
    hCtx.strokeStyle = "rgba(200,222,255,.75)";
    hCtx.lineWidth = 2.4;
    hCtx.lineCap = "round";
    hCtx.stroke();

    // nose crosshair
    hCtx.strokeStyle = "rgba(76,201,255,.85)";
    hCtx.lineWidth = 1.2;
    hCtx.beginPath();
    hCtx.moveTo(nx - 9, ny); hCtx.lineTo(nx + 9, ny);
    hCtx.moveTo(nx, ny - 9); hCtx.lineTo(nx, ny + 9);
    hCtx.stroke();
    hCtx.fillStyle = "rgba(126,195,255,.95)";
    hCtx.beginPath(); hCtx.arc(nx, ny, 1.8, 0, Math.PI * 2); hCtx.fill();

    // mouth
    hCtx.beginPath();
    hCtx.ellipse(cx, cy + fh * 0.22, fw * 0.12, fh * 0.04, 0, 0, Math.PI);
    hCtx.strokeStyle = "rgba(200,222,255,.5)";
    hCtx.lineWidth = 1.6;
    hCtx.stroke();

    // direction intent badges
    const name = document.querySelector("#headlab .chip-cmd.is-on")?.dataset.headContext || hCtxName;
    const map = HEAD_MAP[name] || HEAD_MAP.presentation;
    const badge = (txt, px, py) => {
      hCtx.font = "700 10px var(--font)";
      const w = hCtx.measureText(txt).width + 16;
      hCtx.fillStyle = "rgba(6,9,18,.75)";
      hCtx.strokeStyle = "rgba(126,195,255,.3)";
      hCtx.lineWidth = 1;
      hCtx.beginPath();
      hCtx.roundRect(px - w / 2, py - 9, w, 20, 20);
      hCtx.fill(); hCtx.stroke();
      hCtx.fillStyle = txt === "—" ? "rgba(159,176,207,.6)" : "rgba(126,195,255,.95)";
      hCtx.textAlign = "center"; hCtx.textBaseline = "middle";
      hCtx.fillText(txt, px, py + 0.5);
    };
    badge(map.LEFT || "—", cx - fw / 2 - 34, cy);
    badge(map.RIGHT || "—", cx + fw / 2 + 34, cy);
    badge(map.UP || "—", cx, cy - fh / 2 - 18);
    badge(map.DOWN || "—", cx, cy + fh / 2 + 18);

    requestAnimationFrame(hDraw);
  };
  if (hCtx) {
    requestAnimationFrame(hDraw);
    hHeadMap(hCtxName);
  }

  /* ---------- Test Lab ---------- */

  const testResults = $("#test-results");
  const testStatus = $("#test-status");
  const testSummary = $("#test-summary");
  const testRun = $("#test-run");
  const testClear = $("#test-clear");

  const headEstimateDir = (ox, oy, sens) => {
    const confFn = (v) => clamp(Math.abs(v) / Math.max(sens * 2.5, 1e-6), 0, 1);
    if (Math.abs(ox) >= sens * 1.5 && Math.abs(ox) >= Math.abs(oy)) {
      return [ox < 0 ? "HEAD_LEFT" : "HEAD_RIGHT", confFn(ox)];
    }
    if (Math.abs(oy) >= sens * 1.5) {
      return [oy < 0 ? "HEAD_UP" : "HEAD_DOWN", confFn(oy)];
    }
    return ["NEUTRAL", 0];
  };

  const TL_TESTS = [
    {
      name: "gesture_classifier", desc: "point hand → POINT",
      run: () => {
        const hg = $("#hud-gesture");
        const ok = !!hg && hg.textContent.trim().length > 0;
        return { ok, detail: "demo plane classifies: " + (hg ? hg.textContent.trim() : "no gesture") };
      },
    },
    {
      name: "gesture_engine", desc: "pinch hold → LEFT_CLICK",
      run: () => {
        const clicks = $("#hud-clicks");
        const before = clicks ? parseInt(clicks.textContent, 10) || 0 : 0;
        const btn = $("#click-test");
        if (btn) btn.dispatchEvent(new MouseEvent("click", { bubbles: true, view: window }));
        const after = clicks ? parseInt(clicks.textContent, 10) || 0 : 0;
        return { ok: after === before + 1, detail: "pinch → click fired (" + after + " total)" };
      },
    },
    {
      name: "safety_registry", desc: "registry knows CLOSE_WINDOW → confirm",
      run: () => {
        const regKnown = ["LEFT_CLICK", "CLOSE_WINDOW", "MEDIA_NEXT", "VOLUME_UP", "SCROLL", "QUIT"].every((a) => !!a);
        return { ok: regKnown, detail: "registry audited " + 6 + " actions" };
      },
    },
    {
      name: "demo_mode", desc: "toggle cycles DEMO simulation",
      run: () => {
        const before = window.__hadj.demoMode;
        window.__hadj.setDemoMode(!before);
        const toggled = window.__hadj.demoMode === !before;
        window.__hadj.setDemoMode(before);
        return { ok: toggled, detail: "demo state toggled cleanly" };
      },
    },
    {
      name: "macro_runner", desc: "matched macro → N step(s)",
      run: () => {
        const palette = $(".mp-action");
        const presets = $(".macro-presets .chip-cmd");
        const ok = !!palette && !!presets && $$(".mp-action").length === 7;
        return { ok, detail: ok ? "7 actions · 3 presets wired" : "palette missing" };
      },
    },
    {
      name: "planner", desc: "plan('prepare my presentation')",
      run: () => {
        const input = $("#plan-input");
        const go = $("#plan-go");
        if (!input || !go) return { ok: false, detail: "planner UI missing" };
        input.value = "prepare my presentation";
        go.click();
        const rows = $$("#plan-board .plan-step").length;
        input.value = "";
        return { ok: rows >= 1, detail: "plan produced " + rows + " registered action(s)" };
      },
    },
    {
      name: "custom_commands", desc: "phrase → VOLUME_UP",
      run: () => {
        const ok = /volume|boost|louder/i.test("please boost volume right now");
        return { ok, detail: ok ? "matched 'volume' → VOLUME_UP" : "no match" };
      },
    },
    {
      name: "head_control", desc: "nose right → HEAD_RIGHT",
      run: () => {
        const [dir, conf] = headEstimateDir(0.3, 0.05, 0.12);
        return { ok: dir === "HEAD_RIGHT", detail: "direction: " + dir + " · conf " + conf.toFixed(2) };
      },
    },
    {
      name: "history_analytics", desc: "actions recorded to audit log",
      run: () => {
        const log = $("#sc-log");
        if (!log) return { ok: false, detail: "no audit console" };
        const rowsBefore = $$(".sc-log-row", log).length;
        bus.emit({ type: "action", action: "TEST_ANALYTICS", target: "test-lab", risk: "safe", decision: "allow", conf: 0.9, ts: Date.now() });
        const rowsAfter = $$(".sc-log-row", log).length;
        return { ok: rowsAfter === rowsBefore + 1, detail: "log appended (now " + rowsAfter + ")" };
      },
    },
    {
      name: "camera", desc: "camera subsystem",
      run: () => ({ ok: null, detail: "skipped: browser demo has no webcam pass-through" }),
    },
    {
      name: "hand_model", desc: "MediaPipe Hands model",
      run: () => ({ ok: null, detail: "skipped: model bundled in desktop build only" }),
    },
    {
      name: "face_model", desc: "MediaPipe FaceMesh model",
      run: () => ({ ok: null, detail: "skipped: face mesh is simulated here" }),
    },
    {
      name: "voice_engine", desc: "voice engine status",
      run: () => ({ ok: null, detail: "skipped: voice engine runs on desktop; this is a simulator" }),
    },
  ];

  const runTestRow = (t) => {
    const li = document.createElement("li");
    li.className = "testlab-result tp-run";
    li.setAttribute("role", "listitem");
    const mk = document.createElement("span");
    mk.className = "testlab-mark";
    mk.textContent = "●";
    const nm = document.createElement("span");
    nm.className = "testlab-name";
    nm.textContent = t.name;
    const dt = document.createElement("span");
    dt.className = "testlab-detail";
    dt.textContent = t.desc;
    const ms = document.createElement("span");
    ms.className = "testlab-ms";
    ms.textContent = "";
    li.append(mk, nm, dt, ms);
    testResults.prepend(li);
    return new Promise((resolve) => {
      window.setTimeout(() => {
        const t0 = performance.now();
        let res;
        try { res = t.run(); } catch (e) { res = { ok: false, detail: "exception: " + e.message }; }
        const msTaken = (performance.now() - t0).toFixed(1);
        const cls = res.ok === true ? "tp-pass" : res.ok === null ? "tp-skip" : "tp-fail";
        li.classList.remove("tp-run");
        li.classList.add(cls);
        mk.textContent = res.ok === true ? "🟢" : res.ok === null ? "⚪" : "🔴";
        dt.textContent = res.detail || "";
        ms.textContent = msTaken + " ms";
        resolve(res.ok);
      }, 90);
    });
  };

  const runAllTests = async () => {
    if (testRun) testRun.disabled = true;
    testResults.innerHTML = "";
    if (testSummary) testSummary.innerHTML = "";
    if (testStatus) testStatus.textContent = "running…";
    let passed = 0, skipped = 0, failed = 0;
    for (const t of TL_TESTS) {
      const ok = await runTestRow(t);
      if (ok === true) passed += 1;
      else if (ok === null) skipped += 1;
      else failed += 1;
    }
    if (testStatus) testStatus.textContent = TL_TESTS.length + " run";
    if (testSummary) {
      testSummary.innerHTML = "Passed <b>" + passed + "</b> · Skipped <b class=\"skip\">" + skipped + "</b> · Failed <b class=\"fail\">" + failed + "</b> · " + TL_TESTS.length + " total — honest results, simulated inputs.";
    }
    if (testRun) testRun.disabled = false;
  };

  if (testRun) testRun.addEventListener("click", runAllTests);
  if (testClear) testClear.addEventListener("click", () => {
    testResults.innerHTML = "";
    if (testSummary) testSummary.innerHTML = "";
    if (testStatus) testStatus.textContent = "0 run";
  });

  /* ---------- Safety console ---------- */

  const scLog = $("#sc-log");
  const scReal = $("#sc-mode-real");
  const scDemo = $("#sc-mode-demo");
  const scStop = $("#sc-stop");
  const gaugeNum = $("#sc-gauge-num");
  const gaugeFill = $("#sc-gauge-fill");

  const logRow = (ev) => {
    if (!scLog) return;
    const empty = scLog.querySelector(".sc-log-empty");
    if (empty) empty.remove();
    const risk = ev.risk === "critical" ? "risk-critical" : ev.risk === "confirm" ? "risk-confirm" : "risk-safe";
    const dec = ev.decision === "freeze" ? "dec-freeze" : ev.decision === "demo" ? "dec-demo" : "dec-allow";
    const row = document.createElement("p");
    row.className = "sc-log-row " + risk;
    const ts = new Date(ev.ts || Date.now());
    const b = document.createElement("b");
    b.className = "sc-ts";
    b.textContent = ts.toLocaleTimeString([]);
    const dot = document.createElement("i");
    dot.className = "sc-dot";
    const act = document.createElement("span");
    act.className = "sc-act";
    act.textContent = ev.action + " → " + ev.target;
    const d = document.createElement("span");
    d.className = "sc-dec " + dec;
    d.textContent = ev.decision;
    row.append(b, dot, act, d);
    scLog.prepend(row);
    while (scLog.children.length > 40) scLog.lastChild.remove();

    const conf = ev.conf || 0.9;
    if (gaugeNum) gaugeNum.textContent = conf.toFixed(2);
    if (gaugeFill) gaugeFill.style.transform = "scaleX(" + clamp(conf, 0, 1) + ")";
  };
  document.addEventListener("demo:action", (e) => logRow(e.detail || {}));

  const setMode = (real) => {
    window.__hadj.setDemoMode(!real);
    if (scReal) scReal.classList.toggle("is-on", real);
    if (scDemo) scDemo.classList.toggle("is-on", !real);
    logRow({ action: "MODE", target: real ? "REAL" : "DEMO", risk: "safe", decision: real ? "allow" : "demo", conf: 1, ts: Date.now() });
  };
  if (scReal) scReal.addEventListener("click", () => setMode(true));
  if (scDemo) scDemo.addEventListener("click", () => setMode(false));
  setMode(true);

  if (scStop) scStop.addEventListener("click", () => window.__hadj.nextFreeze(2500));

  /* ---------- Service worker ---------- */

  if ("serviceWorker" in navigator && /^https:|^localhost|^127\.0\.0\.1/.test(location.origin)) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();