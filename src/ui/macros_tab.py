"""تبويب الماكرو: عبارة و/أو إيماءة ← خطوات (مفاتيح، نص، انتظار، نقر، تمرير)، بلا تعديل ملفات.

المفاتيح تُختار بخانات (Ctrl/Alt/Shift/Win) وقائمة مفاتيح لا بالضغط على لوحة المفاتيح:
من يتحكم بالإيماءات أو بالشبكة الصوتية يستطيع إنشاء ماكرو كاملاً دون لمس لوحة المفاتيح.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from config import macros as mac
from config.profiles import GESTURES, PROTECTED_BINDINGS
from ui.i18n import Tr
from ui.theme import Theme

KEY_LABELS = {"escape": "Esc", "pageup": "Page ↑", "pagedown": "Page ↓", "up": "↑", "down": "↓",
              "left": "←", "right": "→", "printscreen": "PrtSc", "plus": "+", "minus": "-",
              "comma": ",", "period": ".", "apps": "Menu", "backspace": "⌫", "delete": "Del"}


def key_label(k: str) -> str:
    return KEY_LABELS.get(k, k.upper() if len(k) <= 3 else k.capitalize())


class MacrosTab(QWidget):
    def __init__(self, tr: Tr, th: Theme, api, combo_factory, parent: QWidget | None = None):
        super().__init__(parent)
        self.t, self.th, self.api = tr, th, api
        self._combo = combo_factory
        self.current: dict = {}
        self._loading = False
        t = th

        # ---- القائمة ----
        self.list = QListWidget()
        self.list.setMinimumWidth(t.px(180))
        self.list.currentItemChanged.connect(lambda *_: self._load_selected())
        btn_new = self._button("macro_new", self.new_macro, primary=True)
        self.btn_delete = self._button("macro_delete", self._delete)
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(btn_new)
        row.addWidget(self.btn_delete)
        left.addLayout(row)

        # ---- المحرر ----
        form = QFormLayout()
        form.setVerticalSpacing(t.px(8))
        self.phrase = {}
        for lang, name in (("fr", "Français"), ("ar", "العربية"), ("en", "English")):
            e = QLineEdit()
            e.setLayoutDirection(Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
            e.textChanged.connect(self._sync)
            self.phrase[lang] = e
            form.addRow(self.t("macro_phrase", lang=name), e)
        gestures = [("", self.t("macro_no_gesture"))] + [
            (g, self.t(f"g_{g}")) for g in GESTURES if g not in PROTECTED_BINDINGS]
        self.gesture = self._combo(gestures, "")
        self.gesture.currentIndexChanged.connect(self._sync)
        form.addRow(self.t("macro_gesture"), self.gesture)

        self.steps = QListWidget()
        self.steps.setMinimumHeight(t.px(120))
        self.steps.currentRowChanged.connect(self._show_step)
        add_keys = self._button("macro_add_keys", lambda: self._add({"kind": "keys", "keys": "ctrl+c"}))
        add_text = self._button("macro_add_text", lambda: self._add({"kind": "text", "text": ""}))
        add_wait = self._button("macro_add_wait", lambda: self._add({"kind": "wait", "ms": 300}))
        add_mouse = self._button("macro_add_mouse", None)
        menu = QMenu(add_mouse)
        for kind in ("click", "double_click", "right_click", "scroll_up", "scroll_down"):
            menu.addAction(self.t(f"macro_step_{kind}"), lambda k=kind: self._add({"kind": k}))
        add_mouse.setMenu(menu)
        up = self._button("macro_up", lambda: self._move(-1))
        down = self._button("macro_down", lambda: self._move(1))
        remove = self._button("macro_remove_step", self._remove_step)
        adds = QHBoxLayout()
        for b in (add_keys, add_text, add_wait, add_mouse):
            adds.addWidget(b)
        moves = QHBoxLayout()
        for b in (up, down, remove):
            moves.addWidget(b)

        # محرر الخطوة المحددة
        self.stack = QStackedWidget()
        self.mods = {m: QCheckBox(m.capitalize() if m != "win" else "Win") for m in mac.MODIFIERS}
        self.key = self._combo([(k, key_label(k)) for k in mac.KEYS], "c")
        keys_page = QWidget()
        kl = QHBoxLayout(keys_page)
        kl.setContentsMargins(0, 0, 0, 0)
        for m in mac.MODIFIERS:
            self.mods[m].toggled.connect(self._edit_step)
            kl.addWidget(self.mods[m])
        kl.addWidget(QLabel("+"))
        kl.addWidget(self.key, 1)
        self.key.currentIndexChanged.connect(self._edit_step)
        self.text = QLineEdit()
        self.text.setMaxLength(mac.MAX_TEXT)
        self.text.setPlaceholderText(self.t("macro_text_hint"))
        self.text.textChanged.connect(self._edit_step)
        self.wait = QSpinBox()
        self.wait.setRange(50, mac.MAX_WAIT_MS)
        self.wait.setSingleStep(100)
        self.wait.setSuffix(" ms")
        self.wait.valueChanged.connect(self._edit_step)
        none = QLabel(self.t("macro_no_setting"))
        none.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;")
        for w in (keys_page, self.text, self.wait, none):
            self.stack.addWidget(w)

        self.confirm = QCheckBox(self.t("macro_confirm"))
        self.confirm.toggled.connect(self._sync)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet(f"color: {t.c('warn')}; background: transparent; font-weight: 600;")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("background: transparent;")
        self.btn_save = self._button("macro_save", self._save, primary=True)
        note = QLabel(self.t("macro_note"))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;")

        right = QVBoxLayout()
        right.addLayout(form)
        right.addWidget(QLabel(self.t("macro_steps")))
        right.addWidget(self.steps, 1)
        right.addLayout(adds)
        right.addLayout(moves)
        right.addWidget(self.stack)
        right.addWidget(self.confirm)
        right.addWidget(self.warn)
        right.addWidget(self.btn_save)
        right.addWidget(self.status)
        right.addWidget(note)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(t.px(6), t.px(6), t.px(6), t.px(6))
        lay.addLayout(left, 1)
        lay.addLayout(right, 2)
        self.refresh()

    def _button(self, key: str, slot, primary: bool = False) -> QPushButton:
        b = QPushButton(self.t(key))
        b.setObjectName("primaryButton" if primary else "ghostButton")
        if slot is not None:
            b.clicked.connect(slot)
        return b

    # ---------------- القائمة ----------------
    def _title(self, m: dict) -> str:
        ph = m.get("phrases", {})
        words = ph.get(self.t.lang) or next(iter(ph.values()), None)
        text = f"« {words[0]} »" if words else self.t(f"g_{m.get('gesture', '')}")
        return ("⚠ " if m.get("dangerous") else "") + text + (" ✋" if m.get("gesture") else "")

    def refresh(self, select: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for m in self.api.macros:
            item = QListWidgetItem(self._title(m))
            item.setData(Qt.UserRole, m["id"])
            self.list.addItem(item)
            if m["id"] == select:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if select is None and self.list.count():
            self.list.setCurrentRow(0)
        if self.list.currentItem() is None:
            self.new_macro()
        else:
            self._load_selected()

    def _load_selected(self) -> None:
        item = self.list.currentItem()
        m = next((x for x in self.api.macros if item and x["id"] == item.data(Qt.UserRole)), None)
        if m is None:
            return
        self._load({"id": m["id"], "phrases": {k: v[0] for k, v in m.get("phrases", {}).items() if v},
                    "steps": [mac.action_to_step(s) for s in m["steps"]],
                    "dangerous": bool(m.get("dangerous")), "gesture": m.get("gesture", "")})

    def new_macro(self) -> None:
        self.list.blockSignals(True)
        self.list.clearSelection()
        self.list.setCurrentItem(None)
        self.list.blockSignals(False)
        self._load({"id": "", "phrases": {}, "steps": [], "dangerous": False, "gesture": ""})

    def _load(self, data: dict) -> None:
        self._loading = True
        self.current = data
        for lang, e in self.phrase.items():
            e.setText(data["phrases"].get(lang, ""))
        self.gesture.setCurrentIndex(max(0, self.gesture.findData(data.get("gesture", ""))))
        self.confirm.setChecked(data.get("dangerous", False))
        self.btn_delete.setEnabled(bool(data.get("id")))
        self._loading = False
        self._render_steps(0)
        self.status.setText("")

    # ---------------- الخطوات ----------------
    def step_text(self, s: dict) -> str:
        kind = s["kind"]
        if kind == "keys":
            return "⌨ " + " + ".join(key_label(k) if k not in mac.MODIFIERS else k.capitalize()
                                     for k in str(s.get("keys", "")).split("+") if k)
        if kind == "text":
            return f"✎ « {s.get('text', '')} »"
        if kind == "wait":
            return f"⏱ {s.get('ms', 300)} ms"
        return "🖱 " + self.t(f"macro_step_{kind}")

    def _render_steps(self, select: int | None = None) -> None:
        self.steps.blockSignals(True)
        self.steps.clear()
        for i, s in enumerate(self.current["steps"]):
            self.steps.addItem(f"{i + 1}. {self.step_text(s)}")
        self.steps.blockSignals(False)
        if self.current["steps"]:
            self.steps.setCurrentRow(min(select or 0, len(self.current["steps"]) - 1))
        else:
            self.stack.setCurrentIndex(3)
        self._sync()

    def _add(self, step: dict) -> None:
        if len(self.current["steps"]) >= mac.MAX_STEPS:
            self._say(self.t("macro_too_many", n=mac.MAX_STEPS), ok=False)
            return
        self.current["steps"].append(step)
        self._render_steps(len(self.current["steps"]) - 1)

    def _move(self, delta: int) -> None:
        i = self.steps.currentRow()
        j = i + delta
        steps = self.current["steps"]
        if 0 <= i < len(steps) and 0 <= j < len(steps):
            steps[i], steps[j] = steps[j], steps[i]
            self._render_steps(j)

    def _remove_step(self) -> None:
        i = self.steps.currentRow()
        if 0 <= i < len(self.current["steps"]):
            del self.current["steps"][i]
            self._render_steps(max(0, i - 1))

    def _show_step(self, row: int) -> None:
        if not 0 <= row < len(self.current.get("steps", [])):
            return
        s = self.current["steps"][row]
        self._loading = True
        if s["kind"] == "keys":
            keys = str(s.get("keys", "")).split("+")
            for m, box in self.mods.items():
                box.setChecked(m in keys[:-1])
            self.key.setCurrentIndex(max(0, self.key.findData(keys[-1])))
            self.stack.setCurrentIndex(0)
        elif s["kind"] == "text":
            self.text.setText(s.get("text", ""))
            self.stack.setCurrentIndex(1)
        elif s["kind"] == "wait":
            self.wait.setValue(int(s.get("ms", 300)))
            self.stack.setCurrentIndex(2)
        else:
            self.stack.setCurrentIndex(3)
        self._loading = False

    def _edit_step(self, *_):
        if self._loading:
            return
        row = self.steps.currentRow()
        if not 0 <= row < len(self.current["steps"]):
            return
        s = self.current["steps"][row]
        if s["kind"] == "keys":
            mods = [m for m in mac.MODIFIERS if self.mods[m].isChecked()]
            s["keys"] = "+".join([*mods, self.key.currentData()])
        elif s["kind"] == "text":
            s["text"] = self.text.text()
        elif s["kind"] == "wait":
            s["ms"] = self.wait.value()
        self.steps.item(row).setText(f"{row + 1}. {self.step_text(s)}")
        self._sync()

    # ---------------- الأمان المباشر ----------------
    def destructive(self) -> bool:
        try:
            return mac.is_destructive([mac.step_to_action(s) for s in self.current.get("steps", [])
                                       if s["kind"] == "keys"])
        except mac.MacroError:
            return False

    def _sync(self, *_):
        """التأكيد إجباري للاختصارات المدمّرة، والماكرو المؤكَّد لا يُربط بإيماءة."""
        if self._loading or not self.current:
            return
        forced = self.destructive()
        self.confirm.blockSignals(True)
        if forced:
            self.confirm.setChecked(True)
        self.confirm.setEnabled(not forced)
        self.confirm.blockSignals(False)
        dangerous = self.confirm.isChecked()
        self.gesture.setEnabled(not dangerous)
        if dangerous and self.gesture.currentData():
            self.gesture.setCurrentIndex(0)
        msgs = []
        if forced:
            msgs.append(self.t("macro_forced_confirm"))
        if dangerous:
            msgs.append(self.t("macro_no_gesture_when_confirm"))
        self.warn.setText("\n".join(msgs))
        self.warn.setVisible(bool(msgs))

    # ---------------- الحفظ ----------------
    def collect(self) -> dict:
        return {"id": self.current.get("id", ""),
                "phrases": {lang: e.text().strip() for lang, e in self.phrase.items() if e.text().strip()},
                "steps": [dict(s) for s in self.current.get("steps", [])],
                "dangerous": self.confirm.isChecked(),
                "gesture": self.gesture.currentData() or ""}

    def _say(self, text: str, ok: bool = True) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {self.th.c('ok' if ok else 'err')}; background: transparent;")

    def _save(self) -> None:
        try:
            spec = self.api.save_macro(self.collect())
        except mac.MacroError as e:
            self._say(self.t(e.key, **e.values), ok=False)
            return
        self.refresh(spec["id"])
        self._say(self.t("macro_saved"))

    def _delete(self) -> None:
        mid = self.current.get("id")
        if mid:
            self.api.delete_macro(mid)
            self.refresh()
            self._say(self.t("macro_deleted"))
