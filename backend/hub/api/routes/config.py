"""System / skill / backend / agents-registry config routes (P3.1 Wave 3)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from base.agent_chat import (
    apply_model_to_all,
    get_agent_backend_config,
    get_backend_models,
    list_all_backends_with_models,
    set_agent_backend_config,
)
from store.skill_config import skill_config
from store.system_config import system_config

router = APIRouter(tags=["config"])


@router.get("/api/agents/{agent_id}/config")
async def agent_config(agent_id: str):
    cfg = get_agent_backend_config(agent_id)
    return {
        "agent_id": agent_id,
        "backend": cfg.backend_id,
        "model": cfg.model,
        "model_override": cfg.model_override,
        "uses_settings_default": cfg.uses_settings_default,
    }


@router.post("/api/agents/{agent_id}/config")
async def update_agent_config(agent_id: str, body: dict):
    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    set_agent_backend_config(agent_id, backend, model)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


@router.post("/api/agents/apply-model")
async def api_apply_model(body: dict):
    backend = body.get("backend", "opencode")
    model = (body.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    result = apply_model_to_all(backend, model)
    return {"success": True, **result}


@router.get("/api/backends")
async def list_backends():
    return {"backends": list_all_backends_with_models()}


@router.get("/api/backends/{backend_id}/models")
async def list_backend_models(backend_id: str, refresh: bool = False):
    try:
        models = get_backend_models(backend_id, refresh=refresh)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"unknown backend: {backend_id}")
    return {"backend_id": backend_id, "models": models, "refreshed": bool(refresh)}


@router.get("/api/config")
async def get_system_config():
    return {"config": system_config.get_all()}


@router.put("/api/config")
async def update_system_config(body: dict):
    config_data = body.get("config", {})
    if config_data:
        system_config.update_all(config_data)
    return {"success": True, "config": system_config.get_all()}


@router.get("/api/skill-config")
@router.get("/api/skill_config")
async def get_skill_config_api():
    return {"config": skill_config.get_all()}


@router.put("/api/skill-config")
@router.put("/api/skill_config")
async def update_skill_config_api(body: dict):
    config_data = body.get("config", {})
    if config_data:
        skill_config.update_all(config_data)
        from common.skill_settings import reload_skill_settings

        reload_skill_settings()
    return {"success": True, "config": skill_config.get_all()}


@router.get("/api/agents/registry")
async def get_agents_registry_api():
    from hub.services.agent_registry import get_agents_registry

    return get_agents_registry()


@router.post("/api/agents/sync-task-types")
async def api_sync_agent_task_types():
    """为未配置 task_types 的 Agent 从名册/PGD/描述规则补全。"""
    from hub.services.agent_registry import sync_missing_agent_task_types

    return sync_missing_agent_task_types(only_empty=True)


@router.post("/api/agents/sync-skills")
async def api_sync_agent_skills():
    """为未配置 skills 的 Agent 从名册/PGD 补全挂载，并同步到 CLI skill 注册表。"""
    from hub.services.agent_registry import sync_missing_agent_skills
    from common.adapter_skill_registry import sync_all_agent_skill_mounts

    roster_result = sync_missing_agent_skills(only_empty=True)
    mount_result = sync_all_agent_skill_mounts()
    return {
        "success": roster_result.get("success") and mount_result.get("success"),
        "roster": roster_result,
        "mount": mount_result,
    }


@router.post("/api/agents/sync-mcp")
async def api_sync_agent_mcp():
    """同步所有 Agent 的 MCP 挂载到各 CLI 后端，并清理 AGENTS.md 历史 MCP 节。"""
    from common.adapter_mcp_registry import sync_all_agent_mcp_mounts

    return sync_all_agent_mcp_mounts()


@router.post("/api/agents/suggest-task-types")
async def api_suggest_agent_task_types(body: dict):
    from common.agent_task_type_suggest import suggest_task_types_for_agent

    desc = (body.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="description 不能为空")
    try:
        return suggest_task_types_for_agent(
            desc,
            name=(body.get("name") or "").strip(),
            agent_id=(body.get("agent_id") or "").strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
