#!/usr/bin/env python3
"""团队偏好库 — config/USER.md 为唯一真相源，全员 Agent 注入同一份。"""
from __future__ import annotations

from pathlib import Path

from common.paths import CONFIG_DIR, workspace_dir

GLOBAL_USER_PATH = CONFIG_DIR / "USER.md"
GLOBAL_OWNER_ID = "default"
LEGACY_USERS_DIR = CONFIG_DIR / "users"


def global_user_path() -> Path:
    return GLOBAL_USER_PATH


def list_legacy_per_agent_user_files() -> list[dict]:
    """历史 per-agent 偏好文件（供 UI 迁移提示）。"""
    out: list[dict] = []
    if not LEGACY_USERS_DIR.is_dir():
        return out
    for child in sorted(LEGACY_USERS_DIR.iterdir()):
        if not child.is_dir():
            continue
        p = child / "USER.md"
        if p.is_file():
            out.append({"agent_id": child.name, "path": str(p)})
    return out


def read_global_user_md() -> str:
    """团队偏好库 — 只读 config/USER.md。"""
    if GLOBAL_USER_PATH.is_file():
        return GLOBAL_USER_PATH.read_text(encoding="utf-8", errors="replace")
    return ""


def write_global_user_md(content: str) -> Path:
    """写入团队偏好并同步全部 Agent workspace 有界副本。"""
    GLOBAL_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else content + "\n"
    GLOBAL_USER_PATH.write_text(text, encoding="utf-8")
    sync_all_agents_bounded_user()
    return GLOBAL_USER_PATH


def sync_all_agents_bounded_user(agent_ids: list[str] | None = None) -> list[str]:
    """从 config/USER.md 刷新各 Agent workspace/USER.md（有界）。

    Args:
        agent_ids: 可选注入的 agent 列表。None 时尝试从 agents_config.json 读取。
    """
    synced: list[str] = []
    if agent_ids is None:
        try:
            from common.paths import BUSINESS_CONFIG_DIR
            import json
            path = BUSINESS_CONFIG_DIR / "agents_config.json"
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                agent_ids = list(raw.keys())
        except Exception:
            agent_ids = []
        if not agent_ids:
            try:
                from hub.services.agent_registry import list_available_agent_ids
                agent_ids = list_available_agent_ids()
            except Exception:
                agent_ids = []
    if not agent_ids and LEGACY_USERS_DIR.is_dir():
        agent_ids = [d.name for d in LEGACY_USERS_DIR.iterdir() if d.is_dir()]
    for aid in agent_ids:
        try:
            from execution_harness.identity.bounded import sync_bounded_identity
            sync_bounded_identity(aid, owner_id=GLOBAL_OWNER_ID, workspace=workspace_dir(aid))
            synced.append(aid)
        except Exception:
            continue
    return synced


def read_canonical_user_md(owner_id: str, *, agent_id: str = "") -> str:
    """Harness 注入：始终团队全局偏好（忽略 per-agent owner）。"""
    return read_global_user_md()


def write_canonical_user_md(
    owner_id: str,
    content: str,
    *,
    agent_id: str = "",
) -> Path:
    """兼容旧 API — 重定向到全局偏好库。"""
    return write_global_user_md(content)
