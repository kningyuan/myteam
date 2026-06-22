"""Agent 注册表 — skill 侧读取 config/agents_registry.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from common.paths import BUSINESS_CONFIG_DIR, MYTEAM_ROOT, WORKSPACES_DIR, WORKSPACE_PREFIX

REGISTRY_FILE = BUSINESS_CONFIG_DIR / "agents_registry.json"
_ROSTER_FILE = MYTEAM_ROOT / "business" / "templates" / "business-roster.json"


def _load_business_roster_agent(agent_id: str) -> dict:
    if not _ROSTER_FILE.is_file():
        return {}
    try:
        import json

        raw = json.loads(_ROSTER_FILE.read_text(encoding="utf-8"))
        entry = (raw.get("agents") or {}).get(agent_id)
        return dict(entry) if isinstance(entry, dict) else {}
    except Exception:
        return {}


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
        caps = "、".join(info.get("capabilities") or [])[:80]
        tts = "、".join(info.get("task_types") or [])
        bound = (info.get("boundaries") or "")[:120]
        extra = f"；可执行 task_type：{tts}" if tts else ""
        if bound:
            extra += f"；边界：{bound}"
        lines.append(f"- {aid}（{name}）：{desc}；擅长：{caps}{extra}")
    if not workers_only:
        lines.append("")
        lines.append("说明：main 为协调者，通常不必放入 agents 列表；deputy 用于持续项目轮次评审。")
    return "\n".join(lines)


def validate_agent_ids(agent_ids: list[str]) -> tuple[bool, list[str]]:
    available = set(list_available_agent_ids())
    bad = [a for a in agent_ids if a not in available]
    return len(bad) == 0, bad


def build_registry_capability_context(agent_id: str) -> str:
    """从 agents_registry 生成「我是谁、能做什么」块（替代 AGENTS.md 能力段）。"""
    info = get_agent_info(agent_id)
    if not info:
        return ""
    lines: list[str] = ["<registry_capabilities>"]
    name = (info.get("name") or agent_id).strip()
    lines.append(f"注册名：{name}")
    desc = (info.get("description") or "").strip()
    if desc:
        lines.append(f"角色说明：{desc}")
    tts = [str(t).strip() for t in (info.get("task_types") or []) if str(t).strip()]
    if tts:
        lines.append(f"可接 task_type（workflow 硬边界）：{', '.join(tts)}")
    caps = [str(c).strip() for c in (info.get("capabilities") or []) if str(c).strip()]
    if caps:
        lines.append(f"能力标签：{'、'.join(caps)}")
    bound = (info.get("boundaries") or "").strip()
    if bound:
        lines.append(f"边界：{bound}")
    lines.append("</registry_capabilities>")
    return "\n".join(lines)


def get_agent_info(agent_id: str) -> dict:
    """注册表中该 agent 的元数据；skills/task_types 空时回退 business-roster 模板。"""
    info = dict((_load_registry().get("agents") or {}).get(agent_id) or {})
    roster = _load_business_roster_agent(agent_id)
    if roster:
        if not info.get("skills") and roster.get("skills"):
            info["skills"] = list(roster["skills"])
        if not info.get("task_types") and roster.get("task_types"):
            info["task_types"] = list(roster["task_types"])
        if not info.get("description") and roster.get("description"):
            info["description"] = roster["description"]
        if not info.get("capabilities") and roster.get("capabilities"):
            info["capabilities"] = list(roster["capabilities"])
    return info


def get_agent_task_types(agent_id: str) -> list[str]:
    """注册表中声明的交付物 task_type 列表（可接哪些交付类型）。"""
    return list(get_agent_info(agent_id).get("task_types") or [])


def agent_task_type_map() -> dict[str, list[str]]:
    """agent_id → task_types（仅静态注册表，不含 filesystem 扫描）。"""
    raw = _load_registry().get("agents") or {}
    return {aid: list(info.get("task_types") or []) for aid, info in raw.items()}
