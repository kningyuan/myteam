"""Group chat and project-group routes (P3.1 Wave 3)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from base.group_manager import (
    add_member,
    bind_group_project,
    clear_group_messages,
    create_group,
    delete_group,
    dissolve_group,
    get_group,
    list_groups,
    remove_member,
    reorder_group_members,
    restore_group,
    search_groups,
    send_group_message,
    update_group_roundtable_settings,
)

router = APIRouter(tags=["groups"])
groups_router = APIRouter(prefix="/api/groups", tags=["groups"])
projects_router = APIRouter(prefix="/api/projects", tags=["groups"])


@projects_router.post("/{project_id}/setup-group")
async def api_setup_project_group(project_id: str, body: dict):
    from hub.services.project_group_service import setup_project_group

    team = body.get("team") or []
    project_name = body.get("project_name") or project_id
    ok, msg, group_id = await asyncio.to_thread(
        setup_project_group, project_id, team, project_name=project_name,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "group_id": group_id}


@projects_router.post("/{project_id}/group-message")
async def api_project_group_message(project_id: str, body: dict):
    from hub.services.project_group_service import format_progress_message, post_project_progress

    event_type = body.get("event_type", "group_notify")
    agent_id = body.get("agent_id", "")
    task_id = body.get("task_id", "")
    message = body.get("message", "").strip()
    extra = body.get("extra", "")

    if not message:
        message = format_progress_message(event_type, project_id, agent_id, task_id, extra)

    ok, result = await asyncio.to_thread(
        post_project_progress, project_id, message, sender=body.get("sender", "system"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail=result)
    return {"success": True, "group_id": result, "message": message}


@groups_router.get("/search")
async def api_search_groups(q: str = Query(""), include_dissolved: bool = True):
    return {"groups": search_groups(q, include_dissolved=include_dissolved)}


@groups_router.post("/{group_id}/dissolve")
async def api_dissolve_group(group_id: str):
    ok, msg = dissolve_group(group_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@groups_router.post("/{group_id}/restore")
async def api_restore_group(group_id: str):
    ok, msg = restore_group(group_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@groups_router.get("")
async def list_all_groups():
    return {"groups": list_groups()}


@groups_router.post("")
async def api_create_group(body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="群组名不能为空")
    group = create_group(name, body.get("description", ""), body.get("project_id"))
    return {"success": True, "group": group}


@groups_router.post("/{group_id}/bind-project")
async def api_bind_group_project(group_id: str, body: dict):
    project_id = body.get("project_id", "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")
    ok, msg = bind_group_project(group_id, project_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@groups_router.delete("/{group_id}")
async def api_delete_group(group_id: str):
    if not delete_group(group_id):
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"success": True}


@groups_router.get("/{group_id}")
async def api_get_group(group_id: str):
    g = get_group(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"group": g}


@groups_router.post("/{group_id}/members")
async def api_add_member(group_id: str, body: dict):
    agent_id = body.get("agent_id", "")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id 不能为空")
    ok, msg = add_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


def _reorder_group_members_response(group_id: str, body: dict) -> dict:
    member_ids = body.get("members")
    if not isinstance(member_ids, list):
        raise HTTPException(status_code=400, detail="members 必须是数组")
    ok, msg = reorder_group_members(group_id, member_ids)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    g = get_group(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"success": True, "message": msg, "group": g}


# 必须在 /members/{agent_id} 之前注册，否则旧路由会把 "order" 当成 agent_id → 405
@groups_router.post("/{group_id}/members/order")
async def api_reorder_group_members_post(group_id: str, body: dict):
    return _reorder_group_members_response(group_id, body)


@groups_router.put("/{group_id}/members/order")
async def api_reorder_group_members_put(group_id: str, body: dict):
    return _reorder_group_members_response(group_id, body)


@groups_router.delete("/{group_id}/members/{agent_id}")
async def api_remove_member(group_id: str, agent_id: str):
    ok, msg = remove_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@groups_router.post("/{group_id}/clear")
async def api_clear_group(group_id: str):
    ok, msg = clear_group_messages(group_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@groups_router.post("/{group_id}/roundtable-settings")
async def api_update_group_roundtable_settings(group_id: str, body: dict):
    facilitator = body.get("roundtable_facilitator")
    if facilitator is not None:
        facilitator = str(facilitator).strip()
    max_rounds = body.get("roundtable_max_rounds")
    if max_rounds is not None:
        try:
            max_rounds = int(max_rounds)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="roundtable_max_rounds 必须是整数")
    ok, msg = update_group_roundtable_settings(
        group_id,
        facilitator=facilitator,
        max_rounds=max_rounds,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    g = get_group(group_id)
    return {"success": True, "message": msg, "group": g}


@groups_router.get("/{group_id}/chat")
async def group_chat(
    request: Request,
    group_id: str,
    sender: str = Query("user", description="发送者"),
    text: str = Query(..., description="消息内容"),
    mode: str = Query("", description="roundtable | notify；留空则按 @all / @Agent 自动判定"),
    rounds: int | None = Query(None, description="圆桌最大轮数（覆盖群设置）"),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    if mode == "auto":
        mode = ""
    if mode and mode not in ("roundtable", "notify"):
        raise HTTPException(status_code=400, detail="mode 必须是 roundtable 或 notify")

    from hub.services.sse_bridge import stream_with_cancel
    from hub.services.chat_cancel import group_session_key, wrap_producer

    def produce_inner(cancel):
        try:
            for evt in send_group_message(
                group_id, sender, text, cancel_event=cancel, mode=mode,
                roundtable_rounds=rounds,
            ):
                yield json.dumps(evt, ensure_ascii=False)
        except Exception as e:
            yield json.dumps({"event": "error", "data": {"message": str(e)}}, ensure_ascii=False)

    async def event_stream():
        try:
            async for event_json in stream_with_cancel(
                request, wrap_producer(group_session_key(group_id), produce_inner)
            ):
                yield f"data: {event_json}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@groups_router.post("/{group_id}/cancel")
async def cancel_group_chat(group_id: str):
    from hub.services.chat_cancel import cancel_group_roundtable

    g = get_group(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="群组不存在")
    members = [m for m in (g.get("members") or []) if m != "user"]
    result = cancel_group_roundtable(group_id, members)
    return {"success": bool(result.get("cancelled") or result.get("killed_pids")), **result}


@groups_router.get("/{group_id}/chat/status")
async def group_chat_status(group_id: str):
    """后台圆桌/派活是否仍在运行（刷新后恢复 UI 状态）。"""
    from hub.services.chat_cancel import group_session_key, is_chat_active

    if not get_group(group_id):
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"active": is_chat_active(group_session_key(group_id))}


@groups_router.get("/{group_id}/events")
async def group_events_stream(request: Request, group_id: str):
    """订阅群组实时事件（任务 dispatch 时推送 agent_thinking）。"""
    from hub.services.group_broadcast import subscribe, unsubscribe

    if not get_group(group_id):
        raise HTTPException(status_code=404, detail="群组不存在")

    queue = subscribe(group_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            unsubscribe(group_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


router.include_router(groups_router)
router.include_router(projects_router)
