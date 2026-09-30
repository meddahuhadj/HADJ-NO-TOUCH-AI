"""المتحكم الرئيسي: يربط الإعدادات وطبقة النظام والموزّع والعمليات الفرعية.

لا يعتمد على Qt؛ الواجهة تتلقى الإشعارات عبر دالة notify وتقرأ snapshot().
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import queue
import threading
from typing import Callable

from audio import worker as audio_worker
from commands.actions import ActionContext
from commands.dispatcher import Dispatcher
from commands.grammar import build_grammar, grid_and_dictation_phrases
from commands.modes import DictationMode, GridMode
from commands.parser import CommandParser
from commands.wake import WakeGate
from config.loader import load_command_specs, load_config, update_user_config
from config.schema import AppConfig
from core import paths
from core.events import ControlMessage
from core.ipc import Hub
from os_layer.apps_index import AppIndex
from os_layer.base import OSBackend
from vision import worker as vision_worker

log = logging.getLogger(__name__)
MAX_RESTARTS = 3
LANGUAGES = ("ar", "en", "fr")


class Worker:
    """عملية فرعية مع حالة وإعادة تشغيل تلقائية عند التعطل.

    لا تُمرَّر للعملية أي كائنات multiprocessing (طوابير/أحداث)، بل عنوان الأنبوب ومفتاحه فقط.
    """

    def __init__(self, name: str, ctx, hub: Hub, target, args_factory: Callable[[], tuple]):
        self.name = name
        self.ctx = ctx
        self.hub = hub
        self.target = target
        self.args_factory = args_factory
        self.proc = None
        self.state = ("stopped", "")
        self.restarts = 0
        self.wanted = False

    def start(self) -> None:
        self.wanted = True
        self.state = ("loading", "")
        args = (*self.args_factory(), self.hub.address, self.hub.authkey)
        self.proc = self.ctx.Process(target=self.target, args=args, daemon=True, name=self.name)
        self.proc.start()

    def send(self, kind: str, **payload) -> bool:
        return self.hub.send(self.name, ControlMessage(kind, payload))

    def stop(self, timeout: float = 3) -> None:
        self.wanted = False
        if self.proc is None:
            return
        self.send("shutdown")
        self.proc.join(timeout=timeout)
        if self.proc.is_alive():
            self.proc.terminate()
        self.proc = None
        self.state = ("stopped", "")

    def check(self) -> bool:
        """يرجع False إذا تعطلت العملية نهائياً."""
        if not self.wanted or self.proc is None or self.proc.is_alive():
            return True
        if self.state[0] == "error":   # خطأ معروف (ميكروفون/كاميرا) ← لا إعادة تشغيل
            return True
        if self.restarts < MAX_RESTARTS:
            self.restarts += 1
            log.warning("العملية %s توقفت (رمز الخروج %s)؛ إعادة تشغيل (%d)",
                        self.name, self.proc.exitcode, self.restarts)
            self.start()
            return True
        self.state = ("error", f"{self.name} process crashed")
        return False


class Controller:
    def __init__(self, backend: OSBackend, notify: Callable[..., None],
                 config: AppConfig | None = None):
        self.os = backend
        self._notify = notify
        self.config = config or load_config()
        self.mp = mp.get_context("spawn")
        self.paused = threading.Event()    # يُرسل لعملية الرؤية كرسالة "paused" عند كل تغيير
        self.stopping = False
        self.events: queue.Queue = queue.Queue()
        self.hub = Hub(self.events)
        self._dispatch_stop = threading.Event()
        self._dispatch_thread: threading.Thread | None = None

        sp = self.config.speech
        self.parser = CommandParser(load_command_specs(), sp.match_threshold)
        self.gate = WakeGate(self._wake_words(), sp.continuous_listening,
                             sp.wake_timeout_s, sp.followup_s)
        self.apps = AppIndex(backend.list_apps, self.config.app_aliases,
                             paths.user_dir() / "apps_cache.json")
        self.ctx = ActionContext(os=backend, apps=self.apps, app=self, config=self.config)
        self.dispatcher = Dispatcher(self.ctx, self.parser, self.gate, self.notify, self.paused)
        self.dispatcher.on_mode_exit = self._on_mode_exit
        self.dictation_state = "off"
        self.calibrating = False

        self.audio = Worker("audio", self.mp, self.hub, audio_worker.run,
                            lambda: (self.audio_config(),))
        self.vision = Worker("vision", self.mp, self.hub, vision_worker.run,
                             lambda: (self.vision_config(), str(paths.models_dir())))
        self._sync_vision_pause()

    def _sync_vision_pause(self) -> None:
        msg = ControlMessage("paused", {"value": self.paused.is_set()})
        self.hub.set_initial("vision", [msg])   # لعملية رؤية تتصل لاحقاً
        self.hub.send("vision", msg)

    def notify(self, kind: str, **data) -> None:
        if kind == "status" and data.get("source") == "dictation":
            self.dictation_state = data["state"]
            log.info("حالة الإملاء: %s %s", data["state"], data.get("detail", ""))
        if kind == "status":
            w = {"audio": self.audio, "vision": self.vision}.get(data.get("source"))
            if w is not None:
                w.state = (data["state"], data.get("detail", ""))
                log.info("حالة %s: %s %s", w.name, data["state"], data.get("detail", ""))
        self._notify(kind, **data)

    def _wake_words(self) -> list[str]:
        sp = self.config.speech
        return sp.wake_words.get(sp.language) or ["computer"]

    # ------------------------------------------------------------------
    def start(self) -> None:
        if not self.apps.load_cache():
            log.info("لا توجد ذاكرة تطبيقات؛ ستتم الفهرسة الآن")
        self.apps.refresh_async()
        self.audio.start()
        if self.config.vision.enabled:
            self.vision.start()
        self._dispatch_thread = threading.Thread(
            target=self.dispatcher.run, args=(self.events, self._dispatch_stop),
            daemon=True, name="dispatcher")
        self._dispatch_thread.start()
        hk = self.config.safety.emergency_hotkey
        if hk:
            self.os.register_hotkey(hk, self.toggle_pause)

    def _log_level(self) -> str:
        return logging.getLevelName(logging.getLogger().level)

    def audio_config(self) -> dict:
        sp = self.config.speech
        grammar = {}
        latin = [a for a in self.config.app_aliases if not any("؀" <= ch <= "ۿ" for ch in a)]
        for lang in LANGUAGES:
            # "open notepad" / "ouvre calculatrice"... لكي يتعرف المُعرِّف المقيّد على أسماء التطبيقات الشائعة
            verb = {"en": "open", "fr": "ouvre"}.get(lang)
            extra = [f"{verb} {a}" for a in latin] if verb else []
            extra += grid_and_dictation_phrases(lang)
            grammar[lang] = build_grammar(self.parser, lang, sp.wake_words.get(lang, []), extra)
        return {
            "language": sp.language,
            "models_dir": str(paths.models_dir()),
            "use_grammar": sp.use_grammar,
            "input_device": sp.input_device,
            "vad_aggressiveness": sp.vad_aggressiveness,
            "silence_ms": sp.silence_ms,
            "max_utterance_s": sp.max_utterance_s,
            "grammar": grammar,
            "log_level": self._log_level(),
        }

    vision_dry_run = False   # للاختبار: تتبع اليد دون تحريك المؤشر (--vision-dry-run)

    def vision_config(self) -> dict:
        d = self.config.vision.model_dump()
        d["log_level"] = self._log_level()
        d["dry_run"] = self.vision_dry_run
        return d

    def watchdog(self) -> None:
        """يُستدعى دورياً من الواجهة."""
        if self.stopping:
            return
        for w in (self.audio, self.vision):
            if not w.check():
                self.notify("status", source=w.name, state="error", detail=w.state[1])

    def shutdown(self) -> None:
        """آمن للاستدعاء أكثر من مرة. ينتظر خيط الموزّع حتى لا يرسل إشعارات بعد إغلاق الواجهة."""
        if self.stopping:
            return
        self.stopping = True
        self.audio.stop()
        self.vision.stop()
        self._dispatch_stop.set()
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=2)
        self.hub.close()
        self.os.release_all()
        self.os.close()

    def snapshot(self) -> dict:
        return {
            "paused": self.paused.is_set(),
            "armed": self.gate.armed,
            "continuous": self.gate.continuous,
            "language": self.config.speech.language,
            "wake": self._wake_words()[0],
            "audio_state": self.audio.state[0],
            "audio_detail": self.audio.state[1],
            "vision_enabled": self.vision.wanted,
            "vision_state": self.vision.state[0],
            "vision_detail": self.vision.state[1],
            "pending": self.dispatcher.pending is not None,
            "mode": self.dispatcher.mode.name if self.dispatcher.mode else None,
            "dictation_state": self.dictation_state,
        }

    # ---------------- AppControl ----------------
    def pause(self) -> None:
        self.paused.set()
        self._sync_vision_pause()
        self.dispatcher.exit_mode(abort=True)   # لا إملاء ولا شبكة بعد الإيقاف الطارئ
        self.os.release_all()
        self.dispatcher.cancel_pending()
        self.gate.disarm()
        self._sound("pause")
        self.notify("state", **self.snapshot())

    def resume(self) -> None:
        self.paused.clear()
        self._sync_vision_pause()
        self.gate.after_command()
        self._sound("resume")
        self.notify("state", **self.snapshot())

    def toggle_pause(self) -> None:
        self.resume() if self.paused.is_set() else self.pause()

    def sleep(self) -> None:
        self.gate.disarm()
        self.notify("state", **self.snapshot())

    def set_language(self, lang: str) -> None:
        if lang not in LANGUAGES or lang == self.config.speech.language:
            return
        self.config.speech.language = lang
        self.gate.wake_words = self._wake_words()
        self.gate.disarm()
        self.audio.send("reload", language=lang)
        update_user_config({"speech": {"language": lang}})
        self.notify("state", **self.snapshot())

    def toggle_language(self) -> None:
        """بالتناوب: العربية ← الإنجليزية ← الفرنسية ← العربية."""
        cur = self.config.speech.language
        i = LANGUAGES.index(cur) if cur in LANGUAGES else -1
        self.set_language(LANGUAGES[(i + 1) % len(LANGUAGES)])

    def set_continuous(self, value: bool) -> None:
        self.config.speech.continuous_listening = value
        self.gate.continuous = value
        update_user_config({"speech": {"continuous_listening": value}})
        self.notify("state", **self.snapshot())

    def set_muted(self, value: bool) -> None:
        self.audio.send("mute", value=value)

    def set_camera(self, enabled: bool) -> None:
        """إيقاف الكاميرا يحرّرها كلياً (يُطفأ ضوء الكاميرا)."""
        if enabled and not self.vision.wanted:
            self.vision.restarts = 0
            self.vision.start()
        elif not enabled and self.vision.wanted:
            threading.Thread(target=self.vision.stop, daemon=True).start()
            self.vision.wanted = False
        self.config.vision.enabled = enabled
        update_user_config({"vision": {"enabled": enabled}})
        self.notify("state", **self.snapshot())

    def refresh_apps(self) -> None:
        self.apps.refresh_async()

    def start_dictation(self) -> None:
        dc = self.config.dictation
        self.dictation_state = "loading" if dc.engine == "whisper" else "ready"
        self.audio.send("dictation", on=True, engine=dc.engine, model=dc.whisper_model,
                        threads=dc.threads, beam_size=dc.beam_size)
        self.dispatcher.enter_mode(DictationMode(self.dispatcher, self.config.speech.language))

    def stop_dictation(self) -> None:
        if isinstance(self.dispatcher.mode, DictationMode):
            self.dispatcher.exit_mode()

    def show_grid(self) -> None:
        self.dispatcher.enter_mode(GridMode(self.dispatcher, self.config.grid.timeout_s))

    # ---------------- الإعدادات ----------------
    def open_settings(self) -> None:
        self.notify("open_settings")

    def apply_settings(self, changes: dict) -> bool:
        """يحفظ التغييرات ويطبّقها. يرجع True إذا احتاجت إعادة تشغيل التطبيق (لغة/خط/تباين)."""
        before = self.config.model_copy(deep=True)
        update_user_config(changes)
        new = load_config()
        for name in type(self.config).model_fields:   # في المكان: ctx.config يشير لنفس الكائن
            setattr(self.config, name, getattr(new, name))
        sp = self.config.speech
        self.gate.wake_words = self._wake_words()
        self.gate.continuous = sp.continuous_listening
        self.gate.timeout_s, self.gate.followup_s = sp.wake_timeout_s, sp.followup_s
        self.parser.threshold = sp.match_threshold
        self.apps.set_aliases(self.config.app_aliases)

        if before.speech != self.config.speech or before.dictation != self.config.dictation:
            self._restart_worker(self.audio)
        if before.vision != self.config.vision:
            if self.config.vision.enabled:
                self._restart_worker(self.vision)
            elif self.vision.wanted:
                threading.Thread(target=self.vision.stop, daemon=True).start()
                self.vision.wanted = False
        if before.safety.emergency_hotkey != self.config.safety.emergency_hotkey:
            self.os.close()
            if self.config.safety.emergency_hotkey:
                self.os.register_hotkey(self.config.safety.emergency_hotkey, self.toggle_pause)
        log.info("طُبّقت الإعدادات")
        self.notify("state", **self.snapshot())
        return before.ui != self.config.ui

    def _restart_worker(self, w: Worker) -> None:
        def run():
            if w.wanted:
                w.stop()
            w.restarts = 0
            w.start()
        threading.Thread(target=run, daemon=True, name=f"{w.name}-restart").start()

    # ---------------- المعايرة ----------------
    def start_calibration(self) -> None:
        """الواجهة تفتح معالج المعايرة عند إشعار calibration/start وتستقبل العينات."""
        if not self.vision.wanted or self.vision.state[0] in ("error", "no_image", "loading"):
            self.notify("calibration", state="no_camera")
            return
        self.calibrating = True
        self.vision.send("calibrate", on=True)
        self.notify("calibration", state="start")

    def end_calibration(self, changes: dict | None) -> None:
        """changes: تغييرات الإعدادات من CalibrationResult.config_changes() أو None للإلغاء."""
        self.calibrating = False
        self.vision.send("calibrate", on=False)
        if not changes:
            return
        update_user_config(changes)
        v = changes.get("vision", {})
        if "tuning" in v:
            for k, val in v["tuning"].items():
                setattr(self.config.vision.tuning, k, val)
        if "control_zone" in v:
            self.config.vision.control_zone = tuple(v["control_zone"])
        log.info("المعايرة حُفظت: %s", v)

        def restart():   # عملية الرؤية تقرأ إعداداتها عند البدء
            self.vision.stop()
            self.vision.restarts = 0
            self.vision.start()
        threading.Thread(target=restart, daemon=True, name="vision-restart").start()

    def _on_mode_exit(self, name: str, abort: bool) -> None:
        if name == "dictation":
            # بدون abort: Whisper يكمل تحويل ما قيل قبل "أوقف الإملاء" ثم يتحرر
            self.audio.send("dictation", on=False, abort=abort)

    def _sound(self, kind: str) -> None:
        if self.config.feedback.sounds:
            try:
                self.os.play_sound(kind)
            except Exception:  # noqa: BLE001
                pass
