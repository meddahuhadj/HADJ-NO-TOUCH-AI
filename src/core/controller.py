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
from config import macros as mac
from config import profiles as prof
from config.loader import load_command_specs, load_config, update_user_config
from config.schema import AppConfig
from core import edition, paths
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
        from commands.actions import unsupported_actions
        self.unsupported = unsupported_actions(backend)
        self.base_specs = self._supported(load_command_specs())
        if self.unsupported:
            log.info("إجراءات غير مدعومة على هذا النظام (أُخفيت أوامرها): %s", sorted(self.unsupported))
        self.profiles = prof.load_profiles(self.base_specs)
        self.profile = self.profiles.get(self.config.profiles.active) or self.profiles[prof.STANDARD]
        self.macros = mac.load_macros(self._non_macro_specs(), self.config.safety.emergency_hotkey)
        self.parser = CommandParser(self._command_specs(), sp.match_threshold)
        self.gate = WakeGate(self._wake_words(), sp.continuous_listening,
                             sp.wake_timeout_s, sp.followup_s)
        self.apps = AppIndex(backend.list_apps, self.config.app_aliases,
                             paths.user_dir() / "apps_cache.json")
        self.ctx = ActionContext(os=backend, apps=self.apps, app=self, config=self.config)
        self.dispatcher = Dispatcher(self.ctx, self.parser, self.gate, self.notify, self.paused)
        self.dispatcher.on_mode_exit = self._on_mode_exit
        self.dictation_state = "off"
        self.calibrating = False
        self.languages = edition.available_languages()
        self.lang_fallback: str | None = None
        self._apply_language_fallback()

        self.audio = Worker("audio", self.mp, self.hub, audio_worker.run,
                            lambda: (self.audio_config(),))
        self.vision = Worker("vision", self.mp, self.hub, vision_worker.run,
                             lambda: (self.vision_config(), str(paths.models_dir())))
        self._sync_vision_pause()

    def _apply_language_fallback(self) -> None:
        """نموذج لغة الأوامر غير مثبّت (مثل العربية في النسخة الخفيفة) ← لغة متاحة، في الذاكرة فقط:
        إعداد المستخدم يبقى كما هو، فيعود تلقائياً عند تثبيت الحزمة."""
        wanted = self.config.speech.language
        lang = edition.fallback_language(wanted, self.languages)
        self.lang_fallback = wanted if lang != wanted else None
        if self.lang_fallback:
            log.warning("نموذج اللغة %s غير مثبّت؛ أوامر بـ %s", wanted, lang)
            self.config.speech.language = lang
            self.gate.wake_words = self._wake_words()

    def dictation_engine(self) -> str:
        dc = self.config.dictation
        return "whisper" if dc.engine == "whisper" and edition.whisper_available() else "vosk"

    def _sync_vision_pause(self) -> None:
        msg = ControlMessage("paused", {"value": self.paused.is_set()})
        self.hub.set_initial("vision", [msg])   # لعملية رؤية تتصل لاحقاً
        self.hub.send("vision", msg)

    def notify(self, kind: str, **data) -> None:
        if kind == "wake" or (kind == "result" and data.get("ok") and data.get("heard")):
            self.wake_camera()   # من يتكلم حاضر: الكاميرا النائمة تستعد
        if kind == "status" and data.get("source") == "vision":
            self._vision_sound(data.get("state", ""))
        if kind == "status" and data.get("source") == "dictation":
            self.dictation_state = data["state"]
            log.info("حالة الإملاء: %s %s", data["state"], data.get("detail", ""))
        if kind == "status":
            w = {"audio": self.audio, "vision": self.vision}.get(data.get("source"))
            if w is not None:
                w.state = (data["state"], data.get("detail", ""))
                log.info("حالة %s: %s %s", w.name, data["state"], data.get("detail", ""))
        self._notify(kind, **data)

    def _vision_sound(self, state: str) -> None:
        """تنبيه صوتي لحالة الكاميرا: ضروري لمن لا يرى مؤشر الحالة."""
        prev = self.vision.state[0]
        if state == prev or self.paused.is_set() or self.calibrating:
            return
        if state in ("error", "no_image"):
            self._sound("error")
        elif self.config.feedback.hand_sounds:
            if state == "tracking":
                self._sound("hand")
            elif state == "ready" and prev == "tracking":
                self._sound("hand_lost")

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
        if self.lang_fallback:
            self.notify("lang_fallback", wanted=self.lang_fallback, used=self.config.speech.language)

    def _log_level(self) -> str:
        return logging.getLevelName(logging.getLogger().level)

    def _supported(self, specs: list[dict]) -> list[dict]:
        def actions(spec):
            if "steps" in spec:
                return {s.get("action") for s in spec["steps"]}
            return {spec.get("action")}
        return [s for s in specs if not actions(s) & self.unsupported]

    def _command_specs(self) -> list[dict]:
        """الأساسية + الماكرو + أوامر الملف الشخصي النشط + أوامر التبديل بين الملفات."""
        return [*self.base_specs, *self.macros, *self._supported(self.profile.commands),
                *prof.switch_specs(self.profiles)]

    def _non_macro_specs(self) -> list[dict]:
        """كل ما قد يتعارض مع عبارة ماكرو (الماكرو عام: يُقارن بأوامر كل الملفات الشخصية)."""
        own = [c for p in self.profiles.values() for c in p.commands]
        return [*self.base_specs, *own, *prof.switch_specs(self.profiles)]

    def _grammar(self) -> dict:
        sp = self.config.speech
        grammar = {}
        latin = [a for a in self.config.app_aliases if not any("؀" <= ch <= "ۿ" for ch in a)]
        for lang in LANGUAGES:
            # "open notepad" / "ouvre calculatrice"... لكي يتعرف المُعرِّف المقيّد على أسماء التطبيقات الشائعة
            verb = {"en": "open", "fr": "ouvre"}.get(lang)
            extra = [f"{verb} {a}" for a in latin] if verb else []
            extra += grid_and_dictation_phrases(lang)
            grammar[lang] = build_grammar(self.parser, lang, sp.wake_words.get(lang, []), extra)
        return grammar

    def audio_config(self) -> dict:
        sp = self.config.speech
        grammar = self._grammar()
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
        d["hand_preview"] = self.config.ui.status_orb
        d["bindings"] = self.effective_bindings()
        return d

    def effective_bindings(self) -> dict[str, str]:
        """الإعدادات العامة ← إيماءات الماكرو ← الملف الشخصي النشط ← القبضة المقفلة."""
        base = {**self.config.vision.bindings, **mac.bindings_for(self.macros)}
        out = prof.effective_bindings(base, self.profile)
        # إيماءة مربوطة بإجراء غير مدعوم على هذا النظام ← معطّلة (القبضة لا تُمس)
        return {g: ("none" if a in self.unsupported and g != "fist_hold" else a) for g, a in out.items()}

    _wake_sent = 0.0

    def wake_camera(self) -> bool:
        """يوقظ الكاميرا من السكون (لا يشغّلها إن أوقفها المستخدم بنفسه)."""
        import time
        if not self.vision.wanted or self.vision.state[0] not in ("dozing", "asleep"):
            return False
        now = time.monotonic()
        if now - self._wake_sent < 2.0:   # رسالة واحدة تكفي حتى تتغير الحالة
            return True
        self._wake_sent = now
        self.vision.send("wake")
        return True

    def watchdog(self) -> None:
        """يُستدعى دورياً من الواجهة."""
        if self.stopping:
            return
        if self.config.vision.wake_on_input and self.vision.state[0] == "asleep":
            idle = self.os.seconds_since_input()
            if idle is not None and idle < 1.0:
                self.wake_camera()
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
            "profile": self.profile.id,
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

    def set_language(self, lang: str) -> bool:
        """يرجع False إن لم يكن نموذج اللغة مثبّتاً."""
        if lang not in self.languages:
            return False
        if lang == self.config.speech.language:
            return True
        self.lang_fallback = None
        self.config.speech.language = lang
        self.gate.wake_words = self._wake_words()
        self.gate.disarm()
        self.audio.send("reload", language=lang)
        update_user_config({"speech": {"language": lang}})
        self.notify("state", **self.snapshot())
        return True

    def toggle_language(self) -> None:
        """بالتناوب بين اللغات المثبّتة: العربية ← الإنجليزية ← الفرنسية ← العربية."""
        langs = self.languages or list(LANGUAGES)
        cur = self.config.speech.language
        i = langs.index(cur) if cur in langs else -1
        self.set_language(langs[(i + 1) % len(langs)])

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
        engine = self.dictation_engine()   # النسخة الخفيفة: Vosk دائماً
        self.dictation_state = "loading" if engine == "whisper" else "ready"
        self.audio.send("dictation", on=True, engine=engine, model=dc.whisper_model,
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

    def open_help(self) -> None:
        self.notify("open_help")

    # ---------------- الملفات الشخصية ----------------
    def set_profile(self, pid: str) -> bool:
        p = self.profiles.get(pid)
        if p is None:
            return False
        changed = p.id != self.profile.id
        self.profile = p
        if changed:
            self.config.profiles.active = p.id
            update_user_config({"profiles": {"active": p.id}})
            self._apply_profile()
            log.info("الملف الشخصي: %s", p.id)
        self._sound("ok")
        self.notify("profile", id=p.id, name=p.label(self.config.ui.ui_language))
        self.notify("state", **self.snapshot())
        return True

    def _apply_profile(self) -> None:
        """دون إعادة تشغيل أي عملية: قواعد صوت جديدة وربط إيماءات جديد فوراً."""
        parser = CommandParser(self._command_specs(), self.config.speech.match_threshold)
        self.parser = parser
        self.dispatcher.parser = parser
        self.audio.send("set_grammar", grammar=self._grammar())
        self.vision.send("bindings", bindings=self.effective_bindings())

    def reload_profiles(self) -> None:
        """بعد استيراد/نسخ/حذف/تعديل ملف: إعادة القراءة من القرص."""
        self.profiles = prof.load_profiles(self.base_specs)
        self.profile = self.profiles.get(self.profile.id) or self.profiles[prof.STANDARD]
        self.config.profiles.active = self.profile.id
        self._apply_profile()
        self.notify("profiles_changed")

    def import_profile(self, path) -> tuple["prof.Profile", list[str]]:
        p, warnings = prof.import_profile(path, self.base_specs, self.profiles)
        self.reload_profiles()
        return self.profiles[p.id], warnings

    def export_profile(self, pid: str, dest) -> None:
        prof.export_profile(self.profiles[pid], dest)

    def duplicate_profile(self, pid: str, name: str) -> "prof.Profile":
        p = prof.duplicate_profile(self.profiles[pid], name, self.profiles, self.base_specs)
        self.reload_profiles()
        return self.profiles[p.id]

    def delete_profile(self, pid: str) -> None:
        prof.delete_profile(self.profiles[pid])
        if pid == self.profile.id:
            self.set_profile(prof.STANDARD)
        self.reload_profiles()

    # ---------------- الماكرو ----------------
    def save_macro(self, data: dict) -> dict:
        """ينشئ ماكرو أو يعدّله (data["id"] موجود = تعديل). يرفع MacroError برسالة للواجهة."""
        others = [m for m in self.macros if m["id"] != data.get("id")]
        owners = mac.phrase_owners([*self._non_macro_specs(), *others])
        spec = mac.build_macro(data, owners, self.config.safety.emergency_hotkey,
                               {m["id"] for m in others})
        if spec.get("gesture"):   # إيماءة واحدة لماكرو واحد: الأحدث يأخذها
            others = [{k: v for k, v in m.items() if not (k == "gesture" and v == spec["gesture"])}
                      for m in others]
        idx = next((i for i, m in enumerate(self.macros) if m["id"] == data.get("id")), None)
        self.macros = others[:idx] + [spec] + others[idx:] if idx is not None else [*others, spec]
        mac.save_macros(self.macros)
        self._apply_profile()
        self.notify("macros_changed")
        return spec

    def delete_macro(self, mid: str) -> None:
        self.macros = [m for m in self.macros if m["id"] != mid]
        mac.save_macros(self.macros)
        self._apply_profile()
        self.notify("macros_changed")

    def save_profile_bindings(self, pid: str, bindings: dict[str, str]) -> list[str]:
        """يحفظ تبديلات الإيماءات لملف مستخدم (تمر بنفس التحقق الأمني). يرجع التحذيرات."""
        data = self.profiles[pid].to_dict()
        data["bindings"] = {g: a for g, a in bindings.items() if a}
        p, warnings = prof.parse_profile(data, self.base_specs)
        prof.save_profile(p)
        self.reload_profiles()
        return warnings

    def apply_settings(self, changes: dict) -> bool:
        """يحفظ التغييرات ويطبّقها. يرجع True إذا احتاجت إعادة تشغيل التطبيق (لغة/خط/تباين)."""
        before = self.config.model_copy(deep=True)
        update_user_config(changes)
        new = load_config()
        for name in type(self.config).model_fields:   # في المكان: ctx.config يشير لنفس الكائن
            setattr(self.config, name, getattr(new, name))
        self._apply_language_fallback()
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

    def play_cue(self, kind: str) -> None:
        """للواجهة: نغمة تأكيد (تحترم إعداد الأصوات ومستواها)."""
        self._sound(kind)

    def _sound(self, kind: str) -> None:
        fb = self.config.feedback
        if fb.sounds:
            try:
                self.os.play_sound(kind, fb.sound_volume)
            except Exception:  # noqa: BLE001
                pass
