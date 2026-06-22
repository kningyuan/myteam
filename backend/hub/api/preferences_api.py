"""团队偏好库 API — config/USER.md（非 per-agent）。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from memstack.preferences.user_store import (
    GLOBAL_USER_PATH,
    list_legacy_per_agent_user_files,
    read_global_user_md,
    sync_all_agents_bounded_user,
    write_global_user_md,
)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesBody(BaseModel):
    content: str


@router.get("/library")
async def get_preferences_library():
    """团队偏好库（全员 Agent execute/群聊 注入同一份）。"""
    legacy = list_legacy_per_agent_user_files()
    return {
        "content": read_global_user_md(),
        "path": str(GLOBAL_USER_PATH),
        "scope": "team",
        "legacy_per_agent_files": legacy,
        "legacy_warning": (
            f"发现 {len(legacy)} 个历史 per-agent USER.md；"
            "现已统一为团队偏好库，请在此编辑并删除旧文件避免混淆。"
            if legacy
            else None
        ),
    }


@router.put("/library")
async def put_preferences_library(body: PreferencesBody):
    path = write_global_user_md(body.content)
    from common.hub_operation_meta import touch

    touch("preferences", "library")
    return {
        "success": True,
        "path": str(path),
        "synced_agents": sync_all_agents_bounded_user(),
    }


@router.post("/library/sync")
async def sync_preferences_to_agents():
    synced = sync_all_agents_bounded_user()
    return {"success": True, "synced_agents": synced}
