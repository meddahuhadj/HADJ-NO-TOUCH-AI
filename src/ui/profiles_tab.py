"""تبويب الملفات الشخصية في نافذة الإعدادات: تفعيل، نسخ، استيراد، تصدير، حذف، وتعديل الإيماءات.

التغييرات هنا تُطبَّق فوراً عبر المتحكم (لا تنتظر زر "حفظ" الإعدادات العامة).
الملفات المدمجة للقراءة فقط: انسخها لتعديلها.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from config import profiles as prof
from ui.i18n import Tr
from ui.theme import Theme


class ProfilesApi(Protocol):
    profiles: dict
    profile: "prof.Profile"
    config: object
    def set_profile(self, pid: str) -> bool: ...
    def import_profile(self, path) -> tuple: ...
    def export_profile(self, pid: str, dest) -> None: ...
    def duplicate_profile(self, pid: str, name: str): ...
    def delete_profile(self, pid: str) -> None: ...
    def save_profile_bindings(self, pid: str, bindings: dict) -> list[str]: ...


class ProfilesTab(QWidget):
    def __init__(self, tr: Tr, th: Theme, api: ProfilesApi, gesture_actions: list[str],
                 combo_factory, parent: QWidget | None = None):
        super().__init__(parent)
        self.t, self.th, self.api = tr, th, api
        self.lang = tr.lang
        self.gesture_actions = gesture_actions
        self._combo = combo_factory
        self.combos: dict[str, object] = {}
        t = th

        self.list = QListWidget()
        self.list.setMinimumWidth(t.px(190))
        self.list.currentItemChanged.connect(lambda *_: self._show_selected())

        self.title = QLabel()
        self.title.setStyleSheet(f"font-size: {t.pt(14)}pt; font-weight: 700; background: transparent;")
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet(f"color: {t.c('text_dim')}; background: transparent;")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("background: transparent;")

        self.editor = QWidget()
        self.form = QFormLayout(self.editor)
        self.form.setVerticalSpacing(t.px(8))
        self.btn_save = self._button("prof_save", self._save_bindings, primary=True)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setStyleSheet("background: transparent;")
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(t.px(8))
        for w in (self.title, self.desc, self.summary, self.editor, self.btn_save):
            dl.addWidget(w)
        dl.addStretch(1)
        area.setWidget(detail)

        self.btn_activate = self._button("prof_activate", self._activate, primary=True)
        self.btn_duplicate = self._button("prof_duplicate", self._duplicate)
        self.btn_import = self._button("prof_import", self._import)
        self.btn_export = self._button("prof_export", self._export)
        self.btn_delete = self._button("prof_delete", self._delete)
        buttons = QHBoxLayout()
        for b in (self.btn_activate, self.btn_duplicate, self.btn_import, self.btn_export, self.btn_delete):
            buttons.addWidget(b)

        top = QHBoxLayout()
        top.addWidget(self.list, 1)
        top.addWidget(area, 2)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(t.px(6), t.px(6), t.px(6), t.px(6))
        lay.addLayout(top, 1)
        lay.addWidget(self.status)
        lay.addLayout(buttons)
        self.refresh()

    def _button(self, key: str, slot, primary: bool = False) -> QPushButton:
        b = QPushButton(self.t(key))
        b.setObjectName("primaryButton" if primary else "ghostButton")
        b.clicked.connect(slot)
        return b

    # ---------------- العرض ----------------
    def selected(self) -> "prof.Profile | None":
        item = self.list.currentItem()
        return self.api.profiles.get(item.data(Qt.UserRole)) if item else None

    def refresh(self, select: str | None = None) -> None:
        select = select or (self.selected().id if self.selected() else self.api.profile.id)
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.api.profiles.values():
            mark = "● " if p.id == self.api.profile.id else ""
            lock = " 🔒" if p.builtin else ""
            item = QListWidgetItem(f"{mark}{p.label(self.lang)}{lock}")
            item.setData(Qt.UserRole, p.id)
            self.list.addItem(item)
            if p.id == select:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._show_selected()

    def _action_label(self, action: str, p: "prof.Profile") -> str:
        if action.startswith(prof.CMD_PREFIX):
            cid = action[len(prof.CMD_PREFIX):]
            spec = next((c for c in p.commands if c["id"] == cid), None) or \
                next((c for c in getattr(self.api, "base_specs", []) if c.get("id") == cid), None)
            phrases = (spec or {}).get("phrases", {})
            words = phrases.get(self.lang) or phrases.get("en") or [cid]
            return f"🗣 « {words[0]} »"
        return self.t(f"act_{action}")

    def _show_selected(self) -> None:
        p = self.selected()
        while self.form.rowCount():
            self.form.removeRow(0)
        self.combos.clear()
        if p is None:
            return
        active = p.id == self.api.profile.id
        self.title.setText(p.label(self.lang) + (f"  · {self.t('prof_active')}" if active else ""))
        self.desc.setText(p.description.get(self.lang, ""))
        self.summary.setText(self.t("prof_summary", g=len(p.bindings), c=len(p.commands))
                             + ("\n" + self.t("prof_builtin_note") if p.builtin and p.id != prof.STANDARD else ""))
        self.btn_activate.setEnabled(not active)
        self.btn_delete.setEnabled(not p.builtin)
        self.btn_export.setEnabled(p.id != prof.STANDARD)
        self.btn_save.setVisible(not p.builtin)

        lock = QLabel(self.t("prof_locked_fist"))
        lock.setStyleSheet(f"color: {self.th.c('warn')}; background: transparent; font-weight: 600;")
        self.form.addRow(lock)
        inherit = [("", self.t("prof_inherit"))]
        actions = [(a, self.t(f"act_{a}")) for a in self.gesture_actions if a != "app.pause"]
        refs = [f"{prof.CMD_PREFIX}{c['id']}" for c in p.commands if not c.get("dangerous")]
        # أوامر أساسية مربوطة مسبقاً (مثل cmd:page_down في المطبخ) تبقى قابلة للاختيار بعنوان مقروء
        refs += [a for a in p.bindings.values() if a.startswith(prof.CMD_PREFIX) and a not in refs]
        cmds = [(ref, self._action_label(ref, p)) for ref in refs]
        for g in prof.GESTURES:
            if g in prof.PROTECTED_BINDINGS:
                continue
            current = p.bindings.get(g, "")
            if p.builtin:
                text = self._action_label(current, p) if current else self.t("prof_inherit")
                value = QLabel(text)
                value.setStyleSheet("background: transparent;")
                self.form.addRow(self.t(f"g_{g}"), value)
            else:
                combo = self._combo(inherit + actions + cmds, current)
                self.combos[g] = combo
                self.form.addRow(self.t(f"g_{g}"), combo)

    def _say(self, text: str, ok: bool = True) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {self.th.c('ok' if ok else 'err')}; background: transparent;")

    def _error(self, e: Exception) -> None:
        key = getattr(e, "key", "")
        self._say(self.t(key, detail=getattr(e, "detail", "")) if key else self.t("prof_error", detail=str(e)),
                  ok=False)

    # ---------------- الإجراءات ----------------
    def _activate(self) -> None:
        p = self.selected()
        if p and self.api.set_profile(p.id):
            self.refresh(p.id)
            self._say(self.t("profile_switched", name=p.label(self.lang)))

    def _duplicate(self) -> None:
        p = self.selected()
        if p is None:
            return
        name, ok = QInputDialog.getText(self, self.t("prof_duplicate"), self.t("prof_duplicate_prompt"),
                                        text=f"{p.label(self.lang)} 2")
        if not ok or not name.strip():
            return
        try:
            new = self.api.duplicate_profile(p.id, name.strip())
        except (prof.ProfileError, OSError) as e:
            self._error(e)
            return
        self.refresh(new.id)
        self._say(self.t("prof_saved"))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.t("prof_import"), str(Path.home()),
                                              f"{self.t('prof_file_filter')} (*{prof.SUFFIX} *.yaml *.yml)")
        if path:
            self.import_path(Path(path))

    def import_path(self, path: Path) -> None:
        try:
            p, warnings = self.api.import_profile(path)
        except (prof.ProfileError, OSError) as e:
            self._error(e)
            return
        self.refresh(p.id)
        msg = self.t("prof_imported", name=p.label(self.lang))
        if warnings:
            msg += "\n" + self.t("prof_import_warn", n=len(warnings))
        self._say(msg, ok=not warnings)

    def _export(self) -> None:
        p = self.selected()
        if p is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, self.t("prof_export"),
                                              str(Path.home() / f"{p.id}{prof.SUFFIX}"),
                                              f"{self.t('prof_file_filter')} (*{prof.SUFFIX})")
        if not path:
            return
        try:
            self.api.export_profile(p.id, Path(path))
        except OSError as e:
            self._error(e)
            return
        self._say(self.t("prof_exported", path=path))

    def _delete(self) -> None:
        p = self.selected()
        if p is None or p.builtin:
            return
        if QMessageBox.question(self, self.t("prof_delete"),
                                self.t("prof_delete_confirm", name=p.label(self.lang))) != QMessageBox.Yes:
            return
        try:
            self.api.delete_profile(p.id)
        except (prof.ProfileError, OSError) as e:
            self._error(e)
            return
        self.refresh(self.api.profile.id)
        self._say(self.t("prof_deleted"))

    def collect_bindings(self) -> dict[str, str]:
        return {g: c.currentData() or "" for g, c in self.combos.items()}

    def _save_bindings(self) -> None:
        p = self.selected()
        if p is None or p.builtin:
            return
        try:
            warnings = self.api.save_profile_bindings(p.id, self.collect_bindings())
        except (prof.ProfileError, OSError) as e:
            self._error(e)
            return
        self.refresh(p.id)
        self._say(self.t("prof_saved") + ("\n" + self.t("prof_import_warn", n=len(warnings)) if warnings else ""),
                  ok=not warnings)
