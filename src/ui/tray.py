"""أيقونة شريط النظام + ربط إشعارات المتحكم (من خيوط أخرى) بالواجهة."""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import paths
from core.controller import Controller
from ui.calibration_wizard import CalibrationWizard
from ui.control_panel import ControlPanel
from ui.grid_overlay import GridOverlay
from ui.i18n import Tr
from ui.icons import state_icon
from ui.overlay import ConfirmWindow, Overlay
from ui.status_orb import StatusOrb


class Bridge(QObject):
    """notify() آمنة من أي خيط؛ الإشارة تُسلَّم في خيط الواجهة."""
    notified = Signal(str, dict)   # ليس "event": ذلك يحجب QObject.event() الذي تستدعيه Qt
    closed = False

    def notify(self, kind: str, **data) -> None:
        if not self.closed:   # لا إشارات بعد إغلاق الواجهة (كانت تسبب انهياراً عند الخروج)
            self.notified.emit(kind, data)


class TrayApp(QObject):
    def __init__(self, app: QApplication, controller: Controller, bridge: Bridge):
        super().__init__()
        self.app = app
        self.c = controller
        cfg = controller.config
        self.t = Tr(cfg.ui.ui_language)
        self.overlay = Overlay(self.t, cfg.ui.font_scale, cfg.ui.high_contrast, cfg.ui.overlay_seconds)
        self.confirm = ConfirmWindow(self.t, cfg.ui.font_scale, cfg.ui.high_contrast)
        self.confirm.answered.connect(self._on_confirm_answer)
        self.grid = GridOverlay(cfg.ui.font_scale, cfg.ui.high_contrast)
        self.orb: StatusOrb | None = None
        if cfg.ui.status_orb:
            self.orb = StatusOrb(cfg.ui.font_scale, cfg.ui.high_contrast, cfg.ui.orb_corner, self.t.rtl)
            self.orb.place()
            self.orb.show()
        self.wizard = CalibrationWizard(self.t, cfg.ui.font_scale, cfg.ui.high_contrast,
                                        cue=controller.play_cue)
        self.wizard.finished.connect(self._on_calibration_done)
        self._muted = False
        self._last_visual = None

        self.tray = QSystemTrayIcon(state_icon("loading"))
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        self.bridge = bridge
        bridge.notified.connect(self._on_event)

        self.panel = ControlPanel(self.t, cfg.ui.font_scale, cfg.ui.high_contrast)
        b = self.panel.buttons
        b["pause"].clicked.connect(self.c.toggle_pause)
        b["dictation"].clicked.connect(self._toggle_dictation)
        b["grid"].clicked.connect(self.c.show_grid)
        b["calibrate"].clicked.connect(self.c.start_calibration)
        b["settings"].clicked.connect(self.open_settings)
        b["quit"].clicked.connect(self.quit)
        self.panel.hidden_by_user.connect(
            lambda: self.overlay.show_message(self.t("panel_still_running"), state="ready"))
        if cfg.ui.show_panel:
            self.show_panel()

        self._poll = QTimer(self)
        self._poll.setInterval(300)
        self._poll.timeout.connect(self._refresh)
        self._poll.start()
        self._refresh()

    # ---------------- القائمة ----------------
    def _build_menu(self) -> QMenu:
        m = QMenu()
        tr = self.t
        self.act_pause = QAction(tr("menu_pause"), m, triggered=self.c.toggle_pause)
        self.act_mute = QAction(tr("menu_mute"), m, checkable=True, triggered=self._toggle_mute)
        self.act_cont = QAction(tr("menu_continuous"), m, checkable=True,
                                triggered=lambda v: self.c.set_continuous(v))
        self.act_lang = QAction("", m, triggered=self.c.toggle_language)
        self.act_camera = QAction(tr("menu_camera"), m, checkable=True,
                                  triggered=lambda v: self.c.set_camera(v))
        m.addAction(QAction(tr("menu_panel"), m, triggered=self.show_panel))
        m.addSeparator()
        m.addAction(self.act_pause)
        m.addAction(self.act_mute)
        m.addAction(self.act_camera)
        m.addAction(self.act_cont)
        m.addAction(self.act_lang)
        self.menu_profiles = m.addMenu("")
        self._fill_profiles_menu()
        m.addAction(QAction(tr("menu_calibrate"), m, triggered=self.c.start_calibration))
        m.addAction(QAction(tr("menu_settings"), m, triggered=self.open_settings))
        m.addAction(QAction(tr("menu_help"), m, triggered=self.open_help))
        m.addSeparator()
        m.addAction(QAction(tr("menu_refresh_apps"), m, triggered=self.c.refresh_apps))
        m.addAction(QAction(tr("menu_open_folder"), m,
                            triggered=lambda: self.c.os.open_path(paths.user_dir())))
        m.addSeparator()
        hk = self.c.config.safety.emergency_hotkey
        if hk:
            hint = QAction(tr("hotkey_hint", hotkey=hk), m)
            hint.setEnabled(False)
            m.addAction(hint)
        m.addAction(QAction(tr("menu_quit"), m, triggered=self.quit))
        if self.t.rtl:
            m.setLayoutDirection(self.app.layoutDirection())
        return m

    def _fill_profiles_menu(self) -> None:
        """قائمة فرعية: الملف النشط مع علامة، ونقرة واحدة للتبديل."""
        lang = self.c.config.ui.ui_language
        menu = self.menu_profiles
        menu.clear()
        menu.setTitle(self.t("menu_profile", name=self.c.profile.label(lang)))
        for p in self.c.profiles.values():
            act = QAction(p.label(lang), menu, checkable=True)
            act.setChecked(p.id == self.c.profile.id)
            act.triggered.connect(lambda _=False, pid=p.id: self.c.set_profile(pid))
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction(QAction(self.t("menu_manage_profiles"), menu, triggered=self.open_settings))
        if self.t.rtl:
            menu.setLayoutDirection(self.app.layoutDirection())

    def _toggle_mute(self, value: bool):
        self._muted = value
        self.c.set_muted(value)

    def show_panel(self):
        self.panel.show()
        self.panel.raise_()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_panel()

    def _toggle_dictation(self):
        if self.c.snapshot()["mode"] == "dictation":
            self.c.stop_dictation()
        else:
            self.c.start_dictation()

    def quit(self):
        self.bridge.closed = True
        self._poll.stop()
        self.tray.hide()
        self.overlay.hide()
        if self.orb is not None:
            self.orb.hide()
        self.panel.hide()
        self.c.shutdown()
        self.app.quit()

    # ---------------- الحالة ----------------
    def _visual_state(self, s: dict) -> str:
        if s["audio_state"] == "error":
            return "error"
        if s["audio_state"] in ("loading", "starting"):
            return "loading"
        if s["paused"]:
            return "paused"
        if self._muted or s["audio_state"] == "muted":
            return "muted"
        if s["mode"] in ("dictation", "grid"):
            return s["mode"]
        return "armed" if s["armed"] and not s["continuous"] else "ready"

    def _status_text(self, s: dict, visual: str) -> str:
        tr = self.t
        return {
            "error": tr("state_mic_error", detail=s["audio_detail"]),
            "loading": tr("state_loading"),
            "paused": tr("state_paused", wake=s["wake"]),
            "muted": tr("state_muted"),
            "armed": tr("state_armed"),
            "dictation": tr("dict_on"),
            "grid": tr("grid_hint"),
        }.get(visual, tr("state_continuous") if s["continuous"] else tr("state_ready", wake=s["wake"]))

    def _camera_text(self, s: dict) -> str:
        if not s["vision_enabled"]:
            return self.t("cam_off")
        return {
            "tracking": self.t("cam_tracking"),
            "ready": self.t("cam_ready"),
            "error": self.t("cam_error", detail=s["vision_detail"]),
            "no_image": self.t("cam_no_image"),
            "slow": self.t("cam_slow", fps=s["vision_detail"]),
            "dozing": self.t("cam_dozing"),
            "asleep": self.t("cam_asleep"),
        }.get(s["vision_state"], self.t("cam_loading"))

    @Slot()
    def _refresh(self):
        self.c.watchdog()
        s = self.c.snapshot()
        visual = self._visual_state(s)
        text = self._status_text(s, visual)
        self.tray.setIcon(state_icon(visual))
        self.tray.setToolTip(f"{self.t('app_name')}\n{text}\n{self._camera_text(s)}")
        self.act_camera.setChecked(s["vision_enabled"])
        self.act_pause.setText(self.t("menu_resume" if s["paused"] else "menu_pause"))
        self.act_cont.setChecked(s["continuous"])
        self.act_lang.setText(self.t("menu_cmd_lang", lang=self.t(f"lang_{s['language']}")))
        if self.orb is not None:
            self.orb.set_state(visual, s["vision_state"] if s["vision_enabled"] else "off")
        if self.panel.isVisible():
            self.panel.set_state(visual, text, self._camera_text(s), s["paused"], s["mode"])
        if visual != self._last_visual:
            # حالات دائمة تبقى ظاهرة؛ غيرها يظهر لحظياً
            if self.c.config.ui.overlay and visual in ("paused", "error", "armed", "loading", "ready", "muted"):
                sticky = visual in ("paused", "error")
                if visual != "ready" or self._last_visual in ("loading", "paused", "error", "muted"):
                    self.overlay.show_message(text, state=visual, sticky=sticky)
                elif self.overlay.sticky:
                    self.overlay.sticky = False
                    self.overlay.hide()
            self._last_visual = visual

    # ---------------- الإشعارات ----------------
    @Slot(str, dict)
    def _on_event(self, kind: str, d: dict):
        if kind == "voice":
            if self.orb is not None:
                self.orb.set_voice(d["active"], d.get("level", 0.0))
            return
        if kind == "hand":
            if self.orb is not None:
                self.orb.set_hand(d["points"], d.get("pose", "none"))
            return
        if kind == "heard" and d.get("text"):
            self.panel.set_heard(d["text"])
        elif kind == "result" and d.get("heard"):
            self.panel.set_heard(d["heard"], d["ok"])
        if not self.c.config.ui.overlay and kind not in ("confirm", "confirm_cleared"):
            return
        s = self.c.snapshot()
        visual = self._visual_state(s)
        if kind == "partial" and (s["armed"] or s["continuous"]):
            self.overlay.show_message(d["text"] + " …", state=visual)
        elif kind == "wake":
            self.overlay.show_message(self.t("state_armed"), state="armed")
        elif kind == "result":
            ok = d["ok"]
            msg = self.t(d["key"], **{k: v for k, v in d.get("values", {}).items()})
            line1 = d.get("heard") or d.get("command") or ""
            self.overlay.show_message(("✓ " if ok else "✗ ") + line1, msg,
                                      state=visual, color="ok" if ok else "err",
                                      sticky=s["paused"] and not ok)
        elif kind == "confirm":
            self.confirm.ask(d["heard"])
            self.overlay.show_message(self.t("confirm_prompt", heard=d["heard"]), state="armed", sticky=True)
        elif kind == "confirm_cleared":
            self.confirm.hide()
            self.overlay.sticky = False
            if not d.get("executed"):
                self.overlay.show_message(self.t("confirm_cancelled"), state=visual)
        elif kind == "state":
            self._last_visual = None
            self._refresh()
        elif kind == "gesture" and d.get("action") and d["action"] not in ("app.pause", "app.resume"):
            self.overlay.show_message(self.t("gesture_done", action=d["action"]), state=visual, color="ok")
        elif kind == "status" and d.get("source") == "vision" and d.get("state") == "error":
            self.overlay.show_message(self.t("cam_error", detail=d.get("detail", "")), state="error", color="err")
        elif kind == "status" and d.get("source") == "vision" and d.get("state") == "no_image":
            self.overlay.show_message(self.t("cam_no_image"), state=visual, color="err")
        elif kind == "status" and d.get("source") == "vision" and d.get("state") == "asleep":
            self.overlay.show_message(self.t("cam_asleep"), self.t("cam_asleep_hint", wake=s["wake"]),
                                      state=visual)
        elif kind == "status" and d.get("source") == "vision" and d.get("state") == "slow":
            self.overlay.show_message(self.t("cam_slow", fps=d.get("detail", "?")), state=visual, color="err")
        # ---- الإملاء ----
        elif kind == "mode" and d["name"] == "dictation":
            if d["active"]:
                self.overlay.show_message(self.t("dict_on"), state="dictation", sticky=True)
            else:
                pending = d.get("pending", 0)
                self.overlay.show_message(self.t("dict_off"),
                                          self.t("dict_pending", count=pending) if pending else "",
                                          state=visual)
        elif kind == "dictation_pending" and s["mode"] == "dictation":
            loading = s["dictation_state"] == "loading"
            self.overlay.show_message(self.t("dict_on"),
                                      self.t("dict_loading") if loading else
                                      self.t("dict_pending", count=d["count"]),
                                      state="dictation", sticky=True)
        elif kind == "dictation_typed":
            line2 = self.t("dict_pending", count=d["pending"]) if d["pending"] else ""
            self.overlay.show_message("✎ " + (d["text"] or "…"), line2,
                                      state=visual, sticky=s["mode"] == "dictation")
        elif kind == "status" and d.get("source") == "dictation" and d.get("state") == "error":
            self.overlay.show_message(self.t("dict_error", detail=d.get("detail", "")), state="error", color="err")
        # ---- الشبكة ----
        elif kind == "grid":
            self.grid.show_grid(d["rect"], d["level"], d["can_split"])
            self.overlay.show_message(self.t("grid_hint"), state="grid", sticky=True)
        elif kind == "mode" and d["name"] == "grid" and not d["active"]:
            self.grid.hide()
            self.overlay.sticky = False
            self.overlay.hide()
        # ---- المعايرة ----
        elif kind == "calibration" and d["state"] == "start":
            self.wizard.start()
        elif kind == "calibration" and d["state"] == "no_camera":
            self.overlay.show_message(self.t("calib_no_camera"), state=visual, color="err")
        elif kind == "calib_sample":
            self.wizard.add_sample(d["sample"])
        elif kind == "open_settings":
            self.open_settings()
        elif kind == "open_help":
            self.open_help()
        elif kind == "profile":
            self._fill_profiles_menu()
            self.overlay.show_message(self.t("profile_switched", name=d["name"]), state=visual, color="ok")
            if getattr(self, "settings", None) is not None and self.settings.profiles_tab is not None:
                self.settings.profiles_tab.refresh()
        elif kind == "lang_fallback":
            self.overlay.show_message(self.t("lang_fallback", wanted=self.t(f"lang_{d['wanted']}"),
                                             used=self.t(f"lang_{d['used']}")),
                                      self.t("lang_pack_hint"), state=visual)
        elif kind == "profiles_changed":
            self._fill_profiles_menu()

    def open_help(self):
        """يفتح الدليل المحلي في المتصفح بلغة الواجهة (ملف ثابت، بلا إنترنت)."""
        page = paths.help_dir() / f"{self.c.config.ui.ui_language}.html"
        if not page.exists():
            page = paths.help_dir() / "index.html"
        try:
            self.c.os.open_path(page)
        except OSError:
            self.overlay.show_message(self.t("help_missing"), str(page), state="error", color="err")

    def open_settings(self):
        from audio.capture import list_input_devices
        from ui.settings_window import SettingsWindow
        try:
            mics = list_input_devices()
        except Exception:  # noqa: BLE001 - أنظمة بلا WinMM
            mics = []
        self.settings = SettingsWindow(self.t, self.c.config, paths.models_dir(), mics,
                                       on_save=self._on_settings_saved,
                                       on_calibrate=self.c.start_calibration,
                                       on_open_folder=lambda: self.c.os.open_path(paths.user_dir()),
                                       profiles_api=self.c)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _on_settings_saved(self, changes: dict):
        restart_needed = self.c.apply_settings(changes)
        self.overlay.show_message(self.t("set_restart_needed" if restart_needed else "set_saved"),
                                  state="ready", color="ok")

    def _on_calibration_done(self, changes):
        self.c.end_calibration(changes)
        if changes:
            self.overlay.show_message(self.t("calib_saved"), state="ready", color="ok")

    def _on_confirm_answer(self, yes: bool):
        if yes:
            self.c.dispatcher.confirm_pending()
        else:
            self.c.dispatcher.cancel_pending()
