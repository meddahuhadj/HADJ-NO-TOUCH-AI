/* ============================================================
   HADJ NO-TOUCH AI — app.js
   Interactivity + live canvas demo + PWA install + service worker
   ============================================================ */

(() => {
  "use strict";

  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => Array.prototype.slice.call((c || document).querySelectorAll(s));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  const RM = window.matchMedia("(prefers-reduced-motion: reduce)");
  const lerpEase = RM.matches ? 0.9 : 0.14;

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
    trackIdx = (i + TRACKS.length) % TRACKS.length;
    elapsed = 0;
    if (mediaTitle) mediaTitle.textContent = TRACKS[trackIdx].title;
    if (mediaCap) mediaCap.textContent = "Now playing a local file — no stream, all on your machine.";
    paintMedia();
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
    if (!el) return;
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
  };

  const hitTarget = (x, y) => {
    const el = document.elementFromPoint(x, y);
    return el ? el.closest("[data-demo-target]") : null;
  };

  window.addEventListener("pointerdown", (e) => {
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
    const step = palm ? 210 : 56;
    const d = deltaY > 0 ? step : -step;
    el.scrollBy({ top: d });
    if (docPos) {
      const line = Math.floor(el.scrollTop / 24) + 1;
      docPos.textContent = "L:" + String(line).padStart(4, "0");
    }
  };

  $$(".demo-scroll").forEach((el) => {
    el.addEventListener(
      "wheel",
      (e) => {
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

  /* ---------- Service worker ---------- */

  if ("serviceWorker" in navigator && /^https:|^localhost|^127\.0\.0\.1/.test(location.origin)) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();