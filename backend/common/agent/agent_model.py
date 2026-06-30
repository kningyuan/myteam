#!/usr/bin/env python3
"""Agent backend/model 解析 — 设置页为默认，agents_config 为 per-agent 覆盖。"""
from __future__ import annotations

import json
from typing import Optional

from common.paths import BUSINESS_CONFIG_DIR, WORKSPACES_DIR, WORKSPACE_PREFIX


def read_agents_config() -> dict:
    path = BUSINESS_CONFIG_DIR / "agents_config.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_agents_config(config: dict) -> None:
    path = BUSINESS_CONFIG_DIR / "agents_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def system_default_backend() -> str:
    try:
        from config_store.system_config import system_config

        return (system_config.get("system", "default_backend", default="opencode") or "opencode").strip()
    except Exception:
        return "opencode"


def default_model_for_backend(backend_id: str) -> str:
    """设置页 default_model → adapter 默认。"""
    backend = (backend_id or "opencode").strip() or "opencode"
    try:
        from config_store.system_config import system_config

        dm = (system_config.get_default_model(backend) or "").strip()
        if dm:
            return dm
    except Exception:
        pass
    try:
        import adapter  # noqa: F401  — side-effect CLI 注册
        from adapter.core.registry import registry

        adapter = registry.get(backend)
        if adapter is not None:
            return (adapter.get_default_model() or "").strip()
    except Exception:
        pass
    return ""


def agent_model_override(agent_id: str, *, config: Optional[dict] = None) -> str:
    """agents_config 中显式配置的 model（空 = 未单独配置，跟随设置）。"""
    cfg = config if config is not None else read_agents_config()
    return ((cfg.get(agent_id) or {}).get("model") or "").strip()


def agent_backend_override(agent_id: str, *, config: Optional[dict] = None) -> str:
    cfg = config if config is not None else read_agents_config()
    return ((cfg.get(agent_id) or {}).get("backend") or "").strip()


def resolve_agent_backend(agent_id: str, *, config: Optional[dict] = None) -> str:
    explicit = agent_backend_override(agent_id, config=config)
    return explicit or system_default_backend()


def resolve_agent_model(agent_id: str, *, config: Optional[dict] = None) -> str:
    """运行时 model：Agent 管理中的显式配置 → 设置页 default_model。"""
    cfg = config if config is not None else read_agents_config()
    explicit = agent_model_override(agent_id, config=cfg)
    if explicit:
        return explicit
    backend = resolve_agent_backend(agent_id, config=cfg)
    return default_model_for_backend(backend)


def uses_settings_default(agent_id: str, *, config: Optional[dict] = None) -> bool:
    return not agent_model_override(agent_id, config=config)


def list_workspace_agent_ids() -> list[str]:
    if not WORKSPACES_DIR.is_dir():
        return []
    ids: list[str] = []
    for ws in sorted(WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*")):
        if ws.is_dir():
            aid = ws.name[len(WORKSPACE_PREFIX):]
            if aid:
                ids.append(aid)
    return ids


def ensure_agents_config_entries(*, persist: bool = True) -> list[str]:
    """为每个 workspace agent 补全 agents_config 条目（仅 backend/name，不写 model）。"""
    config = read_agents_config()
    default_backend = system_default_backend()
    touched: list[str] = []
    for aid in list_workspace_agent_ids():
        entry = dict(config.get(aid) or {})
        changed = False
        if not entry.get("name"):
            entry["name"] = aid
            changed = True
        if not agent_backend_override(aid, config={aid: entry}):
            entry["backend"] = default_backend
            changed = True
        entry.setdefault("extra", {})
        if changed or aid not in config:
            config[aid] = entry
            touched.append(aid)
    if touched and persist:
        write_agents_config(config)
    return touched
