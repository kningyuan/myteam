"""Agent 注册表 — skill 侧读取 config/agents_registry.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from common.paths import CONFIG_DIR, MYTEAM_ROOT, WORKSPACES_DIR, WORKSPACE_PREFIX

REGISTRY_FILE = CONFIG_DIR / "agents_registry.json"


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "1.0", "agents": {}}


def list_available_agent_ids() -> list[str]:
    ids = []
    if WORKSPACES_DIR.is_dir():
        for ws in sorted(WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*")):
            if ws.is_dir():
                ids.append(ws.name[len(WORKSPACE_PREFIX):])
    return ids


def format_registry_for_prompt(*, workers_only: bool = False) -> str:
    raw = _load_registry()
    static = raw.get("agents") or {}
    available = set(list_available_agent_ids())
    lines = [
        "以下 Agent 已在 myteam workspaces 中注册，team_config 只能从中选择（英文小写 id）：",
        "",
    ]
    for aid in sorted(static.keys()):
        if aid not in available:
            continue
        info = static[aid]
        if workers_only and aid in ("main", "deputy"):
            continue
        name = info.get("name", aid)
        desc = info.get("description", "")
        caps = "、".join(info.get("capabilities") or [])[:100]
        lines.append(f"- {aid}（{name}）：{desc}；擅长：{caps}")
    if not workers_only:
        lines.append("")
        lines.append("说明：main 为协调者，通常不必放入 agents 列表；deputy 用于持续项目轮次评审。")
    return "\n".join(lines)


def validate_agent_ids(agent_ids: list[str]) -> tuple[bool, list[str]]:
    available = set(list_available_agent_ids())
    bad = [a for a in agent_ids if a not in available]
    return len(bad) == 0, bad
