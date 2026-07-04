"""将 agents_registry 中的 Skill 同步到各 CLI 的原生 skill 注册表。"""

from __future__ import annotations

from common.agent.agent_skills import get_agent_mounted_skill_ids
from common.paths import workspace_dir


def sync_agent_skills_to_cli(agent_id: str, *, workspace: str | None = None) -> dict:
    """按 Agent 后端，把 registry skills 写入 CLI 原生 skill 系统（非全局）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return {"success": False, "error": "agent_id 为空"}

    import adapter as _adapter  # noqa: F401  — side-effect CLI 注册 — 注册 CLI 实例
    from adapter.core.registry import registry
    from base.agent_chat import get_agent_backend_config

    backend_cfg = get_agent_backend_config(aid)
    adapter = registry.get(backend_cfg.backend_id)
    if adapter is None:
        return {
            "success": False,
            "error": f"未知后端: {backend_cfg.backend_id}",
            "agent_id": aid,
        }

    ws = workspace or str(workspace_dir(aid))
    skill_ids = get_agent_mounted_skill_ids(aid)
    result = adapter.sync_agent_skills(aid, ws, skill_ids)
    result.setdefault("agent_id", aid)
    result.setdefault("backend_id", backend_cfg.backend_id)
    result.setdefault("skill_ids", skill_ids)
    return result


def sync_all_agent_skills_to_cli() -> dict:
    """为所有可用 Agent 执行 CLI skill 同步（幂等）。"""
    from hub.services.agent_registry import list_available_agent_ids

    results: list[dict] = []
    for aid in list_available_agent_ids():
        results.append(sync_agent_skills_to_cli(aid))
    ok = all(r.get("success") for r in results)
    return {"success": ok, "count": len(results), "results": results}


def remount_skill_after_library_move(skill_id: str) -> dict:
    """Skill 物理目录变更后：规范化 registry 挂载 id，并刷新 Cursor / CLI 工作区软链。"""
    from common.skill.skill_link import (
        _migrate_flat_vendor_anchor,
        business_skill_anchor,
        sync_cursor_skill_links,
    )
    from hub.services.agent_registry import (
        list_agents_mounting_skill,
        normalize_agent_skill_mounts,
    )

    sid = (skill_id or "").strip()
    if not sid:
        return {"success": False, "error": "skill_id 为空"}

    dest = business_skill_anchor(sid)
    _migrate_flat_vendor_anchor(sid, dest)

    registry_updated = normalize_agent_skill_mounts(skill_id=sid)
    agent_ids = sorted(set(list_agents_mounting_skill(sid)) | set(registry_updated))

    cursor = sync_cursor_skill_links(skill_ids=[sid])
    cli_results: list[dict] = []
    for aid in agent_ids:
        cli_results.append(sync_agent_skills_to_cli(aid))

    cli_ok = all(r.get("success") for r in cli_results) if cli_results else True
    return {
        "success": cursor.get("success", False) and cli_ok,
        "skill_id": sid,
        "registry_normalized": registry_updated,
        "agents_synced": agent_ids,
        "cursor": cursor,
        "cli": cli_results,
    }


def sync_all_agent_skill_mounts() -> dict:
    """将 registry skills 同步到 CLI，并清理 AGENTS.md 中历史 Skill 挂载节。"""
    from common.agent.agent_skills import strip_agents_md_skills_section
    from common.skill.skill_link import ensure_all_vendor_skill_links, sync_cursor_skill_links
    from hub.services.agent_registry import list_available_agent_ids

    vendor = ensure_all_vendor_skill_links()
    cursor = sync_cursor_skill_links()
    agents_md_stripped: list[str] = []
    cli = sync_all_agent_skills_to_cli()
    for aid in list_available_agent_ids():
        if strip_agents_md_skills_section(aid):
            agents_md_stripped.append(aid)
    ok = (
        cli.get("success", False)
        and vendor.get("success", False)
        and cursor.get("success", False)
    )
    return {
        "success": ok,
        "vendor": vendor,
        "cursor": cursor,
        "agents_md_stripped": agents_md_stripped,
        "cli": cli,
    }
