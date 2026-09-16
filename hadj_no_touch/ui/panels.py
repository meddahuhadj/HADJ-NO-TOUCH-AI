"""v2.0 panels: Macro Studio, AI plan preview, Test Lab, Settings Center,
and the quick-start Help dialog. All follow the dark dashboard theme.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QListWidget, QTabWidget, QWidget,
    QSpinBox, QDoubleSpinBox, QCheckBox, QMessageBox, QGroupBox,
)

from .dashboard import DARK
from ..i18n import tr, trf


def _empty(text: str) -> str:
    return (text or "").strip()


class MacroStudioDialog(QDialog):
    """Create / edit / delete macros and custom voice commands."""

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle(tr("Macro Studio & Custom Commands"))
        self.resize(720, 520)
        self.setStyleSheet(DARK)
        self._current = ""
        self._build()
        self.reload_macros()

    # ---- construction ------------------------------------------------------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_macros(), tr("Macros (voice / gesture / button)"))
        tabs.addTab(self._build_commands(), tr("Custom voice commands"))
        lay.addWidget(tabs, 1)
        close = QPushButton(tr("Close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

    def _build_macros(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        row = QHBoxLayout()
        self.macro_list = QListWidget()
        self.macro_list.setMaximumWidth(230)
        self.macro_list.currentItemChanged.connect(self._on_select)
        row.addWidget(self.macro_list, 1)

        form = QWidget()
        fl = QGridLayout(form)
        self.f_name = QLineEdit()
        self.f_trigger = QComboBox()
        self.f_trigger.addItem(tr("Voice phrase"), "voice")
        self.f_trigger.addItem(tr("Gesture"), "gesture")
        self.f_trigger.addItem(tr("Button"), "button")
        self.f_trigger_value = QLineEdit()
        self.f_trigger_value.setPlaceholderText(tr("e.g. 'go to work' / CIRCLE_CW / quick_action"))
        self.f_actions = QTextEdit()
        self.f_actions.setPlaceholderText(
            tr("One registered action per line, optional key=value params.\n"
               "Examples:\n"
               "  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50"))
        self.f_desc = QLineEdit()
        self.f_desc.setPlaceholderText(tr("optional description"))
        fl.addWidget(QLabel(tr("Name")), 0, 0)
        fl.addWidget(self.f_name, 0, 1)
        fl.addWidget(QLabel(tr("Trigger")), 1, 0)
        fl.addWidget(self.f_trigger, 1, 1)
        fl.addWidget(QLabel(tr("Value")), 2, 0)
        fl.addWidget(self.f_trigger_value, 2, 1)
        fl.addWidget(QLabel(tr("Actions")), 3, 0, alignment=Qt.AlignmentFlag.AlignTop)
        fl.addWidget(self.f_actions, 3, 1)
        fl.addWidget(QLabel(tr("Description")), 4, 0)
        fl.addWidget(self.f_desc, 4, 1)
        btns = QHBoxLayout()
        b_new = QPushButton(tr("New"))
        b_save = QPushButton(tr("Save"))
        b_del = QPushButton(tr("Delete"))
        b_run = QPushButton(tr("Run now"))
        b_new.clicked.connect(self._new_macro)
        b_save.clicked.connect(self._save_macro)
        b_del.clicked.connect(self._delete_macro)
        b_run.clicked.connect(self._run_macro)
        for b in (b_new, b_save, b_del, b_run):
            btns.addWidget(b)
        fl.addLayout(btns, 5, 1)
        row.addWidget(form, 2)
        lay.addLayout(row)
        return w

    def _build_commands(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.cmd_list = QListWidget()
        self.cmd_list.setMaximumWidth(230)
        row.addWidget(self.cmd_list, 1)
        form = QWidget()
        fl = QGridLayout(form)
        self.c_phrase = QLineEdit()
        self.c_phrase.setPlaceholderText(tr("phrase, e.g. 'boost volume'"))
        self.c_action = QComboBox()
        reg = self.core.safety.registry if hasattr(self.core, "safety") else None
        actions = sorted(reg.ids()) if reg else []
        for a in actions:
            self.c_action.addItem(a, a)
        self.c_params = QLineEdit()
        self.c_params.setPlaceholderText(tr("optional params: app=chrome, percent=50"))
        fl.addWidget(QLabel(tr("Phrase")), 0, 0)
        fl.addWidget(self.c_phrase, 0, 1)
        fl.addWidget(QLabel(tr("Action")), 1, 0)
        fl.addWidget(self.c_action, 1, 1)
        fl.addWidget(QLabel(tr("Params")), 2, 0)
        fl.addWidget(self.c_params, 2, 1)
        btns = QHBoxLayout()
        b_add = QPushButton(tr("Add"))
        b_del = QPushButton(tr("Remove"))
        b_add.clicked.connect(self._add_command)
        b_del.clicked.connect(self._delete_command)
        btns.addWidget(b_add)
        btns.addWidget(b_del)
        fl.addLayout(btns, 3, 1)
        row.addWidget(form, 2)
        lay.addLayout(row)
        return w

    # ---- macros ------------------------------------------------------------
    def reload_macros(self) -> None:
        self.macro_list.clear()
        for m in self.core.list_macros():
            self.macro_list.addItem(f"{'✓ ' if m.get('enabled') else '✗ '}{m['name']}"
                                    f"  ({m['trigger']}: {m['trigger_value']})")
        self.cmd_list.clear()
        for c in self.core.list_custom_commands():
            self.cmd_list.addItem(f"{c['phrase']}  →  {c['action']}")

    def _on_select(self, current, _prev) -> None:
        if current is None:
            return
        name = current.text()
        # strip the leading '✓ '/'✗ ' marker
        name = name[2:] if len(name) > 2 and name[1] == ' ' else name
        self._current = name
        m = self.core.macros.get(name)
        if m is None:
            return
        self.f_name.setText(m.name)
        idx = self.f_trigger.findData(m.trigger)
        if idx >= 0:
            self.f_trigger.setCurrentIndex(idx)
        self.f_trigger_value.setText(m.trigger_value)
        self.f_desc.setText(m.description)
        lines = []
        for step in m.actions:
            a = step.get("action", "")
            parts = [a] + [f"{k}={v}" for k, v in (step.get("params") or {}).items()]
            lines.append(" ".join(parts))
        self.f_actions.setPlainText("\n".join(lines))

    def _new_macro(self) -> None:
        self._current = ""
        for w in (self.f_name, self.f_trigger_value, self.f_desc):
            w.clear()
        self.f_actions.clear()
        self.f_trigger.setCurrentIndex(0)

    @staticmethod
    def _parse_actions(text: str) -> list[dict]:
        steps = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            action = tokens[0].upper()
            params = {}
            for tok in tokens[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    params[k.strip()] = _try_num(v.strip())
            steps.append({"action": action, "params": params})
        return steps

    def _save_macro(self) -> None:
        name = _empty(self.f_name.text())
        if not name:
            QMessageBox.warning(self, tr("Macro Studio"), tr("A macro needs a name."))
            return
        actions = self._parse_actions(self.f_actions.toPlainText())
        if not actions:
            QMessageBox.warning(
                self, tr("Macro Studio"),
                tr("Add at least one action line, e.g.  OPEN_APP app=chrome"))
            return
        data = {
            "name": name,
            "trigger": self.f_trigger.currentData(),
            "trigger_value": _empty(self.f_trigger_value.text()),
            "actions": actions,
            "description": _empty(self.f_desc.text()),
            "enabled": True,
        }
        if self.core.macros.get(name) is not None:
            err = self.core.update_macro(data)
        else:
            err = self.core.add_macro(data)
        if err:
            QMessageBox.warning(self, "Macro Studio", str(err))
            return
        self._current = name
        self.reload_macros()
        self._select_macro(name)

    def _select_macro(self, name: str) -> None:
        for i in range(self.macro_list.count()):
            item = self.macro_list.item(i)
            if item.text().endswith(name) or item.text() == f"✓ {name}":
                self.macro_list.setCurrentRow(i)
                break

    def _delete_macro(self) -> None:
        name = self._current
        if not name:
            return
        if self.core.delete_macro(name):
            self._current = ""
            self.reload_macros()

    def _run_macro(self) -> None:
        name = self._current
        if name:
            self.core.run_macro(name)

    # ---- custom commands ---------------------------------------------------
    def _add_command(self) -> None:
        phrase = _empty(self.c_phrase.text())
        action = self.c_action.currentData() or ""
        if not phrase or not action:
            QMessageBox.warning(
                self, tr("Custom Commands"), tr("Enter a phrase and pick an action."))
            return
        params = {}
        for tok in _empty(self.c_params.text()).replace(",", " ").split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                params[k.strip()] = _try_num(v.strip())
        err = self.core.add_custom_command({
            "phrase": phrase, "action": action, "params": params,
            "language": "*", "enabled": True,
        })
        if err:
            QMessageBox.warning(self, "Custom Commands", str(err))
            return
        self.c_phrase.clear()
        self.c_params.clear()
        self.reload_macros()

    def _delete_command(self) -> None:
        item = self.cmd_list.currentItem()
        if item is None:
            return
        phrase = item.text().split("  →  ")[0]
        self.core.delete_custom_command(phrase)
        self.reload_macros()


def _try_num(value: str):
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


class PlannerPreviewDialog(QDialog):
    """Shows an AI-proposed plan; the user executes or cancels."""

    def __init__(self, core, plan, parent=None):
        super().__init__(parent)
        self.core = core
        self.plan = plan
        self.setWindowTitle(tr("AI Planner suggestion"))
        self.setMinimumWidth(480)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("For: ") + (plan.request or "")))
        title = QLabel(plan.description or tr("Proposed actions"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffe08a;")
        lay.addWidget(title)
        self.list = QListWidget()
        for s in plan.steps:
            self.list.addItem(f"• {s.describe()}")
        lay.addWidget(self.list, 1)
        hint = QLabel(tr("Nothing runs yet — every step still passes the Safety Engine gates."))
        hint.setStyleSheet("color: #5f7ea0; font-size: 11px;")
        lay.addWidget(hint)
        row = QHBoxLayout()
        b_exec = QPushButton(tr("Execute plan"))
        b_exec.setObjectName("ok")
        b_cancel = QPushButton(tr("Cancel"))
        b_exec.clicked.connect(self._execute)
        b_cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(b_exec)
        row.addWidget(b_cancel)
        lay.addLayout(row)

    def _execute(self) -> None:
        self.core.execute_plan(self.plan)
        self.accept()


class TestLabDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle(tr("HADJ Test Lab"))
        self.resize(560, 520)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("Self-diagnostics (simulated inputs, no hardware needed)")))
        head.addStretch(1)
        self.btn_run = QPushButton(tr("Run all tests"))
        self.btn_run.clicked.connect(lambda: self.run())
        head.addWidget(self.btn_run)
        lay.addLayout(head)
        self.results = QListWidget()
        lay.addWidget(self.results, 1)
        self.summary = QLabel("")
        lay.addWidget(self.summary)

        live = QFrame()
        live.setStyleSheet("background:#0e1b2b; border:1px solid #223d5c; border-radius:8px;")
        ll = QVBoxLayout(live)
        ll.addWidget(QLabel("Live gesture accuracy (real measured counters from your session)"))
        self.live_stats = QLabel("—")
        self.live_stats.setWordWrap(True)
        ll.addWidget(self.live_stats)
        lrow = QHBoxLayout()
        b_refresh = QPushButton("Refresh")
        b_refresh.clicked.connect(self._refresh_live)
        b_reset = QPushButton("Reset counters")
        b_reset.clicked.connect(self._reset_live)
        lrow.addStretch(1)
        lrow.addWidget(b_refresh)
        lrow.addWidget(b_reset)
        ll.addLayout(lrow)
        lay.addWidget(live)

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._refresh_live()

    def _refresh_live(self) -> None:
        st = self.core.test_lab.live_stats()
        prec = st["click_precision"]
        clicks = st["clicks"]
        if prec is None:
            prec_txt = "n/a (no clicks yet)"
            clean_txt = "—"
        else:
            prec_txt = f"{prec:.0%} ({st['precision_label']})"
            clean_txt = f"{st['clicks_clean']}/{clicks}"
        self.live_stats.setText(
            f"Clicks delivered: <b>{clicks}</b>  ·  clean (≤12% drift): <b>{clean_txt}</b>\n"
            f"Click precision: <b>{prec_txt}</b>  ·  avg drift: "
            f"{st['click_drift_avg'] if st['click_drift_avg'] is not None else '—'}\n"
            f"False triggers: <b>{st['false_triggers']}</b>  ·  session FPS: {st['fps']:.0f}  ·  "
            f"gesture latency: {st['gesture_latency_ms'] if st['gesture_latency_ms'] is not None else '—'} ms")

    def _reset_live(self) -> None:
        self.core.reset_live_metrics()
        self._refresh_live()

    def run(self) -> None:
        self.results.clear()
        self.btn_run.setEnabled(False)
        rows = self.core.run_test_lab()
        for r in rows:
            ok = r.get("ok")
            mark = {"True": "🟢", "False": "🔴", "None": "⚪"}.get(str(ok), "?")
            detail = r.get("detail", "")
            self.results.addItem(f"{mark} {r.get('name')}: {detail}")
        passed = sum(1 for r in rows if r.get("ok") is True)
        skipped = sum(1 for r in rows if r.get("ok") is None)
        failed = sum(1 for r in rows if r.get("ok") is False)
        self.summary.setText(trf(
            "Passed {passed} · Skipped {skipped} · Failed {failed}",
            passed=passed, skipped=skipped, failed=failed))
        self.btn_run.setEnabled(True)
        self._refresh_live()


class SettingsCenterDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle(tr("Settings Center"))
        self.setMinimumWidth(420)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)

        g_safe = QGroupBox(tr("Safety"))
        sl = QVBoxLayout(g_safe)
        sl.addWidget(QLabel(tr("Confirmation level")))
        self.s_conf = QComboBox()
        self.s_conf.addItem(tr("None — run CONFIRM actions freely (CRITICAL still asks)"), "none")
        self.s_conf.addItem(tr("Smart — confirm sensitive actions"), "smart")
        self.s_conf.addItem(tr("All — confirm every action except emergency/safety toggles"), "all")
        idx = self.s_conf.findData(self.core.safety.confirmation_level)
        self.s_conf.setCurrentIndex(max(0, idx))
        sl.addWidget(self.s_conf)
        sl.addWidget(QLabel(tr("Demo mode blocks every real OS action and simulates it loudly.")))
        lay.addWidget(g_safe)

        g_voice = QGroupBox(tr("Voice recognition"))
        vl = QVBoxLayout(g_voice)
        rv = QHBoxLayout()
        rv.addWidget(QLabel(tr("Language")))
        self.v_lang = QComboBox()
        self.v_lang.addItem("English (en-US)", "en-US")
        self.v_lang.addItem("Français (fr-FR)", "fr-FR")
        self.v_lang.addItem("العربية (ar-SA)", "ar-SA")
        idx = self.v_lang.findData(self.core.settings.voice.language)
        self.v_lang.setCurrentIndex(max(0, idx))
        rv.addWidget(self.v_lang)
        rv.addStretch(1)
        vl.addLayout(rv)
        vl.addWidget(QLabel(tr(
            "Recognized commands switch language (open/next/volume… in EN, FR or AR). "
            "Applied on save — the voice engine restarts with the new language.")))
        lay.addWidget(g_voice)

        g_head = QGroupBox(tr("Head control (FaceMesh)"))
        hl = QVBoxLayout(g_head)
        self.h_enabled = QCheckBox(tr("Enable head-direction actions"))
        self.h_enabled.setChecked(self.core.settings.head.enabled)
        hl.addWidget(self.h_enabled)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Sensitivity")))
        self.h_sens = QDoubleSpinBox()
        self.h_sens.setRange(0.02, 0.6)
        self.h_sens.setSingleStep(0.01)
        self.h_sens.setValue(self.core.settings.head.sensitivity)
        r1.addWidget(self.h_sens)
        r1.addWidget(QLabel(tr("Hold (ms)")))
        self.h_hold = QSpinBox()
        self.h_hold.setRange(50, 2000)
        self.h_hold.setSingleStep(50)
        self.h_hold.setValue(self.core.settings.head.hold_ms)
        r1.addWidget(self.h_hold)
        r1.addWidget(QLabel(tr("Cooldown (ms)")))
        self.h_cool = QSpinBox()
        self.h_cool.setRange(200, 5000)
        self.h_cool.setSingleStep(100)
        self.h_cool.setValue(self.core.settings.head.cooldown_ms)
        r1.addWidget(self.h_cool)
        hl.addLayout(r1)
        hl.addWidget(QLabel(tr(
            "Turn left/right → previous/next (slide, page, track). Up/down → volume / "
            "zoom depending on context. Hold the direction, release to repeat.",)))
        lay.addWidget(g_head)

        g_gaze = QGroupBox(tr("Gaze tracking (experimental)"))
        gl = QVBoxLayout(g_gaze)
        self.g_enabled = QCheckBox(tr("Enable gaze estimation (optional)"))
        self.g_enabled.setChecked(self.core.settings.tracking.gaze_enabled)
        gl.addWidget(self.g_enabled)
        gl.addWidget(QLabel(tr(
            "Uses iris position (FaceMesh, local). Gaze confirms pinch/click on the "
            "thing you look at, and feeds the AI Copilot context.")))
        lay.addWidget(g_gaze)

        g_demo = QGroupBox(tr("Demo mode"))
        dl = QVBoxLayout(g_demo)
        self.d_start = QCheckBox(tr("Start the app in demo mode"))
        self.d_start.setChecked(self.core.settings.demo.start_in_demo)
        dl.addWidget(self.d_start)
        lay.addWidget(g_demo)

        g_voice = QGroupBox("Voice engine & privacy")
        vl = QVBoxLayout(g_voice)
        vl.addWidget(QLabel("Recognition engine"))
        self.v_engine = QComboBox()
        self.v_engine.addItem("Google — online recognition (works out of the box)", "google")
        self.v_engine.addItem("Vosk — fully local, audio stays on your device", "vosk")
        self.v_engine.addItem("SAPI — fully local (currently unavailable in this build)", "sapi")
        idx = self.v_engine.findData(self.core.settings.voice.engine)
        self.v_engine.setCurrentIndex(max(0, idx))
        vl.addWidget(self.v_engine)
        vl.addWidget(QLabel("Vosk model folder (only used when Vosk is selected)"))
        self.v_vosk_path = QLineEdit(self.core.settings.voice.vosk_model_path)
        self.v_vosk_path.setPlaceholderText("e.g. C:\\vosk-models\\vosk-model-en-us-0.22")
        vl.addWidget(self.v_vosk_path)
        vl.addWidget(QLabel(
            "Google sends mic audio to Google for recognition and needs internet; the "
            "badge in the header says AUDIO ONLINE while it is active. Vosk/SAPI never "
            "send audio anywhere — the badge says AUDIO LOCAL."))
        lay.addWidget(g_voice)

        g_sense = QGroupBox("Sensitivity profile")
        sl2 = QVBoxLayout(g_sense)
        sl2.addWidget(QLabel("Simple sensitivity dial (applies on top of the active mode)"))
        self.s_sense = QComboBox()
        self.s_sense.addItem("Low — slower, smoother, more forgiving", "low")
        self.s_sense.addItem("Medium — balanced", "medium")
        self.s_sense.addItem("High — fast, small gestures go far", "high")
        idx = self.s_sense.findData(self.core.settings.sensitivity)
        self.s_sense.setCurrentIndex(max(0, idx))
        sl2.addWidget(self.s_sense)
        lay.addWidget(g_sense)

        row = QHBoxLayout()
        b_save = QPushButton(tr("Save"))
        b_save.setObjectName("ok")
        b_close = QPushButton(tr("Close"))
        b_save.clicked.connect(self._save)
        b_close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(b_save)
        row.addWidget(b_close)
        lay.addLayout(row)

    def _save(self) -> None:
        conf = self.s_conf.currentData() or "smart"
        self.core.set_confirmation_level(conf)
        self.core.set_gaze_enabled(self.g_enabled.isChecked())
        s = self.core.settings
        new_lang = self.v_lang.currentData() or "en-US"
        if new_lang != s.voice.language:
            self.core.set_voice_language(new_lang)
        s.head.enabled = self.h_enabled.isChecked()
        s.head.sensitivity = self.h_sens.value()
        s.head.hold_ms = self.h_hold.value()
        s.head.cooldown_ms = self.h_cool.value()
        s.demo.start_in_demo = self.d_start.isChecked()
        self.core.head.sensitivity = self.h_sens.value()
        self.core.head.hold_ms = self.h_hold.value()
        self.core.head.cooldown_ms = self.h_cool.value()
        eng = self.v_engine.currentData() or "google"
        if s.voice.engine != eng:
            self.core.set_voice_engine(eng)
        s.voice.vosk_model_path = self.v_vosk_path.text().strip()
        self.core.set_sensitivity(self.s_sense.currentData() or "medium")
        try:
            s.save()
        except Exception:
            pass
        self.core._event("INFO", "Settings Center: settings saved")


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("HADJ NO-TOUCH AI — quick start"))
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        txt = QLabel(tr(
            "<b>Hands</b><br>"
            "☝️ POINT → move cursor<br>"
            "🤏 PINCH (thumb+index) → left click · hold + move → drag<br>"
            "✌️ Thumb + middle → right click · double pinch → double click<br>"
            "🖐 PALM + move vertically → scroll · swipe → next/previous<br>"
            "✊ FIST held → lock · PALM held → pause<br><br>"
            "<b>Voice</b> (EN / FR / AR)<br>"
            "'open chrome' · 'next page' · 'volume 50 percent'<br>"
            "'close this window' · 'take screenshot' · 'switch profile'\n\n"
            "<b>Safety</b><br>"
            "🔴 REAL mode acts on your computer; 🔵 DEMO simulates nothing.<br>"
            "Sensitive actions ask for confirmation first.<br>"
            "Emergency stop: <b>CTRL + ALT + H</b>"))
        txt.setTextFormat(Qt.TextFormat.RichText)
        txt.setWordWrap(True)
        lay.addWidget(txt)
        b = QPushButton(tr("Got it"))
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)