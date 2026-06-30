"""将 agents_registry 中的 MCP 同步到各 CLI 的原生 MCP 配置。"""

from __future__ import annotations

from common.agent.agent_mcp import get_agent_mcp_ids
from common.paths import workspace_dir


def sync_agent_mcp_to_cli(agent_id: str, *, workspace: str | None = None) -> dict:
    aid = (agent_id or "").strip()
    if not aid:
        return {"success": False, "error": "agent_id 为空"}

    import adapter  # noqa: F401  — side-effect CLI 注册
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
    server_ids = get_agent_mcp_ids(aid)
    result = adapter.sync_agent_mcp(aid, ws, server_ids)
    result.setdefault("agent_id", aid)
    result.setdefault("backend_id", backend_cfg.backend_id)
    result.setdefault("server_ids", server_ids)
    return result


def sync_all_agent_mcp_to_cli() -> dict:
    from hub.services.agent_registry import list_available_agent_ids

    results: list[dict] = []
    for aid in list_available_agent_ids():
        results.append(sync_agent_mcp_to_cli(aid))
    ok = all(r.get("success") for r in results)
    return {"success": ok, "count": len(results), "results": results}


def sync_all_agent_mcp_mounts() -> dict:
    """将 registry MCP 同步到 CLI，并清理 AGENTS.md 中历史 MCP 挂载节。"""
    from common.agent.agent_mcp import strip_agents_md_mcp_section
    from hub.services.agent_registry import list_available_agent_ids

    agents_md_stripped: list[str] = []
    cli = sync_all_agent_mcp_to_cli()
    for aid in list_available_agent_ids():
        if strip_agents_md_mcp_section(aid):
            agents_md_stripped.append(aid)
    return {
        "success": cli.get("success", False),
        "agents_md_stripped": agents_md_stripped,
        "cli": cli,
    }
