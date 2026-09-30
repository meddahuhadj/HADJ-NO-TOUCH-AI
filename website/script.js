/* ==========================================================================
   HADJ NO-TOUCH AI — landing page behaviour
   Vanilla JS, no dependencies, no build step.
   ========================================================================== */
(function () {
  "use strict";

  var w = window;
  var D = w.document;
  var DICT = w.SITE_I18N || {};
  var COMMANDS = w.SITE_COMMANDS || [];
  var CATEGORIES = w.SITE_CATEGORIES || [];
  var TRAY = w.SITE_TRAY || [];
  var DEMO = w.SITE_DEMO || {};
  var STATS = w.SITE_STATS || [];

  var LANGS = ["fr", "ar", "en"];
  var DEFAULT = "fr";
  var STORE_KEY = "hadj.lang";
  var RTL = "ar";

  var S = {
    lang: DEFAULT,
    dir: "ltr",
    revealIO: null,
    navIO: null,
    lab: null,
    grid: null,
    dict: null,
    calib: null,
    cmd: { cat: "all", q: "", pending: null, timer: null, raf: 0 },
    trayIdx: 0,
    trayTimer: 0,
    reduced: false
  };

  /* ------------------------------------------------------------- helpers */
  function $(sel, root) { return (root || D).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || D).querySelectorAll(sel)); }
  function byId(id) { return D.getElementById(id); }

  function el(tag, cls, txt) {
    var n = D.createElement(tag);
    if (cls) { n.className = cls; }
    if (txt != null) { n.textContent = txt; }
    return n;
  }

  function icon(id, cls) {
    var svg = D.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "ic" + (cls ? " " + cls : ""));
    svg.setAttribute("aria-hidden", "true");
    var use = D.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttributeNS("http://www.w3.org/1999/xlink", "href", "#" + id);
    use.setAttribute("href", "#" + id);
    svg.appendChild(use);
    return svg;
  }

  function clear(node) { while (node && node.firstChild) { node.removeChild(node.firstChild); } }

  function store(key, val) {
    try {
      if (val === undefined) { return w.localStorage.getItem(key); }
      w.localStorage.setItem(key, val);
    } catch (e) { return null; }
    return val;
  }

  /* ---------------------------------------------------------------- i18n */
  function dict(lang) { return DICT[lang] || DICT[DEFAULT] || {}; }

  function has(key) {
    return (key in dict(S.lang)) || (key in (DICT[DEFAULT] || {}));
  }

  function t(key, vars) {
    var d = dict(S.lang);
    var s = (key in d) ? d[key] : ((key in (DICT[DEFAULT] || {})) ? DICT[DEFAULT][key] : key);
    if (vars) {
      s = s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] != null ? vars[k] : m; });
    }
    return s;
  }

  /* Applies data-i18n / data-i18n-attr across the whole document. */
  function applyStatic(root) {
    var scope = root || D;

    $$("[data-i18n]", scope).forEach(function (n) {
      n.textContent = t(n.getAttribute("data-i18n"));
    });

    $$("[data-i18n-attr]", scope).forEach(function (n) {
      var spec = n.getAttribute("data-i18n-attr");
      if (!spec) { return; }
      var d = dict(S.lang);
      spec.split(";").forEach(function (pair) {
        var i = pair.indexOf(":");
        if (i < 0) { return; }
        var attr = pair.slice(0, i).trim();
        var key = pair.slice(i + 1).trim();
        if (!attr) { return; }
        /* only translate real keys — plain literals (aria-hidden:true, id refs) pass through */
        if (key in d) { n.setAttribute(attr, t(key)); }
        else if (n.getAttribute(attr) == null) { n.setAttribute(attr, key); }
      });
    });
  }

  function detectLang() {
    var saved = store(STORE_KEY);
    if (saved && LANGS.indexOf(saved) >= 0) { return saved; }
    var list = (navigator.languages && navigator.languages.length)
      ? navigator.languages
      : [navigator.language || ""];
    for (var i = 0; i < list.length; i++) {
      var base = String(list[i] || "").slice(0, 2).toLowerCase();
      if (LANGS.indexOf(base) >= 0) { return base; }
    }
    return DEFAULT;
  }

  function announce(msg) {
    var live = byId("live");
    if (!live) { return; }
    live.textContent = "";
    w.setTimeout(function () { live.textContent = msg; }, 60);
  }

  function setLang(lang, opts) {
    if (LANGS.indexOf(lang) < 0) { lang = DEFAULT; }
    var changed = S.lang !== lang;
    S.lang = lang;
    S.dir = (lang === RTL) ? "rtl" : "ltr";

    var html = D.documentElement;
    html.setAttribute("lang", lang);
    html.setAttribute("dir", S.dir);

    D.title = t("meta.title");
    var desc = $('meta[name="description"]');
    if (desc) { desc.setAttribute("content", t("meta.description")); }

    applyStatic();
    renderAll();
    syncLangUI();

    store(STORE_KEY, lang);

    if (changed && !(opts && opts.silent)) {
      announce(t("a11y.langChanged", { lang: (DICT._names || {})[lang] || lang }));
    }
    if (changed && S.navIO) { S.navIO.disconnect(); watchNav(); }
  }

  function syncLangUI() {
    $$("[data-set-lang]").forEach(function (b) {
      var on = b.getAttribute("data-set-lang") === S.lang;
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    moveLangThumb();
  }

  function moveLangThumb() {
    var group = $(".lang");
    var thumb = byId("langThumb");
    if (!group || !thumb) { return; }
    var active = $('.lang-btn[aria-pressed="true"]', group) || $(".lang-btn", group);
    if (!active) { return; }
    var pr = group.getBoundingClientRect();
    var ar = active.getBoundingClientRect();
    if (!ar.width || !pr.width) { return; }
    thumb.style.width = ar.width + "px";
    thumb.style.transform = "none";
    if (S.dir === "rtl") {
      thumb.style.left = "auto";
      thumb.style.right = (pr.right - ar.right) + "px";
    } else {
      thumb.style.right = "auto";
      thumb.style.left = (ar.left - pr.left) + "px";
    }
  }

  /* ================================================================ HEADER */
  function initHeader() {
    var head = $(".site-header");
    if (head) {
      var onScroll = function () {
        head.classList.toggle("is-stuck", w.scrollY > 8);
      };
      onScroll();
      w.addEventListener("scroll", onScroll, { passive: true });
    }

    /* mobile sheet */
    var burger = byId("hamburger");
    var sheet = byId("mobileSheet");
    if (burger && sheet) {
      sheet.removeAttribute("hidden");
      var setSheet = function (open) {
        sheet.classList.toggle("is-open", open);
        burger.classList.toggle("is-open", open);
        burger.setAttribute("aria-expanded", open ? "true" : "false");
        burger.setAttribute("data-i18n-attr", open ? "aria-label:" + (open ? "nav.menuClose" : "nav.menuOpen") : "aria-label:nav.menuOpen");
        burger.setAttribute("aria-label", t(open ? "nav.menuClose" : "nav.menuOpen"));
        D.body.style.overflow = open ? "hidden" : "";
      };
      burger.addEventListener("click", function () {
        setSheet(!sheet.classList.contains("is-open"));
      });
      $$(".sheet-link", sheet).forEach(function (a) {
        a.addEventListener("click", function () { setSheet(false); });
      });
      D.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && sheet.classList.contains("is-open")) { setSheet(false); burger.focus(); }
      });
      w.addEventListener("resize", function () {
        if (w.innerWidth > 860 && sheet.classList.contains("is-open")) { setSheet(false); }
      });
    }

    /* language buttons */
    $$("[data-set-lang]").forEach(function (b) {
      b.addEventListener("click", function () {
        setLang(b.getAttribute("data-set-lang"));
      });
    });
    w.addEventListener("resize", moveLangThumb, { passive: true });
    w.addEventListener("load", moveLangThumb);
  }

  function watchNav() {
    var links = $$(".nav-link");
    var map = {};
    var sections = [];
    links.forEach(function (a) {
      var id = (a.getAttribute("href") || "").slice(1);
      var sec = id ? byId(id) : null;
      if (sec) { map[id] = a; sections.push(sec); }
    });
    if (!sections.length) { return; }

    var ind = byId("navIndicator");
    var place = function (a) {
      if (!ind || !a) { ind.style.opacity = "0"; return; }
      var p = a.parentNode.getBoundingClientRect();
      var r = a.getBoundingClientRect();
      ind.style.opacity = "1";
      ind.style.width = r.width + "px";
      ind.style.transform = "translateX(" + (r.left - p.left) + "px)";
    };

    var visible = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting ? en.intersectionRatio : 0; });
      var bestId = null, best = 0;
      Object.keys(visible).forEach(function (id) {
        if (visible[id] > best) { best = visible[id]; bestId = id; }
      });
      links.forEach(function (a) { a.classList.remove("is-active"); });
      var a = bestId ? map[bestId] : null;
      if (a) { a.classList.add("is-active"); place(a); }
    }, { rootMargin: "-45% 0px -45% 0px", threshold: [0, 0.2, 0.6, 1] });

    sections.forEach(function (s) { io.observe(s); });
    S.navIO = io;
  }

  /* =============================================================== REVEAL */
  function initReveal() {
    var nodes = $$(".reveal");
    if (S.reduced || !("IntersectionObserver" in w)) {
      nodes.forEach(function (n) { n.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("is-in");
          io.unobserve(en.target);
        }
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.08 });
    nodes.forEach(function (n) { io.observe(n); });
    S.revealIO = io;
  }

  function initMagnetic() {
    if (S.reduced || !w.matchMedia) { return; }
    if (w.matchMedia("(hover: none)").matches) { return; }
    $$("[data-magnetic]").forEach(function (n) {
      n.addEventListener("pointermove", function (e) {
        var r = n.getBoundingClientRect();
        var x = (e.clientX - r.left - r.width / 2) / r.width;
        var y = (e.clientY - r.top - r.height / 2) / r.height;
        n.style.transform = "translate(" + (x * 7).toFixed(2) + "px," + (y * 5).toFixed(2) + "px)";
      });
      n.addEventListener("pointerleave", function () { n.style.transform = ""; });
    });
  }

  function initPointerGlow() {
    var glow = byId("pointerGlow");
    if (!glow || S.reduced) { return; }
    if (w.matchMedia && w.matchMedia("(hover: none)").matches) { return; }
    var raf = 0;
    w.addEventListener("pointermove", function (e) {
      glow.classList.add("is-on");
      if (raf) { return; }
      raf = w.requestAnimationFrame(function () {
        glow.style.left = e.clientX + "px";
        glow.style.top = e.clientY + "px";
        raf = 0;
      });
    }, { passive: true });
    D.addEventListener("pointerleave", function () { glow.classList.remove("is-on"); });
  }

  /* ================================================================ HERO */
  function renderStats() {
    var host = byId("statRow");
    if (!host) { return; }
    clear(host);
    STATS.forEach(function (s) {
      var li = el("li");
      li.appendChild(el("span", "st-n", String(s.n)));
      li.appendChild(el("span", "st-k", t(s.k)));
      host.appendChild(li);
    });
  }

  var FEATURE_ICONS = { f1: "i-mic", f2: "i-hand", f3: "i-keyboard", f4: "i-sparkle" };

  function renderFeatures() {
    var host = byId("featureGrid");
    if (!host) { return; }
    clear(host);
    ["f1", "f2", "f3", "f4"].forEach(function (id, i) {
      var card = el("article", "card reveal");
      card.style.setProperty("--i", String(i));
      var ic = el("span", "card-ic");
      ic.appendChild(icon(FEATURE_ICONS[id] || "i-sparkle"));
      card.appendChild(ic);
      card.appendChild(el("h3", "card-t", t(id + ".title")));
      card.appendChild(el("p", "card-b", t(id + ".body")));
      var tagKey = id + ".tag";
      if (has(tagKey)) { card.appendChild(el("p", "card-k", t(tagKey))); }
      host.appendChild(card);
    });
    if (S.revealIO) {
      $$(".reveal", host).forEach(function (n) { S.revealIO.observe(n); });
    } else {
      $$(".reveal", host).forEach(function (n) { n.classList.add("is-in"); });
    }
  }

  function renderTrayLegend() {
    var host = byId("trayLegend");
    if (!host) { return; }
    clear(host);
    var ul = el("ul");
    TRAY.forEach(function (st, i) {
      var li = el("li", i === S.trayIdx ? "is-on" : "");
      var sw = el("i");
      sw.style.background = st.color;
      sw.style.color = st.color;
      li.appendChild(sw);
      li.appendChild(el("span", "", t("tray." + st.id)));
      ul.appendChild(li);
    });
    host.appendChild(ul);
  }

  function trayState(i) { return TRAY[i] || TRAY[0]; }

  function paintTray() {
    var st = trayState(S.trayIdx);
    var dot = byId("trayDot");
    var label = byId("trayState");
    if (dot && st) {
      dot.style.setProperty("--dot", st.color);
      dot.style.background = st.color;
    }
    if (label && st) { label.textContent = t("tray." + st.id); }
    renderTrayLegend();
    var widget = byId("trayWidget");
    if (widget && st) {
      widget.setAttribute("title", t("tray." + st.id));
    }
  }

  function initTray() {
    var widget = byId("trayWidget");
    var wave = byId("trayWave");
    paintTray();
    if (widget) {
      widget.addEventListener("click", function () {
        S.trayIdx = (S.trayIdx + 1) % TRAY.length;
        paintTray();
        restartTrayAuto();
      });
      widget.style.cursor = "pointer";
    }
    if (wave) { runWave(wave, "tray"); }
    restartTrayAuto();
  }

  function restartTrayAuto() {
    if (S.trayTimer) { w.clearInterval(S.trayTimer); S.trayTimer = 0; }
    if (S.reduced) { return; }
    S.trayTimer = w.setInterval(function () {
      S.trayIdx = (S.trayIdx + 1) % TRAY.length;
      paintTray();
    }, 4200);
  }

  /* canvas waveform shared by the tray widget and the dictation demo */
  function runWave(canvas, mode) {
    if (!canvas || !canvas.getContext) { return; }
    var ctx = canvas.getContext("2d");
    var bars = 46;
    var phase = 0;
    var grad = ctx.createLinearGradient(0, 0, canvas.width, 0);
    grad.addColorStop(0, "#2ee6c5");
    grad.addColorStop(0.5, "#4d8cff");
    grad.addColorStop(1, "#a06bff");

    var raf = 0;
    var draw = function () {
      var wdt = canvas.width, hgt = canvas.height;
      ctx.clearRect(0, 0, wdt, hgt);
      var bw = wdt / bars;
      for (var i = 0; i < bars; i++) {
        var seed = Math.sin(i * 0.55 + phase * 1.6) * 0.5 + Math.sin(i * 0.21 - phase) * 0.5;
        var env = Math.sin((i / bars) * Math.PI);
        var amp = (mode === "tray" ? 0.30 : 0.75) * (0.35 + Math.abs(seed) * 0.65) * env;
        var bh = Math.max(2, amp * hgt);
        ctx.fillStyle = grad;
        ctx.globalAlpha = 0.30 + amp * 0.7;
        var x = i * bw + bw * 0.22;
        var bwi = bw * 0.56;
        if (ctx.roundRect) {
          ctx.beginPath();
          ctx.roundRect(x, (hgt - bh) / 2, bwi, bh, bwi / 2);
          ctx.fill();
        } else {
          ctx.fillRect(x, (hgt - bh) / 2, bwi, bh);
        }
      }
      ctx.globalAlpha = 1;
      phase += 0.03;
      if (S.reduced) { return; }
      raf = w.requestAnimationFrame(draw);
    };
    draw.stop = function () { if (raf) { w.cancelAnimationFrame(raf); raf = 0; } };
    if (S.reduced) { phase = 6; draw(); return draw; }
    draw();
    return draw;
  }

  /* ========================================================== GESTURE LAB */
  function toast(msg, danger) {
    var node = byId("labToast");
    if (!node) { return; }
    node.textContent = msg;
    node.classList.toggle("is-danger", !!danger);
    node.classList.add("is-on");
    w.clearTimeout(node.__t);
    node.__t = w.setTimeout(function () { node.classList.remove("is-on"); }, 2400);
  }

  function lastAction(msg) {
    var n = byId("hudLast");
    if (n) { n.textContent = msg; }
  }

  function initLab() {
    var stage = byId("labStage");
    if (!stage) { return; }

    var cursor = byId("labCursor");
    var desktop = byId("labDesktop");
    var deskLabel = byId("deskLabel");
    var hudState = byId("hudState");
    var hudLed = byId("hudLed");
    var hudFps = byId("hudFps");
    var hudConf = byId("hudConf");
    var hudConfVal = byId("hudConfVal");
    var veil = byId("labVeil");
    var resumeBtn = byId("labResume");

    var L = {
      x: 0, y: 0, down: false, raf: 0, frames: 0, lastFps: 0, fpsT: 0,
      win: 1, zoom: 1, held: null, scrollEl: null, panX: 0, panY: 0
    };
    S.lab = L;

    /* ---- pointer tracking ---- */
    var onMove = function (e) {
      var r = stage.getBoundingClientRect();
      L.x = e.clientX - r.left;
      L.y = e.clientY - r.top;
      if (cursor) { cursor.classList.add("is-on"); }
      if (!L.raf) { L.raf = w.requestAnimationFrame(tick); }
    };
    var onLeave = function () {
      if (cursor) { cursor.classList.remove("is-on"); }
      if (hudLed) { hudLed.className = "hud-led"; }
      if (hudState) { hudState.textContent = t("lab.hud.nohand"); }
      if (hudConf) { hudConf.style.width = "0%"; }
      if (hudConfVal) { hudConfVal.textContent = "0%"; }
      if (hudFps) { hudFps.textContent = "0"; }
    };

    var tick = function () {
      L.raf = 0;
      if (cursor) {
        cursor.style.transform = "translate(" + L.x.toFixed(1) + "px," + L.y.toFixed(1) + "px)";
      }
      L.frames++;
      var now = w.performance.now();
      if (now - L.fpsT > 500) {
        var fps = Math.round((L.frames * 1000) / (now - L.fpsT));
        L.frames = 0; L.fpsT = now;
        if (hudFps) { hudFps.textContent = String(fps); }
      }

      var handSeen = L.x > 0 && L.y > 0;
      if (hudLed) { hudLed.className = "hud-led" + (handSeen ? " is-on" : ""); }
      if (hudState) {
        hudState.textContent = handSeen
          ? t("lab.hud.hand") + " · " + fpsLabel()
          : t("lab.hud.nohand");
      }
      var conf = handSeen ? 62 + Math.round(30 * Math.abs(Math.sin(now / 900))) : 0;
      if (hudConf) { hudConf.style.width = conf + "%"; }
      if (hudConfVal) { hudConfVal.textContent = conf + "%"; }

      if (L.down || handSeen) { L.raf = w.requestAnimationFrame(tick); }
    };

    var fpsLabel = function () { return (hudFps ? hudFps.textContent : "0") + " " + t("lab.hud.fps"); };

    stage.addEventListener("pointermove", onMove, { passive: true });
    stage.addEventListener("pointerenter", onMove, { passive: true });
    stage.addEventListener("pointerleave", onLeave, { passive: true });
    stage.addEventListener("pointerdown", function (e) {
      onMove(e);
      stage.focus({ preventScroll: true });
      if (e.button === 2) { return; }
      L.down = true;
      /* find a grabbable window under the pointer */
      var win = targetWindow(e.target);
      if (win) {
        var r = stage.getBoundingClientRect();
        L.grabWin = win;
        L.grabDx = e.clientX - r.left - win.offsetLeft;
        L.grabDy = e.clientY - r.top - win.offsetTop;
        win.classList.add("is-grabbed");
        L.held = "drag";
        if (cursor) { cursor.classList.add("is-hold"); }
        if (hudState) { hudState.textContent = t("gestures.3.action"); }
      }
    });
    stage.addEventListener("pointerup", function () {
      L.down = false;
      if (L.grabWin) {
        L.grabWin.classList.remove("is-grabbed", "is-moving");
        L.grabWin = null;
        toast(t("gestures.3.action"));
        lastAction(t("gestures.3.name"));
        L.held = null;
        if (cursor) { cursor.classList.remove("is-hold", "is-click"); }
      }
    });
    stage.addEventListener("pointercancel", function () { L.down = false; L.grabWin = null; });
    stage.addEventListener("contextmenu", function (e) { e.preventDefault(); toast(t("gestures.4.action")); lastAction(t("gestures.4.name")); });
    stage.addEventListener("wheel", function (e) {
      e.preventDefault();
      var box = e.target.closest ? e.target.closest("[data-scroll]") : null;
      if (box) { box.scrollTop += e.deltaY; toast(t("lab.scrollHint")); }
    }, { passive: false });

    var targetWindow = function (node) {
      while (node && node !== stage) {
        if (node.classList && node.classList.contains("win")) { return node; }
        node = node.parentNode;
      }
      return null;
    };

    /* window dragging via the simulated pinch */
    stage.addEventListener("pointermove", function (e) {
      if (L.held !== "drag" || !L.grabWin) { return; }
      var r = stage.getBoundingClientRect();
      var maxX = r.width - L.grabWin.offsetWidth;
      var maxY = r.height - L.grabWin.offsetHeight;
      var nx = Math.max(0, Math.min(maxX, e.clientX - r.left - L.grabDx));
      var ny = Math.max(0, Math.min(maxY, e.clientY - r.top - L.grabDy));
      L.grabWin.style.insetInlineStart = "";
      L.grabWin.style.insetInlineEnd = "";
      L.grabWin.style.left = nx + "px";
      L.grabWin.style.top = ny + "px";
      L.grabWin.classList.add("is-moving");
    }, { passive: true });

    /* ---- keyboard equivalents ---- */
    stage.addEventListener("keydown", function (e) {
      var k = e.key;
      if (k === " " || k === "Spacebar") {
        e.preventDefault();
        if (cursor) { cursor.classList.add("is-click"); }
        toast(t("gestures.2.action"));
        lastAction(t("gestures.2.name"));
        w.setTimeout(function () { if (cursor) { cursor.classList.remove("is-click"); } }, 220);
        return;
      }
      if (k === "Escape") { e.preventDefault(); emergency(); return; }
      if (k === "p" || k === "P") { e.preventDefault(); showDesktop(); return; }
      if (k === "ArrowRight" || k === "ArrowLeft") {
        e.preventDefault();
        var dir = k === "ArrowRight" ? 1 : -1;
        L.win = ((L.win - 1 + dir + 3) % 3) + 1;
        $$(".win", desktop || stage).forEach(function (win) {
          win.classList.toggle("is-focused", win.getAttribute("data-win") === String(L.win));
        });
        toast(t("gestures.6.action"));
        lastAction(t("gestures.6.name"));
      }
    });

    /* ---- demo control buttons ---- */
    holdButton(byId("btnFist"), function () { emergency(); });
    holdButton(byId("btnRight"), function () { toast(t("gestures.4.action")); lastAction(t("gestures.4.name")); });
    holdButton(byId("btnPalm"), function () { showDesktop(); });
    tapButton(byId("btnZoomIn"), function () { zoomBy(0.14); });
    tapButton(byId("btnZoomOut"), function () { zoomBy(-0.14); });
    tapButton(byId("btnLabReset"), resetLab);
    if (resumeBtn) { resumeBtn.addEventListener("click", resume); }

    function zoomBy(d) {
      L.zoom = Math.max(0.6, Math.min(1.6, L.zoom + d));
      if (desktop) { desktop.style.scale = L.zoom === 1 ? "" : String(L.zoom); }
      toast(L.zoom > 1 ? t("gestures.7.action") : t("gestures.7.action"));
      lastAction(t("gestures.7.name"));
    }

    function showDesktop() {
      if (deskLabel) { deskLabel.classList.add("is-on"); }
      toast(t("gestures.8.action"));
      lastAction(t("gestures.8.name"));
      w.setTimeout(function () { if (deskLabel) { deskLabel.classList.remove("is-on"); } }, 2600);
    }

    function emergency() {
      if (veil) { veil.removeAttribute("hidden"); }
      L.down = false;
      L.held = null;
      L.grabWin = null;
      $$(".win", desktop || stage).forEach(function (win) { win.classList.remove("is-grabbed", "is-moving"); });
      if (cursor) { cursor.classList.remove("is-hold", "is-click"); }
      lastAction(t("gestures.9.name"));
      if (resumeBtn) { resumeBtn.focus(); }
    }

    function resume() {
      if (veil) { veil.setAttribute("hidden", ""); }
      stage.focus({ preventScroll: true });
      lastAction(t("gestures.10.name"));
    }

    function resetLab() {
      L.zoom = 1; L.win = 1; L.panX = 0; L.panY = 0;
      if (desktop) { desktop.style.scale = ""; }
      $$(".win", desktop || stage).forEach(function (win) {
        win.style.left = ""; win.style.top = "";
        win.style.insetInlineStart = ""; win.style.insetInlineEnd = "";
        win.classList.remove("is-focused", "is-grabbed", "is-moving");
        var sc = win.querySelector("[data-scroll]");
        if (sc) { sc.scrollTop = 0; }
      });
      if (deskLabel) { deskLabel.classList.remove("is-on"); }
      if (cursor) { cursor.classList.remove("is-hold", "is-click"); }
      lastAction(t("lab.btn.reset"));
    }

    L.emergency = emergency;
    L.resume = resume;
    L.reset = resetLab;
    L.toast = toast;
    L.showDesktop = showDesktop;
  }

  /* hold-to-activate: mirrors a real held gesture (fist = 0.5 s, palm = 2 s) */
  function holdButton(btn, fn) {
    if (!btn) { return; }
    var fill = btn.querySelector(".lc-fill");
    var hold = btn.getAttribute("data-hold");
    var ms = hold === "false" ? 500 : parseInt(hold, 10) || 500;
    var timer = 0, raf = 0, t0 = 0;

    var run = function () {
      t0 = w.performance.now();
      var step = function () {
        var p = Math.min(1, (w.performance.now() - t0) / ms);
        if (fill) { fill.style.inlineSize = (p * 100) + "%"; }
        if (p >= 1) {
          btn.classList.add("is-on");
          fn();
          w.setTimeout(function () { btn.classList.remove("is-on"); if (fill) { fill.style.inlineSize = "0%"; } }, 420);
          raf = 0;
          return;
        }
        raf = w.requestAnimationFrame(step);
      };
      raf = w.requestAnimationFrame(step);
    };
    var stop = function () {
      if (raf) { w.cancelAnimationFrame(raf); raf = 0; }
      if (fill) { fill.style.inlineSize = "0%"; }
    };
    btn.addEventListener("pointerdown", function (e) { e.preventDefault(); run(); });
    ["pointerup", "pointerleave", "pointercancel", "blur"].forEach(function (ev) {
      btn.addEventListener(ev, stop);
    });
    btn.addEventListener("click", function (e) { e.preventDefault(); });
  }

  function tapButton(btn, fn) {
    if (!btn) { return; }
    btn.addEventListener("click", function () {
      btn.classList.add("is-on");
      fn();
      w.setTimeout(function () { btn.classList.remove("is-on"); }, 320);
    });
  }

  function renderLegendTable() {
    var host = byId("legendBody");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 10; i++) {
      var row = el("div", "lg-row");
      row.setAttribute("role", "row");
      var g = el("span", "lg-g", t("gestures." + i + ".name")); g.setAttribute("role", "cell");
      var a = el("span", "lg-a", t("gestures." + i + ".action")); a.setAttribute("role", "cell");
      var k = el("span", "lg-k", t("gestures." + i + ".key")); k.setAttribute("role", "cell");
      row.appendChild(g); row.appendChild(a); row.appendChild(k);
      host.appendChild(row);
    }
  }

  /* ==================================================== COMMAND CATALOGUE */
  function norm(s) {
    return String(s == null ? "" : s)
      .toLowerCase()
      .replace(/[ً-ٟـ]/g, "")      /* Arabic diacritics + tatweel */
      .replace(/[̀-ͯ]/g, "")        /* combining Latin accents */
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /* renders {app} / {num} style placeholders as inline code */
  function withArgs(phrase) {
    var frag = D.createDocumentFragment();
    var re = /\{(\w+)\}/g, last = 0, m;
    while ((m = re.exec(phrase)) !== null) {
      if (m.index > last) { frag.appendChild(D.createTextNode(phrase.slice(last, m.index))); }
      frag.appendChild(el("code", "", m[1]));
      last = re.lastIndex;
    }
    if (last < phrase.length) { frag.appendChild(D.createTextNode(phrase.slice(last))); }
    return frag;
  }

  function allPhrases(cmd) {
    var out = [];
    ["ar", "en", "fr"].forEach(function (l) {
      (cmd[l] || []).forEach(function (p) { if (out.indexOf(p) < 0) { out.push(p); } });
    });
    return out;
  }

  function plural(key, n) {
    var d = dict(S.lang);
    var form = (n === 1) ? "one" : "other";
    var s = d[key + "." + form];
    if (!s) { s = d[key + ".other"] || d[key + ".one"] || String(n); }
    return s.replace(/\{n\}/g, n);
  }

  function renderCatTabs() {
    var host = byId("catTabs");
    if (!host) { return; }
    clear(host);
    var mk = function (id, label, count) {
      var b = el("button", "cat-tab" + (S.cmd.cat === id ? " is-active" : ""));
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", S.cmd.cat === id ? "true" : "false");
      b.appendChild(el("span", "", label));
      var n = el("span", "cat-n", " " + count);
      b.appendChild(n);
      b.addEventListener("click", function () {
        S.cmd.cat = id;
        renderCatTabs();
        renderCommands();
      });
      return b;
    };
    host.appendChild(mk("all", t("cmd.filterAll"), COMMANDS.length));
    CATEGORIES.forEach(function (cat) {
      var n = COMMANDS.filter(function (c) { return c.c === cat; }).length;
      host.appendChild(mk(cat, t("cmd.cat." + cat), n));
    });
  }

  function matches(cmd, q) {
    if (!q) { return true; }
    return allPhrases(cmd).some(function (p) { return norm(p).indexOf(q) >= 0; });
  }

  function highlight(phrase, q) {
    var frag = D.createDocumentFragment();
    if (!q) { frag.appendChild(withArgs(phrase)); return frag; }
    var re = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
    phrase.split(re).forEach(function (part) {
      if (!part) { return; }
      if (norm(part) === q) { frag.appendChild(el("mark", "", part)); }
      else { frag.appendChild(withArgs(part)); }
    });
    return frag;
  }

  function renderCommands() {
    var host = byId("cmdList");
    if (!host) { return; }
    clear(host);

    var q = S.cmd.q;
    var list = COMMANDS.filter(function (c) {
      return (S.cmd.cat === "all" || c.c === S.cmd.cat) && matches(c, q);
    });

    var groups = S.cmd.cat === "all" ? CATEGORIES : [S.cmd.cat];
    groups.forEach(function (cat) {
      var items = list.filter(function (c) { return c.c === cat; });
      if (!items.length) { return; }
      var g = el("div", "cmd-group");
      var h = el("div", "cmd-group-h");
      h.appendChild(el("b", "", t("cmd.cat." + cat)));
      h.appendChild(el("span", "sep"));
      h.appendChild(el("span", "", String(items.length)));
      g.appendChild(h);
      items.forEach(function (cmd) { g.appendChild(cmdItem(cmd, q)); });
      host.appendChild(g);
    });

    var count = byId("cmdCount");
    if (count) { count.textContent = plural("cmd.count", list.length); }
    var empty = byId("cmdEmpty");
    if (empty) { empty.hidden = list.length > 0; }
    var lead = byId("cmdLead");
    if (lead) { lead.textContent = t("cmd.lead", { n: COMMANDS.length }); }
  }

  function cmdItem(cmd, q) {
    var main = (cmd[S.lang] || cmd.en || [])[0] || "";
    var others = allPhrases(cmd).filter(function (p) { return p !== main; });

    var item = el("article", "cmd-item" + (cmd.d ? " is-danger" : ""));
    var tag = el("div", "cmd-tag");
    tag.appendChild(icon(cmd.d ? "i-warn" : "i-check", cmd.d ? "ic-warn" : "ic-ok"));
    tag.appendChild(el("span", "", t("cmd.cat." + cmd.c)));
    if (cmd.d) { tag.appendChild(el("span", "cmd-danger", t("cmd.dangerShort"))); }
    item.appendChild(tag);

    var args = el("div", "cmd-args");
    args.appendChild(highlight(main, q));
    item.appendChild(args);

    if (others.length) {
      var varis = el("div", "cmd-variants");
      varis.setAttribute("title", t("cmd.tagTitle"));
      others.forEach(function (p) { varis.appendChild(el("span", "", p)); });
      item.appendChild(varis);
    }

    var say = el("button", "btn btn-sm btn-ghost cmd-run");
    say.type = "button";
    say.appendChild(icon("i-mic"));
    say.appendChild(el("span", "", t("cmd.run")));
    say.addEventListener("click", function () {
      if (cmd.d) { openConfirm(cmd, main); }
      else { sayLive(main); }
    });
    item.appendChild(say);
    return item;
  }

  function sayLive(phrase) {
    var live = byId("live");
    if (live) { live.textContent = phrase; }
  }

  /* ---- dangerous-command confirmation ---------------------------------- */
  var CONFIRM_MS = 8000;

  function openConfirm(cmd, phrase) {
    var box = byId("cmdConfirm");
    var bar = byId("cmdConfirmBar");
    if (!box) { return; }
    S.cmd.pending = phrase;
    var title = byId("cmdConfirmTitle");
    var body = byId("cmdConfirmBody");
    if (title) { title.textContent = t("cmd.confirm.title", { cmd: phrase }); }
    if (body) { body.textContent = t("cmd.confirm.body", { s: CONFIRM_MS / 1000 }); }
    box.hidden = false;

    if (S.cmd.raf) { w.cancelAnimationFrame(S.cmd.raf); S.cmd.raf = 0; }
    var t0 = w.performance.now();
    var step = function () {
      var p = Math.min(1, (w.performance.now() - t0) / CONFIRM_MS);
      if (bar) { bar.style.transform = "scaleX(" + (1 - p) + ")"; }
      if (p >= 1) { closeConfirm("timeout"); return; }
      S.cmd.raf = w.requestAnimationFrame(step);
    };
    S.cmd.raf = w.requestAnimationFrame(step);

    var yes = byId("cmdYes"), no = byId("cmdNo");
    if (yes) { yes.onclick = function () { closeConfirm("yes"); }; yes.focus(); }
    if (no) { no.onclick = function () { closeConfirm("no"); }; }
  }

  function closeConfirm(result) {
    var box = byId("cmdConfirm");
    var bar = byId("cmdConfirmBar");
    if (S.cmd.raf) { w.cancelAnimationFrame(S.cmd.raf); S.cmd.raf = 0; }
    if (box) { box.hidden = true; }
    if (bar) { bar.style.transform = "scaleX(1)"; }
    var phrase = S.cmd.pending;
    S.cmd.pending = null;
    var live = byId("live");
    if (!live || !phrase) { return; }
    if (result === "yes") { live.textContent = t("cmd.confirm.heard", { cmd: phrase }); }
    else if (result === "timeout") { live.textContent = t("cmd.confirm.timeout"); }
    else { live.textContent = t("cmd.confirm.cancel"); }
  }

  function initCommands() {
    var input = byId("cmdInput");
    var clearBtn = byId("cmdClear");
    renderCatTabs();
    renderCommands();

    if (input) {
      var onInput = function () {
        S.cmd.q = norm(input.value);
        if (clearBtn) { clearBtn.hidden = !input.value; }
        renderCommands();
      };
      input.addEventListener("input", onInput);
      input.addEventListener("search", onInput);
      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && input.value) {
          e.stopPropagation();
          input.value = ""; onInput();
        }
      });
    }
    if (clearBtn && input) {
      clearBtn.addEventListener("click", function () {
        input.value = ""; onInput(); input.focus();
      });
    }
  }

  /* ========================================================== VOICE GRID */
  var GRID_MAX_DEPTH = 4;

  function initGrid() {
    var screen = byId("gridScreen");
    if (!screen) { return; }
    var G = { path: [], depth: 0, focus: -1 };
    S.grid = G;

    var gridRoot = function () { return G.depth === 0 ? screen : G.path[G.depth - 1].node; };

    function fillCells(host) {
      for (var i = 1; i <= 9; i++) {
        (function (i) {
          var c = el("button", "gs-cell" + (i === 5 ? " is-center" : ""));
          c.type = "button";
          c.dataset.n = String(i);
          c.appendChild(el("span", "", String(i)));
          c.addEventListener("click", function (e) { pick(e.currentTarget); });
          host.appendChild(c);
        })(i);
      }
    }

    function paint() {
      clear(screen);
      screen.className = "gs-screen";
      screen.setAttribute("role", "group");
      screen.setAttribute("aria-label", t("grid.root"));
      screen.setAttribute("tabindex", "-1");
      fillCells(screen);
      syncActions();
      syncCrumbs();
      G.focus = -1;
      announcePicked("");
    }

    function pick(btn) {
      var n = parseInt(btn.dataset.n, 10);
      if (n === 5) { actOnTarget(); return; }
      if (G.depth >= GRID_MAX_DEPTH) { actOnTarget(); return; }
      var sub = el("div", "gs-sub");
      fillCells(sub);
      var parent = gridRoot();
      var layer = { n: n, node: sub };
      G.path.push(layer);
      G.depth++;
      clear(parent);
      parent.appendChild(sub);
      syncActions(); syncCrumbs();
      var picked = byId("gridPicked");
      if (picked) { picked.textContent = t("grid.picked", { path: pathWith(n), name: t("grid.act.click") }); }
    }

    function pathLabel() {
      return G.path.map(function (l) { return l.n; }).join(".");
    }

    function pathWith(n) {
      var p = pathLabel();
      return p ? p + "." + n : String(n);
    }

    function flashOk(msg) {
      var centre = $(".gs-cell.is-center", gridRoot());
      if (centre) {
        centre.classList.remove("is-hit");
        void centre.offsetWidth;
        centre.classList.add("is-hit");
        w.setTimeout(function () { centre.classList.remove("is-hit"); }, 460);
      }
      var live = byId("live");
      if (live && msg) { live.textContent = msg; }
    }

    function actOnTarget() {
      var label = pathLabel();
      var picked = byId("gridPicked");
      if (!label) {
        if (picked) { picked.textContent = t("grid.act.move"); }
        flashOk(t("grid.act.move"));
        return;
      }
      if (picked) { picked.textContent = t("grid.picked", { path: pathWith(5), name: t("grid.act.click") }); }
      flashOk(t("grid.picked", { path: pathWith(5), name: t("grid.act.click") }));
    }

    function up() {
      if (!G.path.length) { return; }
      G.path.pop();
      G.depth--;
      if (G.depth === 0) { paint(); }
      else {
        var parent = gridRoot();
        clear(parent);
      }
      syncActions(); syncCrumbs();
      announcePicked("");
    }

    function reset() { G.path = []; G.depth = 0; G.focus = -1; paint(); }

    function syncActions() {
      var host = byId("gridActions");
      if (!host) { return; }
      clear(host);
      var acts = [
        { k: "click", cls: "is-primary" },
        { k: "double" },
        { k: "right" },
        { k: "move" }
      ];
      if (G.path.length) { acts.push({ k: "back" }); acts.push({ k: "cancel" }); }
      acts.forEach(function (a) {
        var b = el("button", "gs-act" + (a.cls ? " " + a.cls : ""));
        b.type = "button";
        b.textContent = t("grid.act." + a.k);
        b.addEventListener("click", function () {
          if (a.k === "back") { up(); return; }
          if (a.k === "cancel") { reset(); return; }
          flashOk(t("grid.picked", { path: pathWith(5), name: t("grid.act." + a.k) }));
        });
        host.appendChild(b);
      });
    }

    function syncCrumbs() {
      var host = byId("gridCrumbs");
      if (!host) { return; }
      clear(host);
      var root = el("li", "gs-crumb-root", t("grid.root"));
      host.appendChild(root);
      G.path.forEach(function (l) { host.appendChild(el("li", "", String(l.n))); });
    }

    function announcePicked(v) {
      var live = byId("live");
      if (live && v) { live.textContent = v; }
    }

    /* keyboard 1–9 */
    D.addEventListener("keydown", function (e) {
      var tag = (e.target && e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || e.target.isContentEditable) { return; }
      if (e.ctrlKey || e.altKey || e.metaKey) { return; }
      if (!/^[1-9]$/.test(e.key)) { return; }
      var inGrid = false;
      var sec = byId("grid");
      if (sec && sec.getBoundingClientRect().width) {
        var r = sec.getBoundingClientRect();
        inGrid = r.top < w.innerHeight && r.bottom > 0;
      }
      if (!inGrid) { return; }
      var cells = $$(".gs-cell", gridRoot()).filter(function (c) { return !c.classList.contains("gs-cell-sub"); });
      var cell = cells[parseInt(e.key, 10) - 1];
      if (cell) { e.preventDefault(); cell.focus(); pick(cell); }
    });

    var resetBtn = byId("gridReset");
    if (resetBtn) { resetBtn.addEventListener("click", reset); }

    paint();
  }

  function renderVocab() {
    var host = byId("vocabList");
    if (!host) { return; }
    clear(host);
    ["click", "double", "right", "move", "back", "cancel"].forEach(function (k) {
      var li = el("li");
      li.appendChild(icon("i-check", "ic-ok"));
      li.appendChild(el("span", "", t("grid.act." + k)));
      host.appendChild(li);
    });
  }

  /* =========================================================== DICTATION */
  function demoTokens() {
    var seq = DEMO[S.lang] || DEMO.en || DEMO.fr || [];
    return seq;
  }

  function renderDictSteps() {
    var host = byId("dictSteps");
    if (!host) { return; }
    clear(host);
    [1, 2, 3].forEach(function (i) { host.appendChild(el("li", "", t("dict.step" + i))); });
  }

  function renderPunct() {
    var host = byId("punctBody");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 5; i++) {
      var row = el("div", "pt-row");
      row.setAttribute("role", "row");
      row.appendChild(el("span", "", t("dict.punct." + i)));
      row.appendChild(el("b", "", t("dict.punct." + i + "w")));
      host.appendChild(row);
    }
  }

  function renderEngines() {
    var host = byId("engines");
    if (!host) { return; }
    clear(host);
    host.appendChild(el("h3", "mini-h", t("dict.engines.title")));
    ["whisper", "vosk"].forEach(function (id) {
      var card = el("div", "engine");
      var h = el("div", "engine-h");
      h.appendChild(el("span", "engine-n", t("dict." + id + ".name")));
      h.appendChild(el("span", "engine-tag", t("dict." + id + ".tag")));
      card.appendChild(h);
      card.appendChild(el("p", "engine-b", t("dict." + id + ".body")));
      host.appendChild(card);
    });
  }

  function initDictation() {
    var box = byId("dictText");
    var demo = byId("dictDemo");
    var toggle = byId("dictToggle");
    var restart = byId("dictRestart");
    var wave = byId("dictWave");
    if (!box) { return; }

    var K = { i: 0, timer: 0, playing: true, draw: null };
    S.dict = K;

    function paint() {
      clear(box);
      var seq = demoTokens();
      for (var i = 0; i <= K.i && i < seq.length; i++) {
        var tok = seq[i];
        if (tok.k === "t") {
          box.appendChild(D.createTextNode(tok.v));
        } else {
          var say = el("span", "dd-say", t("dict.say." + tok.w));
          say.setAttribute("dir", "auto");
          box.appendChild(say);
          box.appendChild(D.createTextNode(tok.v));
        }
      }
      var caret = el("span", "dd-caret");
      caret.setAttribute("aria-hidden", "true");
      box.appendChild(caret);
      box.scrollTop = box.scrollHeight;
    }

    function step() {
      var seq = demoTokens();
      if (K.i >= seq.length) { K.i = 0; }
      K.i++;
      paint();
      var tok = seq[K.i - 1];
      var delay = tok && tok.k === "t" ? 900 : 420;
      K.timer = w.setTimeout(step, delay);
    }

    function play() {
      K.playing = true;
      if (demo) { demo.classList.remove("is-paused"); }
      setToggleIcon("i-play");
      if (toggle) { toggle.setAttribute("aria-label", t("dict.demo.pause")); }
      paint();
      w.clearTimeout(K.timer);
      K.timer = w.setTimeout(step, 700);
    }

    function pause() {
      K.playing = false;
      w.clearTimeout(K.timer);
      if (demo) { demo.classList.add("is-paused"); }
      setToggleIcon("i-play");
      if (toggle) { toggle.setAttribute("aria-label", t("dict.demo.play")); }
      paint();
    }

    function setToggleIcon(id) {
      if (!toggle) { return; }
      var use = toggle.querySelector("use");
      if (use) { use.setAttribute("href", "#" + id); use.setAttributeNS("http://www.w3.org/1999/xlink", "href", "#" + id); }
    }

    if (toggle) { toggle.addEventListener("click", function () { K.playing ? pause() : play(); }); }
    if (restart) {
      restart.addEventListener("click", function () {
        w.clearTimeout(K.timer);
        K.i = 0;
        paint();
        if (K.playing) { K.timer = w.setTimeout(step, 500); }
      });
    }

    K.draw = runWave(wave, "dict");
    if (K.draw) { K.draw(); }
    K.play = play; K.pause = pause;
    paint();
    w.setTimeout(step, 900);
  }

  /* ========================================================= CALIBRATION */
  function renderCalibSteps() {
    var host = byId("calibSteps");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 4; i++) {
      var li = el("li");
      li.dataset.step = String(i);
      li.appendChild(el("span", "cs-n", String(i) + "/4"));
      li.appendChild(el("span", "cs-t", t("acc.step" + i)));
      host.appendChild(li);
    }
  }

  function initCalibration() {
    var btn = byId("calibStart");
    var status = byId("calibStatus");
    var hand = byId("cvHand");
    var host = byId("calibSteps");
    if (!btn || !host) { return; }

    var C = { i: 0, timer: 0, running: false, finished: false };
    S.calib = C;

    var paintSteps = function () {
      $$("li", host).forEach(function (li, idx) {
        var n = idx + 1;
        li.classList.toggle("is-on", C.running && n === C.i);
        li.classList.toggle("is-done", (C.running && n < C.i) || (C.finished && !C.running));
      });
    };

    var run = function () {
      if (C.running) { return; }
      C.running = true; C.finished = false; C.i = 1;
      btn.disabled = true;
      paintSteps();
      if (status) { status.textContent = t("acc.progress", { n: 1 }); }
      if (hand) { hand.classList.add("is-on"); }
      step();
    };

    var step = function () {
      if (!C.running) { return; }
      if (C.i > 4) { finish(); return; }
      if (status) { status.textContent = t("acc.progress", { n: C.i }); }
      paintSteps();
      C.timer = w.setTimeout(function () { C.i++; step(); }, 1700);
    };

    var finish = function () {
      C.running = false;
      C.finished = true;
      C.i = 5;
      btn.disabled = false;
      paintSteps();
      if (hand) { hand.classList.remove("is-on"); }
      if (status) {
        status.textContent = t("acc.done") + " " + t("acc.doneDetail", { enter: "0.34", exit: "0.28", w: 46, h: 52 });
      }
      announce(t("acc.done"));
    };

    btn.addEventListener("click", run);
    paintSteps();
  }

  /* ============================================ static content assemblies */
  function renderA11y() {
    var host = byId("a11yList");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 6; i++) {
      var li = el("li");
      li.appendChild(icon("i-check", "ic-ok"));
      li.appendChild(el("span", "", t("acc.a11y." + i)));
      host.appendChild(li);
    }
  }

  var PRIV_ICONS = { 1: "i-offline", 2: "i-lock", 3: "i-cpu", 4: "i-check" };

  function renderPriv() {
    var host = byId("privGrid");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 4; i++) {
      var card = el("article", "priv-card reveal");
      card.style.setProperty("--i", String(i - 1));
      var ic = el("span", "priv-card-ic");
      ic.appendChild(icon(PRIV_ICONS[i] || "i-shield"));
      card.appendChild(ic);
      card.appendChild(el("h3", "priv-card-t", t("priv." + i + ".title")));
      card.appendChild(el("p", "priv-card-b", t("priv." + i + ".body")));
      host.appendChild(card);
    }
    observeReveals(host);
  }

  function renderEmergency() {
    var host = byId("emList");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 3; i++) {
      var li = el("li");
      var h = el("p", "em-t");
      h.appendChild(icon(i === 1 ? "i-mic" : i === 2 ? "i-hand" : "i-keyboard"));
      h.appendChild(el("span", "", t("priv.emergency." + i + "t")));
      li.appendChild(h);
      li.appendChild(el("p", "em-b", t("priv.emergency." + i + "b")));
      host.appendChild(li);
    }
  }

  function renderSpec() {
    var host = byId("specList");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 7; i++) {
      var li = el("li");
      li.appendChild(el("span", "spec-k", t("req.s" + i)));
      li.appendChild(el("span", "spec-v", t("req.s" + i + "v")));
      host.appendChild(li);
    }
  }

  function renderLaunch() {
    var host = byId("launchSteps");
    if (!host) { return; }
    clear(host);
    [1, 2, 3].forEach(function (i) { host.appendChild(el("li", "", t("req.launch." + i))); });
  }

  function renderLegendColors() {
    var host = byId("legendColors");
    if (!host) { return; }
    clear(host);
    TRAY.forEach(function (st) {
      var li = el("li");
      var sw = el("span", "lc-swatch");
      sw.style.background = st.color;
      sw.style.color = st.color;
      li.appendChild(sw);
      li.appendChild(el("span", "", t("tray." + st.id)));
      host.appendChild(li);
    });
  }

  function renderFaq() {
    var host = byId("faqList");
    if (!host) { return; }
    clear(host);
    for (var i = 1; i <= 9; i++) {
      (function (i) {
        var item = el("div", "faq-item" + (i === 1 ? " is-open" : ""));

        var q = el("button", "faq-q");
        q.type = "button";
        q.setAttribute("aria-expanded", i === 1 ? "true" : "false");
        q.setAttribute("aria-controls", "faq-a" + i);
        q.appendChild(el("span", "faq-n", String(i).padStart(2, "0")));
        q.appendChild(el("span", "faq-qt", t("faq.q" + i)));
        q.appendChild(icon("i-plus", "faq-ic"));
        q.addEventListener("click", function () {
          var open = item.classList.toggle("is-open");
          q.setAttribute("aria-expanded", open ? "true" : "false");
        });

        var a = el("div", "faq-a");
        a.id = "faq-a" + i;
        a.setAttribute("role", "region");
        var inner = el("div", "faq-a-in");
        inner.appendChild(el("p", "", t("faq.a" + i)));
        a.appendChild(inner);

        item.appendChild(q);
        item.appendChild(a);
        host.appendChild(item);
      })(i);
    }
  }

  function observeReveals(host) {
    $$(".reveal", host).forEach(function (n) {
      if (S.reduced || !("IntersectionObserver" in w)) { n.classList.add("is-in"); return; }
      if (S.revealIO) { S.revealIO.observe(n); } else { n.classList.add("is-in"); }
    });
  }

  function renderAll() {
    renderStats();
    renderFeatures();
    renderLegendTable();
    renderCatTabs();
    renderCommands();
    renderVocab();
    renderDictSteps();
    renderPunct();
    renderEngines();
    renderCalibSteps();
    renderA11y();
    renderPriv();
    renderEmergency();
    renderSpec();
    renderLaunch();
    renderLegendColors();
    renderFaq();
    paintTray();
  }

  function initFloatingQuickBar() {
    $$("[data-sim-cmd]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var cmdText = btn.getAttribute("data-sim-cmd");
        toast(cmdText);
        S.trayIdx = 1;
        paintTray();
        var wave = byId("trayWave");
        if (wave) { runWave(wave, "dict"); }
      });
    });
  }

  /* ================================================================= BOOT */
  function boot() {
    try {
      bootAll();
    } catch (err) {
      var msg = String((err && err.message) || err);
      if (w.console) { w.console.error("[hadj] boot failed:", err); }
      D.documentElement.setAttribute("data-boot-error", msg);
      var live = byId("live");
      if (live) { live.textContent = msg; }
    }
  }

  function bootAll() {
    S.reduced = !!(w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches);

    if (S.reduced) { D.documentElement.classList.add("is-reduced"); }

    S.lang = detectLang();
    var startLang = S.lang;
    S.lang = "__init__";
    setLang(startLang, { silent: true });

    initHeader();
    initReveal();
    initMagnetic();
    initPointerGlow();
    initTray();
    initLab();
    initCommands();
    initGrid();
    initDictation();
    initCalibration();
    initFloatingQuickBar();
    watchNav();

    w.setTimeout(moveLangThumb, 60);
    w.setTimeout(moveLangThumb, 400);
  }

  if (D.readyState === "loading") {
    D.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
