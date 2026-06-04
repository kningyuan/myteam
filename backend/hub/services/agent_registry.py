"""Agent 注册表 — 供 Main 选团队与 API 暴露。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from hub.paths import AGENTS_REGISTRY_FILE, WORKSPACES_DIR, WORKSPACE_PREFIX
from base.agent_chat import scan_agents


def _load_registry_file() -> dict:
    if not AGENTS_REGISTRY_FILE.exists():
        return {"version": "1.0", "agents": {}}
    try:
        with open(AGENTS_REGISTRY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": "1.0", "agents": {}}


def list_available_agent_ids() -> list[str]:
    """filesystem 上存在的 workspace agent id。"""
    ids = []
    if WORKSPACES_DIR.is_dir():
        for ws in sorted(WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*")):
            if ws.is_dir():
                aid = ws.name[len(WORKSPACE_PREFIX):]
                if aid:  # 跳过 workspace- 这类无 id 的空目录
                    ids.append(aid)
    return ids


def get_agents_registry(*, merge_scan: bool = True) -> dict:
    """返回完整注册表：静态定义 + 扫描到的可用性。"""
    raw = _load_registry_file()
    static_agents = raw.get("agents") or {}
    scanned = {a["id"]: a for a in scan_agents()} if merge_scan else {}
    available_ids = set(list_available_agent_ids())

    agents_out = {}
    all_ids = sorted(set(static_agents.keys()) | available_ids)
    for aid in all_ids:
        meta = dict(static_agents.get(aid) or {})
        scan_info = scanned.get(aid) or {}
        agents_out[aid] = {
            "id": aid,
            "name": meta.get("name") or scan_info.get("name") or aid,
            "role": meta.get("role", "worker"),
            "description": meta.get("description", ""),
            "capabilities": meta.get("capabilities") or [],
            "task_types": meta.get("task_types") or [],
            "available": aid in available_ids,
            "backend": scan_info.get("backend", ""),
            "model": scan_info.get("model", ""),
            "workspace": scan_info.get("workspace", ""),
        }
    return {
        "version": raw.get("version", "1.0"),
        "agents": agents_out,
        "available_ids": sorted(available_ids),
    }


def format_registry_for_prompt(*, role_filter: Optional[str] = None) -> str:
    """生成 Main team_config 可用的角色说明文本。"""
    reg = get_agents_registry()
    lines = ["可用 Agent（仅能从下列 id 中选择，须为英文小写 id）：", ""]
    for aid, info in reg["agents"].items():
        if role_filter and info.get("role") != role_filter:
            if role_filter == "worker" and info.get("role") == "coordinator" and aid == "main":
                pass  # main 单独说明
            elif role_filter == "worker" and aid in ("main", "deputy"):
                continue
        if not info.get("available"):
            continue
        caps = "、".join(info.get("capabilities") or [])[:80]
        desc = info.get("description") or ""
        lines.append(f"- {aid}（{info.get('name', aid)}）：{desc}；能力：{caps}")
    return "\n".join(lines)


def validate_agent_ids(agent_ids: list[str]) -> tuple[bool, list[str]]:
    """检查 agent id 是否在可用列表中。"""
    available = set(list_available_agent_ids())
    bad = [a for a in agent_ids if a not in available]
    return len(bad) == 0, bad


# ── 注册表写操作 ────────────────────────────────────────────────


def register_agent(agent_id: str, *, name: str = "", role: str = "worker",
                   description: str = "",
                   capabilities: Optional[list[str]] = None,
                   task_types: Optional[list[str]] = None) -> dict:
    """在 agents_registry.json 中注册/更新 agent 元信息。

    不创建 workspace 或 identity 文件——只维护注册表元数据。
    agent_id 须已存在 workspace 目录（否则静默失败，不污染注册表）。
    """
    available = set(list_available_agent_ids())
    if agent_id not in available:
        return {"success": False,
                "error": f"Agent '{agent_id}' 的工作目录不存在，请先创建"}
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    raw["agents"][agent_id] = {
        "name": name or agent_id,
        "role": role,
        "description": description or "",
        "capabilities": capabilities or [],
        "task_types": task_types or [],
    }
    _save_registry_file(raw)
    return {"success": True, "agent_id": agent_id}


def unregister_agent(agent_id: str) -> dict:
    """从 agents_registry.json 中移除 agent。不影响 workspace/config。"""
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    if agent_id not in raw["agents"]:
        return {"success": False, "error": f"Agent '{agent_id}' 不在注册表中"}
    del raw["agents"][agent_id]
    _save_registry_file(raw)
    return {"success": True, "agent_id": agent_id}


def _save_registry_file(data: dict) -> None:
    AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENTS_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
