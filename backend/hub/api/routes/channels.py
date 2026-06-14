"""Workspace 频道路由（R2-2）。"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter

from hub.api.deps import we_store
from hub.api.errors import APIError

router = APIRouter(prefix="/api/workspace", tags=["channels"])


@router.get("/channels")
async def api_list_channels(project_id: str = ""):
    store = we_store()
    if project_id:
        conv = store.get_conversation(f"channel/project-{project_id}")
        channels = [conv] if conv else []
    else:
        channels = store.list_all_conversations()
    return {"channels": [
        {
            "channel_id": c.get("conversation_id", c.get("conversation_id", "")),
            "kind": c.get("kind", ""),
            "project_id": c.get("project_id", ""),
            "title": c.get("title", ""),
            "last_activity": c.get("updated_at", ""),
        }
        for c in channels
    ]}


@router.post("/channels")
async def api_create_channel(body: dict):
    kind = body.get("kind", "project")
    project_id = body.get("project_id", "")
    title = body.get("title", "新频道")
    channel_id = (
        f"channel/project-{project_id}"
        if kind == "project"
        else f"direct/{body.get('agent_id', '')}"
    )
    store = we_store()
    store.create_conversation(
        channel_id,
        kind=kind,
        participants=body.get("members", []),
        project_id=project_id,
        title=title,
    )
    return {"channel_id": channel_id, "created": True}


@router.get("/channels/{channel_id}/messages")
async def api_channel_messages(channel_id: str, limit: int = 50):
    if ".." in channel_id or "/" in channel_id.strip("/"):
        raise APIError("INVALID_CHANNEL", "channel_id 非法")
    store = we_store()
    msgs = store.list_messages(channel_id, limit=limit)
    return {"messages": msgs}


@router.post("/channels/{channel_id}/messages")
async def api_channel_post_message(channel_id: str, body: dict):
    if ".." in channel_id or "/" in channel_id.strip("/"):
        raise APIError("INVALID_CHANNEL", "channel_id 非法")
    store = we_store()
    from common.store import _now

    seq = store.append_message(
        channel_id,
        role="user" if body.get("author") != "agent" else "agent",
        author=body.get("author", "user"),
        text=body.get("content", ""),
    )
    content = body.get("content", "")
    mentions = [w.lstrip("@") for w in content.split() if w.startswith("@") and len(w) > 1]
    if mentions:
        store.append_workspace_event({
            "type": "chat.message.posted",
            "source": "hub/channel",
            "target": channel_id,
            "payload": json.dumps({
                "author": body.get("author"),
                "text": content,
                "mentions": mentions,
            }),
            "metadata": json.dumps({"channel_id": channel_id}),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    return {"message_id": seq, "seq": seq, "created_at": _now()}
