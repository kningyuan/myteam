"""DM chat routes (P3.1 Wave 3)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from base.agent_chat import clear_agent_chat_context, stream_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/{agent_id}")
async def chat(request: Request, agent_id: str, message: str = Query(..., description="用户消息")):
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    from hub.services.sse_bridge import stream_background_on_disconnect
    from hub.services.chat_cancel import agent_session_key, wrap_producer_background

    def produce_inner(cancel):
        try:
            for event_json in stream_chat(
                agent_id, message.strip(), cancel_event=cancel, use_memory=True
            ):
                yield event_json
        except Exception as e:
            yield json.dumps({"event": "error", "data": {"message": str(e)}}, ensure_ascii=False)

    async def event_stream():
        try:
            async for event_json in stream_background_on_disconnect(
                request,
                wrap_producer_background(agent_session_key(agent_id), produce_inner),
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


@router.post("/{agent_id}/cancel")
async def cancel_agent_chat(agent_id: str):
    from hub.services.chat_cancel import agent_session_key, cancel_chat

    return {"success": cancel_chat(agent_session_key(agent_id))}


@router.get("/{agent_id}/status")
async def api_chat_status(agent_id: str):
    """私聊流是否仍在运行（刷新后恢复「思考中」UI）。"""
    from hub.services.chat_cancel import agent_session_key, is_chat_active

    return {"active": is_chat_active(agent_session_key(agent_id))}


@router.get("/{agent_id}/messages")
async def api_chat_messages(agent_id: str, limit: int = Query(200, ge=1, le=2000)):
    """DM 会话历史（P0 记忆地基）——从 Store 的 message 表读，前端据此渲染对话流。"""
    from common.store import Store

    store = Store()
    try:
        conv_id = f"dm:{agent_id}"
        msgs = store.list_messages(conv_id)
        if limit and len(msgs) > limit:
            msgs = msgs[-limit:]
        out = []
        for m in msgs:
            meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
            thinking = meta.get("thinking") if isinstance(meta.get("thinking"), list) else None
            out.append({
                "seq": m["seq"], "role": m["role"], "author": m.get("author", ""),
                "text": m.get("text", ""), "parts": m.get("parts"),
                "created_at": m.get("created_at", ""),
                "thinking": thinking,
            })
    finally:
        store.close()
    return {"agent_id": agent_id, "conversation_id": conv_id, "messages": out}


@router.post("/{agent_id}/clear")
async def api_clear_chat(agent_id: str):
    ok, msg = clear_agent_chat_context(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@router.post("/{agent_id}/archive")
async def api_archive_chat(agent_id: str, body: dict):
    from hub.services.chat_archive import hide_chat

    snapshot = body.get("snapshot")
    entry = hide_chat(agent_id, snapshot)
    return {"success": True, "entry": entry}


@router.post("/{agent_id}/restore")
async def api_restore_chat(agent_id: str):
    from hub.services.chat_archive import restore_chat

    ok, msg, snapshot = restore_chat(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg, "snapshot": snapshot}


@router.get("/archives/search")
async def api_search_chat_archives(q: str = Query("")):
    from hub.services.chat_archive import search_archives

    return {"results": search_archives(q)}
