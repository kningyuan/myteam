"""Workspace event feed routes (P3.1 Wave 4)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from hub.api.deps import we_store

router = APIRouter(tags=["workspace-events"])


@router.get("/api/workspace/events")
async def api_workspace_events(project_id: str = "", type: str = "", limit: int = 50):
    store = we_store()
    events = store.list_workspace_events(
        project_id=project_id or None,
        type=type or None,
        limit=min(limit, 200),
    )
    return {"events": events}


@router.get("/api/workspace/events/stream")
async def api_workspace_events_stream(request: Request, project_id: str = ""):
    """WorkspaceEvent SSE 流。轮询最新事件推送到前端。"""

    async def event_stream():
        last_id = ""
        while True:
            if await request.is_disconnected():
                break
            store = we_store()
            events = store.list_workspace_events(
                project_id=project_id or None,
                limit=20,
            )
            fresh = [e for e in events if e["id"] != last_id]
            if fresh:
                last_id = fresh[0]["id"]
                for e in reversed(fresh):
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
