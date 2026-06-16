"""MCP API — Hub MCP 统一管理页。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.mcp_catalog import (
    create_mcp_server,
    delete_mcp_server,
    get_mcp_server,
    list_all_mcp_servers,
    update_mcp_server,
    validate_server_id,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class McpServerPayload(BaseModel):
    name: str = ""
    description: str = ""
    enabled: bool = True
    type: str = "local"
    command: list[str] = Field(default_factory=list)
    url: str = ""
    environment: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: Optional[int] = None


class McpServerCreate(McpServerPayload):
    id: str


@router.get("/library")
async def list_mcp_library(include_disabled: bool = True):
    items = list_all_mcp_servers(include_disabled=include_disabled)
    return {"servers": items, "count": len(items)}


@router.get("/library/{server_id}")
async def get_mcp_library_item(server_id: str):
    entry = get_mcp_server(server_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"MCP 不存在：{server_id}")
    return entry


@router.post("/library")
async def post_mcp_library_item(body: McpServerCreate):
    ok, err = validate_server_id(body.id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    result = create_mcp_server(body.id, body.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return result


@router.put("/library/{server_id}")
async def put_mcp_library_item(server_id: str, body: McpServerPayload):
    payload: dict[str, Any] = body.model_dump()
    result = update_mcp_server(server_id, payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失败"))
    return result


@router.patch("/library/{server_id}/enabled")
async def patch_mcp_enabled(server_id: str, body: dict):
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="enabled 须为 boolean")
    result = update_mcp_server(server_id, {"enabled": enabled})
    if not result.get("success"):
        raise HTTPException(status_code=404 if "不存在" in str(result.get("error")) else 400,
                          detail=result.get("error", "更新失败"))
    return result


@router.delete("/library/{server_id}")
async def delete_mcp_library_item(server_id: str):
    from hub.services.agent_registry import remove_mcp_from_all_agents

    entry = get_mcp_server(server_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"MCP 不存在：{server_id}")
    unmounted = remove_mcp_from_all_agents(server_id)
    result = delete_mcp_server(server_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "删除失败"))
    return {
        "success": True,
        "server_id": server_id,
        "unmounted_from": unmounted,
        "unmounted_count": len(unmounted),
    }
