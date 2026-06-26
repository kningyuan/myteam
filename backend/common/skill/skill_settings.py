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


def _agent_memory() -> dict:
    raw = _load().get("agent_memory")
    return dict(raw) if isinstance(raw, dict) else {}


def agent_memory_backend(default: str = "native") -> str:
    return str(_agent_memory().get("backend") or default).strip() or default


def agent_memory_enabled(default: bool = True) -> bool:
    raw = _agent_memory().get("enabled", default)
    return bool(raw)


def _memstack() -> dict:
    raw = _load().get("memstack")
    if isinstance(raw, dict):
        return dict(raw)
    raw = _load().get("memory")
    return dict(raw) if isinstance(raw, dict) else {}


def memstack_enabled(default: bool = False) -> bool:
    sec = _memstack()
    if "enabled" in sec:
        return bool(sec.get("enabled"))
    return default


def memstack_kb_backend(default: str = "sqlite") -> str:
    return str(_memstack().get("kb_backend") or default).strip() or default


def memstack_l1_backend(default: str = "sqlite") -> str:
    name = _memstack().get("l1_backend")
    if not name:
        name = _agent_memory().get("backend")
    return str(name or default).strip() or default


def memstack_preferences_backend(default: str = "static") -> str:
    return str(_memstack().get("preferences_backend") or default).strip() or default


def memstack_inject_top_k(default: int = 3) -> int:
    try:
        return max(0, int(_memstack().get("inject_top_k", default)))
    except (TypeError, ValueError):
        return default


def hub_base_url() -> str:
    """skill_config.hub.url — 进度通报/外链默认 Hub 根地址。"""
    url = str((_load().get("hub") or {}).get("url") or "").strip().rstrip("/")
    return url or "http://127.0.0.1:8765"


def agent_msg_timeout(default: int = 1800) -> int:
    return section_int("executor", "agent_msg_timeout", default)


def _group_discussion() -> dict:
    raw = _load().get("group_discussion")
    return dict(raw) if isinstance(raw, dict) else {}


def group_discussion_default_max_rounds(default: int = 3) -> int:
    return max(1, section_int("group_discussion", "default_max_rounds", default))


def roundtable_max_rounds_cap(default: int = 50) -> int:
    return max(1, section_int("group_discussion", "max_rounds_cap", default))


def roundtable_turn_timeout_sec(default: int = 300) -> int:
    gd = _group_discussion().get("roundtable_turn_timeout")
    if gd is not None:
        try:
            configured = int(gd)
            cap = agent_msg_timeout()
            return max(60, min(configured, cap))
        except (TypeError, ValueError):
            pass
    return section_int("executor", "roundtable_turn_timeout", default)


def roundtable_quorum_ratio(default: float = 2 / 3) -> float:
    try:
        val = float(_group_discussion().get("quorum_ratio", default))
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return default


def group_discussion_auto_finalize_on_max_rounds(default: bool = True) -> bool:
    val = _group_discussion().get("auto_finalize_on_max_rounds", default)
    return bool(val) if val is not None else default


def group_discussion_allow_round_extension(default: bool = True) -> bool:
    val = _group_discussion().get("allow_round_extension", default)
    return bool(val) if val is not None else default


def group_discussion_kill_cli_on_cancel(default: bool = True) -> bool:
    val = _group_discussion().get("kill_cli_on_cancel", default)
    return bool(val) if val is not None else default


def roundtable_terminate_commands() -> list[str]:
    raw = _group_discussion().get("terminate_commands")
    if isinstance(raw, list):
        cmds = [str(c).strip() for c in raw if str(c).strip()]
        if cmds:
            return cmds
    return ["/终止讨论", "/终止圆桌", "/stop roundtable"]
