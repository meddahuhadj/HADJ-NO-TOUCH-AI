"""تحميل الإعدادات: الافتراضية + ملف المستخدم (يطغى عليها)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from config.schema import AppConfig
from core import paths

log = logging.getLogger(__name__)

USER_CONFIG = "config.yaml"
EDITION_FILE = "edition.yaml"   # بجانب التطبيق: يكتبه build.ps1 للنسخة الخفيفة (لغة افتراضية…)
USER_COMMANDS = "custom_commands.yaml"


def default_config_path() -> Path:
    return paths.resource_dir() / "config" / "default_config.yaml"


def default_commands_path() -> Path:
    return paths.resource_dir() / "config" / "default_commands.yaml"


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "app_aliases":
            out[k] = deep_merge(out[k], v)
        elif k == "app_aliases" and isinstance(v, dict):
            out[k] = {**out.get(k, {}), **v}
        else:
            out[k] = v
    return out


def read_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def edition_overrides() -> dict:
    """القيم الافتراضية الخاصة بالنسخة (بين الافتراضي العام وإعدادات المستخدم)."""
    try:
        data = read_yaml(paths.app_root() / EDITION_FILE) or {}
    except yaml.YAMLError as e:
        log.error("ملف النسخة غير صالح: %s", e)
        return {}
    return data.get("config") or {} if isinstance(data, dict) else {}


def load_config(user_dir: Path | None = None) -> AppConfig:
    data = deep_merge(read_yaml(default_config_path()) or {}, edition_overrides())
    user_path = (user_dir or paths.user_dir()) / USER_CONFIG
    try:
        user = read_yaml(user_path) or {}
        data = deep_merge(data, user)
    except yaml.YAMLError as e:
        log.error("ملف إعدادات المستخدم غير صالح (%s)، سيتم تجاهله: %s", user_path, e)
    return AppConfig.model_validate(data)


def update_user_config(changes: dict, user_dir: Path | None = None) -> Path:
    """يدمج التغييرات في ملف المستخدم فقط (لا ينسخ كل القيم الافتراضية إليه)."""
    path = (user_dir or paths.user_dir()) / USER_CONFIG
    try:
        current = read_yaml(path) or {}
    except yaml.YAMLError:
        current = {}
    merged = deep_merge(current, changes)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
    return path


def load_command_specs(user_dir: Path | None = None) -> list[dict]:
    """الأوامر الافتراضية ثم المخصصة (المخصصة بنفس المعرّف id تستبدل الافتراضية)."""
    default = (read_yaml(default_commands_path()) or {}).get("commands", [])
    user_path = (user_dir or paths.user_dir()) / USER_COMMANDS
    try:
        custom = (read_yaml(user_path) or {}).get("commands", [])
    except yaml.YAMLError as e:
        log.error("ملف الأوامر المخصصة غير صالح (%s): %s", user_path, e)
        custom = []
    by_id: dict[str, dict] = {}
    for i, spec in enumerate([*default, *custom]):
        by_id[spec.get("id") or f"custom_{i}"] = spec
    return list(by_id.values())
