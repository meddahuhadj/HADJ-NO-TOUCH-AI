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


def _empty(text: str) -> str:
    return (text or "").strip()


class MacroStudioDialog(QDialog):
    """Create / edit / delete macros and custom voice commands."""

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Macro Studio & Custom Commands")
        self.resize(720, 520)
        self.setStyleSheet(DARK)
        self._current = ""
        self._build()
        self.reload_macros()

    # ---- construction ------------------------------------------------------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_macros(), "Macros (voice / gesture / button)")
        tabs.addTab(self._build_commands(), "Custom voice commands")
        lay.addWidget(tabs, 1)
        close = QPushButton("Close")
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
        self.f_trigger.addItem("Voice phrase", "voice")
        self.f_trigger.addItem("Gesture", "gesture")
        self.f_trigger.addItem("Button", "button")
        self.f_trigger_value = QLineEdit()
        self.f_trigger_value.setPlaceholderText("e.g. 'go to work' / CIRCLE_CW / quick_action")
        self.f_actions = QTextEdit()
        self.f_actions.setPlaceholderText(
            "One registered action per line, optional key=value params.\n"
            "Examples:\n"
            "  OPEN_APP app=chrome\n  PROFILE_SWITCH profile=developer\n  VOLUME_SET percent=50")
        self.f_desc = QLineEdit()
        self.f_desc.setPlaceholderText("optional description")
        fl.addWidget(QLabel("Name"), 0, 0)
        fl.addWidget(self.f_name, 0, 1)
        fl.addWidget(QLabel("Trigger"), 1, 0)
        fl.addWidget(self.f_trigger, 1, 1)
        fl.addWidget(QLabel("Value"), 2, 0)
        fl.addWidget(self.f_trigger_value, 2, 1)
        fl.addWidget(QLabel("Actions"), 3, 0, alignment=Qt.AlignmentFlag.AlignTop)
        fl.addWidget(self.f_actions, 3, 1)
        fl.addWidget(QLabel("Description"), 4, 0)
        fl.addWidget(self.f_desc, 4, 1)
        btns = QHBoxLayout()
        b_new = QPushButton("New")
        b_save = QPushButton("Save")
        b_del = QPushButton("Delete")
        b_run = QPushButton("Run now")
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
        self.c_phrase.setPlaceholderText("phrase, e.g. 'boost volume'")
        self.c_action = QComboBox()
        reg = self.core.safety.registry if hasattr(self.core, "safety") else None
        actions = sorted(reg.ids()) if reg else []
        for a in actions:
            self.c_action.addItem(a, a)
        self.c_params = QLineEdit()
        self.c_params.setPlaceholderText("optional params: app=chrome, percent=50")
        fl.addWidget(QLabel("Phrase"), 0, 0)
        fl.addWidget(self.c_phrase, 0, 1)
        fl.addWidget(QLabel("Action"), 1, 0)
        fl.addWidget(self.c_action, 1, 1)
        fl.addWidget(QLabel("Params"), 2, 0)
        fl.addWidget(self.c_params, 2, 1)
        btns = QHBoxLayout()
        b_add = QPushButton("Add")
        b_del = QPushButton("Remove")
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
            QMessageBox.warning(self, "Macro Studio", "A macro needs a name.")
            return
        actions = self._parse_actions(self.f_actions.toPlainText())
        if not actions:
            QMessageBox.warning(self, "Macro Studio",
                                "Add at least one action line, e.g.  OPEN_APP app=chrome")
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
            QMessageBox.warning(self, "Custom Commands", "Enter a phrase and pick an action.")
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
        self.setWindowTitle("AI Planner suggestion")
        self.setMinimumWidth(480)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("For: " + (plan.request or "")))
        title = QLabel(plan.description or "Proposed actions")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffe08a;")
        lay.addWidget(title)
        self.list = QListWidget()
        for s in plan.steps:
            self.list.addItem(f"• {s.describe()}")
        lay.addWidget(self.list, 1)
        hint = QLabel("Nothing runs yet — every step still passes the Safety Engine gates.")
        hint.setStyleSheet("color: #5f7ea0; font-size: 11px;")
        lay.addWidget(hint)
        row = QHBoxLayout()
        b_exec = QPushButton("Execute plan")
        b_exec.setObjectName("ok")
        b_cancel = QPushButton("Cancel")
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
        self.setWindowTitle("HADJ Test Lab")
        self.resize(560, 480)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(QLabel("Self-diagnostics (simulated inputs, no hardware needed)"))
        head.addStretch(1)
        self.btn_run = QPushButton("Run all tests")
        self.btn_run.clicked.connect(lambda: self.run())
        head.addWidget(self.btn_run)
        lay.addLayout(head)
        self.results = QListWidget()
        lay.addWidget(self.results, 1)
        self.summary = QLabel("")
        lay.addWidget(self.summary)

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
        self.summary.setText(f"Passed {passed} · Skipped {skipped} · Failed {failed}")
        self.btn_run.setEnabled(True)


class SettingsCenterDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Settings Center")
        self.setMinimumWidth(420)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)

        g_safe = QGroupBox("Safety")
        sl = QVBoxLayout(g_safe)
        sl.addWidget(QLabel("Confirmation level"))
        self.s_conf = QComboBox()
        self.s_conf.addItem("None — run CONFIRM actions freely (CRITICAL still asks)", "none")
        self.s_conf.addItem("Smart — confirm sensitive actions", "smart")
        self.s_conf.addItem("All — confirm every action except emergency/safety toggles", "all")
        idx = self.s_conf.findData(self.core.safety.confirmation_level)
        self.s_conf.setCurrentIndex(max(0, idx))
        sl.addWidget(self.s_conf)
        sl.addWidget(QLabel("Demo mode blocks every real OS action and simulates it loudly."))
        lay.addWidget(g_safe)

        g_head = QGroupBox("Head control (FaceMesh)")
        hl = QVBoxLayout(g_head)
        self.h_enabled = QCheckBox("Enable head-direction actions")
        self.h_enabled.setChecked(self.core.settings.head.enabled)
        hl.addWidget(self.h_enabled)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Sensitivity"))
        self.h_sens = QDoubleSpinBox()
        self.h_sens.setRange(0.02, 0.6)
        self.h_sens.setSingleStep(0.01)
        self.h_sens.setValue(self.core.settings.head.sensitivity)
        r1.addWidget(self.h_sens)
        r1.addWidget(QLabel("Hold (ms)"))
        self.h_hold = QSpinBox()
        self.h_hold.setRange(50, 2000)
        self.h_hold.setSingleStep(50)
        self.h_hold.setValue(self.core.settings.head.hold_ms)
        r1.addWidget(self.h_hold)
        r1.addWidget(QLabel("Cooldown (ms)"))
        self.h_cool = QSpinBox()
        self.h_cool.setRange(200, 5000)
        self.h_cool.setSingleStep(100)
        self.h_cool.setValue(self.core.settings.head.cooldown_ms)
        r1.addWidget(self.h_cool)
        hl.addLayout(r1)
        hl.addWidget(QLabel(
            "Turn left/right → previous/next (slide, page, track). Up/down → volume / "
            "zoom depending on context. Hold the direction, release to repeat.",))
        lay.addWidget(g_head)

        g_demo = QGroupBox("Demo mode")
        dl = QVBoxLayout(g_demo)
        self.d_start = QCheckBox("Start the app in demo mode")
        self.d_start.setChecked(self.core.settings.demo.start_in_demo)
        dl.addWidget(self.d_start)
        lay.addWidget(g_demo)

        row = QHBoxLayout()
        b_save = QPushButton("Save")
        b_save.setObjectName("ok")
        b_close = QPushButton("Close")
        b_save.clicked.connect(self._save)
        b_close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(b_save)
        row.addWidget(b_close)
        lay.addLayout(row)

    def _save(self) -> None:
        conf = self.s_conf.currentData() or "smart"
        self.core.set_confirmation_level(conf)
        s = self.core.settings
        s.head.enabled = self.h_enabled.isChecked()
        s.head.sensitivity = self.h_sens.value()
        s.head.hold_ms = self.h_hold.value()
        s.head.cooldown_ms = self.h_cool.value()
        s.demo.start_in_demo = self.d_start.isChecked()
        self.core.head.sensitivity = self.h_sens.value()
        self.core.head.hold_ms = self.h_hold.value()
        self.core.head.cooldown_ms = self.h_cool.value()
        try:
            s.save()
        except Exception:
            pass
        self.core._event("INFO", "Settings Center: settings saved")


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HADJ NO-TOUCH AI — quick start")
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK)
        lay = QVBoxLayout(self)
        txt = QLabel(
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
            "Emergency stop: <b>CTRL + ALT + H</b>")
        txt.setTextFormat(Qt.TextFormat.RichText)
        txt.setWordWrap(True)
        lay.addWidget(txt)
        b = QPushButton("Got it")
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)