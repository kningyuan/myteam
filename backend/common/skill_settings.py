"""读取 config/skill_config.json 中的协作引擎开关。"""

from __future__ import annotations

import json
from functools import lru_cache

from common.paths import CONFIG_DIR


def _skill_config_path():
    return CONFIG_DIR / "skill_config.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    path = _skill_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def reload_skill_settings():
    _load.cache_clear()


def section_int(section: str, key: str, default: int) -> int:
    try:
        val = _load().get(section, {}).get(key, default)
        return int(val)
    except (TypeError, ValueError):
        return default


def is_telegram_enabled() -> bool:
    return bool(_load().get("notifications", {}).get("enable_telegram", False))


def is_project_group_enabled() -> bool:
    return bool(_load().get("notifications", {}).get("use_project_group", True))


def is_auto_group_enabled() -> bool:
    return bool(_load().get("auto_group", {}).get("enabled", True))


def process_defaults() -> dict:
    """skill_config.json → process_defaults（与 Hub 启动 kernel 同源）。"""
    raw = _load().get("process_defaults")
    return dict(raw) if isinstance(raw, dict) else {}


def skill_config_all() -> dict:
    return dict(_load())
