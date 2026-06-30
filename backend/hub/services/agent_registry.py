"""Agent 注册表 — 供 Main 选团队与 API 暴露。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from common.paths import AGENTS_REGISTRY_FILE, WORKSPACES_DIR, WORKSPACE_PREFIX
from base.agent_chat import scan_agents
from common.coordinator import get_coordinator_id


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
            "skills": meta.get("skills") or [],
            "mcp_servers": meta.get("mcp_servers") or [],
            "available": aid in available_ids,
            "backend": scan_info.get("backend", ""),
            "model": scan_info.get("model", ""),
            "model_override": scan_info.get("model_override", ""),
            "uses_settings_default": bool(scan_info.get("uses_settings_default")),
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
            if role_filter == "worker" and info.get("role") == "coordinator" and aid == get_coordinator_id():
                pass  # coordinator 单独说明
            elif role_filter == "worker" and aid in (get_coordinator_id(), "deputy"):
                continue
        if not info.get("available"):
            continue
        from common.gate.registry import task_type_label

        caps = "、".join(info.get("capabilities") or [])[:80]
        tts_raw = info.get("task_types") or []
        tts = "、".join(task_type_label(t) for t in tts_raw)
        extra = f"；可执行任务：{tts}" if tts else "；可执行任务：（未配置）"
        desc = (info.get("description") or "")[:120]
        lines.append(f"- {aid}（{info.get('name', aid)}）：{desc}；能力：{caps}{extra}")
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
                   task_types: Optional[list[str]] = None,
                   skills: Optional[list[str]] = None,
                   skills_explicit: bool = False,
                   mcp_servers: Optional[list[str]] = None,
                   mcp_explicit: bool = False) -> dict:
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
    existing = raw["agents"].get(agent_id) or {}
    merged_caps = capabilities if capabilities is not None else (existing.get("capabilities") or [])
    merged_tts = task_types if task_types is not None else (existing.get("task_types") or [])
    merged_skills = skills if skills is not None else (existing.get("skills") or [])
    merged_mcp = mcp_servers if mcp_servers is not None else (existing.get("mcp_servers") or [])
    entry = {
        "name": name or existing.get("name") or agent_id,
        "role": role or existing.get("role") or "worker",
        "description": description if description != "" else (existing.get("description") or ""),
        "capabilities": list(merged_caps),
        "task_types": sorted(set(merged_tts)),
    }
    if skills is not None or skills_explicit or existing.get("skills") is not None:
        entry["skills"] = sorted(set(str(s).strip() for s in merged_skills if str(s).strip()))
    if mcp_servers is not None or mcp_explicit or existing.get("mcp_servers") is not None:
        entry["mcp_servers"] = sorted(set(str(s).strip() for s in merged_mcp if str(s).strip()))
    raw["agents"][agent_id] = entry
    _save_registry_file(raw)
    if skills is not None or skills_explicit:
        from common.agent.agent_skills import strip_agents_md_skills_section

        strip_agents_md_skills_section(agent_id)
        from common.agent.adapter_skill_registry import sync_agent_skills_to_cli

        sync_agent_skills_to_cli(agent_id)
    if mcp_servers is not None or mcp_explicit:
        from common.agent.agent_mcp import strip_agents_md_mcp_section

        strip_agents_md_mcp_section(agent_id)
        from common.agent.adapter_mcp_registry import sync_agent_mcp_to_cli

        sync_agent_mcp_to_cli(agent_id)
    return {"success": True, "agent_id": agent_id}


def update_agent_skills(agent_id: str, skills: list[str]) -> dict:
    """更新 Agent 挂载的 skill id 列表（严格：仅列表内 Skill 对 Agent 可见）。"""
    from common.skill.skill_catalog import validate_skill_ids

    valid, unknown = validate_skill_ids(skills)
    if unknown:
        return {
            "success": False,
            "error": f"以下 skill 无 SKILL.md：{', '.join(unknown)}",
        }
    reg = get_agents_registry()["agents"].get(agent_id) or {}
    return register_agent(
        agent_id,
        name=reg.get("name", agent_id),
        role=reg.get("role", "worker"),
        description=reg.get("description", ""),
        capabilities=reg.get("capabilities"),
        task_types=reg.get("task_types"),
        skills=valid,
        skills_explicit=True,
    )


def update_agent_mcp_servers(agent_id: str, mcp_servers: list[str]) -> dict:
    """更新 Agent 挂载的 MCP id 列表（须全局 enabled）。"""
    from common.mcp_catalog import validate_mcp_ids

    valid, unknown = validate_mcp_ids(mcp_servers)
    if unknown:
        return {
            "success": False,
            "error": f"以下 MCP 不存在或未启用：{', '.join(unknown)}",
        }
    reg = get_agents_registry()["agents"].get(agent_id) or {}
    return register_agent(
        agent_id,
        name=reg.get("name", agent_id),
        role=reg.get("role", "worker"),
        description=reg.get("description", ""),
        capabilities=reg.get("capabilities"),
        task_types=reg.get("task_types"),
        skills=reg.get("skills"),
        mcp_servers=valid,
        mcp_explicit=True,
    )


def update_agent_task_types(agent_id: str, task_types: list[str]) -> dict:
    """更新 Agent 可执行的 task_type 列表（须在 templates.yaml 已注册）。"""
    from common.gate.registry import get_spec

    unknown = [t for t in task_types if get_spec(t) is None]
    if unknown:
        return {"success": False,
                "error": f"以下 task_type 未注册：{', '.join(unknown)}；请先在「任务类型」中创建"}
    reg = get_agents_registry()["agents"].get(agent_id) or {}
    return register_agent(
        agent_id,
        name=reg.get("name", agent_id),
        role=reg.get("role", "worker"),
        description=reg.get("description", ""),
        capabilities=reg.get("capabilities"),
        task_types=sorted(set(task_types)),
    )


def _load_business_roster() -> dict:
    from common.paths import BUSINESS_DIR
    import json

    fp = BUSINESS_DIR / "templates" / "business-roster.json"
    if not fp.is_file():
        return {}
    try:
        raw = json.loads(fp.read_text(encoding="utf-8"))
        return raw.get("agents") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_pgd_template() -> dict:
    from common.workflow.workflow_bootstrap import load_pgd_agent_template

    return load_pgd_agent_template()


def sync_missing_agent_task_types(*, only_empty: bool = True) -> dict:
    """为 workspace 存在但 task_types 为空的 Agent 补全能力（名册 → PGD → 描述推导）。"""
    from common.agent.agent_task_type_suggest import suggest_task_types_for_agent

    roster = _load_business_roster()
    pgd = _load_pgd_template()
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    updated: list[dict] = []

    for aid in list_available_agent_ids():
        existing = raw["agents"].get(aid) or {}
        current = list(existing.get("task_types") or [])
        if only_empty and current:
            continue

        meta = roster.get(aid) or pgd.get(aid) or existing
        tts = list(meta.get("task_types") or [])
        sks = list(existing.get("skills") or [])
        source = "roster" if aid in roster else ("pgd" if aid in pgd else "")

        if not tts:
            desc = meta.get("description") or existing.get("description") or ""
            name = meta.get("name") or existing.get("name") or aid
            try:
                sug = suggest_task_types_for_agent(desc, name=name, agent_id=aid)
                tts = sug.get("task_types") or []
                source = "suggest"
            except ValueError:
                continue

        if not tts:
            continue
        if only_empty and current:
            continue
        merged = sorted(set(current) | set(tts))
        if merged == current:
            continue

        register_agent(
            aid,
            name=meta.get("name") or existing.get("name") or aid,
            role=meta.get("role") or existing.get("role") or "worker",
            description=meta.get("description") or existing.get("description") or "",
            capabilities=meta.get("capabilities") or existing.get("capabilities"),
            task_types=merged,
            skills=sks,
            skills_explicit=bool(sks),
        )
        updated.append({"agent_id": aid, "task_types": merged, "source": source or "merge"})

    return {"success": True, "updated": updated, "count": len(updated)}


def sync_missing_agent_skills(*, only_empty: bool = True) -> dict:
    """为 registry 中未配置 skills 的 Agent 从名册/PGD 补全挂载。"""
    roster = _load_business_roster()
    pgd = _load_pgd_template()
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    updated: list[dict] = []

    for aid in list_available_agent_ids():
        existing = raw["agents"].get(aid) or {}
        current = list(existing.get("skills") or [])
        if only_empty and current:
            continue

        meta = roster.get(aid) or pgd.get(aid) or {}
        sks = list(meta.get("skills") or [])
        if not sks:
            continue

        register_agent(
            aid,
            name=meta.get("name") or existing.get("name") or aid,
            role=meta.get("role") or existing.get("role") or "worker",
            description=meta.get("description") or existing.get("description") or "",
            capabilities=meta.get("capabilities") or existing.get("capabilities"),
            task_types=existing.get("task_types"),
            skills=sks,
            skills_explicit=True,
        )
        updated.append({"agent_id": aid, "skills": sorted(set(sks))})

    return {"success": True, "updated": updated, "count": len(updated)}


def list_agents_mounting_skill(skill_id: str) -> list[str]:
    """返回 skills[] 中挂载了该 skill（含路径式引用）的 agent_id。"""
    from common.skill.skill_catalog import canonical_skill_mount_id

    sid = (skill_id or "").strip()
    if not sid:
        return []
    out: list[str] = []
    for aid, meta in get_agents_registry()["agents"].items():
        for ref in meta.get("skills") or []:
            ref_s = str(ref).strip()
            if not ref_s:
                continue
            if ref_s == sid or canonical_skill_mount_id(ref_s) == sid:
                out.append(aid)
                break
    return out


def normalize_agent_skill_mounts(*, skill_id: str | None = None) -> list[str]:
    """将 agents_registry skills[] 中的路径式引用改写为规范 skill id；返回被更新的 agent_id。"""
    from common.skill.skill_catalog import canonical_skill_mount_id

    sid_filter = (skill_id or "").strip() or None
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    updated: list[str] = []
    for aid, meta in list(raw["agents"].items()):
        skills = [str(s).strip() for s in (meta.get("skills") or []) if str(s).strip()]
        if sid_filter and not any(
            s == sid_filter or canonical_skill_mount_id(s) == sid_filter for s in skills
        ):
            continue
        new_skills: list[str] = []
        seen: set[str] = set()
        changed = False
        for ref in skills:
            canon = canonical_skill_mount_id(ref)
            target = canon if canon else ref
            if canon and canon != ref:
                changed = True
            if target in seen:
                if ref != target:
                    changed = True
                continue
            seen.add(target)
            new_skills.append(target)
        if len(new_skills) != len(skills):
            changed = True
        if not changed:
            continue
        meta = dict(meta)
        meta["skills"] = sorted(new_skills)
        raw["agents"][aid] = meta
        updated.append(aid)
    if updated:
        _save_registry_file(raw)
    return updated


def remove_skill_from_all_agents(skill_id: str) -> list[str]:
    """从所有 Agent 的 skills 列表中移除指定 skill_id；返回被更新的 agent_id。"""
    sid = (skill_id or "").strip()
    if not sid:
        return []
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    updated: list[str] = []
    for aid, meta in list(raw["agents"].items()):
        skills = list(meta.get("skills") or [])
        if sid not in skills:
            continue
        new_skills = [s for s in skills if s != sid]
        register_agent(
            aid,
            name=meta.get("name") or aid,
            role=meta.get("role") or "worker",
            description=meta.get("description") or "",
            capabilities=meta.get("capabilities"),
            task_types=meta.get("task_types"),
            skills=new_skills,
            skills_explicit=True,
        )
        updated.append(aid)
    return updated


def remove_mcp_from_all_agents(server_id: str) -> list[str]:
    """从所有 Agent 的 mcp_servers 列表中移除指定 server_id。"""
    sid = (server_id or "").strip()
    if not sid:
        return []
    raw = _load_registry_file()
    raw.setdefault("agents", {})
    updated: list[str] = []
    for aid, meta in list(raw["agents"].items()):
        servers = list(meta.get("mcp_servers") or [])
        if sid not in servers:
            continue
        new_servers = [s for s in servers if s != sid]
        register_agent(
            aid,
            name=meta.get("name") or aid,
            role=meta.get("role") or "worker",
            description=meta.get("description") or "",
            capabilities=meta.get("capabilities"),
            task_types=meta.get("task_types"),
            skills=meta.get("skills"),
            mcp_servers=new_servers,
            mcp_explicit=True,
        )
        updated.append(aid)
    return updated


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
