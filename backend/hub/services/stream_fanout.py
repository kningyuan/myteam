"""将 stream_chat SSE 转为 agent_thinking 并广播到群组 / Agent Tab。"""

from __future__ import annotations

import json
from typing import Optional

from hub.services.agent_broadcast import publish as publish_agent
from hub.services.group_broadcast import publish as publish_group


def sse_to_thinking(evt: dict) -> Optional[dict]:
    if evt.get("event") == "thinking":
        return evt.get("data")
    return None


def fanout_stream_event(
    agent_id: str,
    sse_json: str,
    *,
    group_id: str = "",
    fanout_group: bool = True,
    reply_to: str = "",
) -> None:
    """解析单条 SSE JSON，广播 agent_thinking / done / error。"""
    try:
        evt = json.loads(sse_json)
    except json.JSONDecodeError:
        return

    event_name = evt.get("event")
    extra = {"reply_to": reply_to} if reply_to else {}
    if event_name == "thinking":
        data = evt.get("data") or {}
        payload = {"event": "agent_thinking", "data": {"agent_id": agent_id, **data, **extra}}
    elif event_name == "text":
        content = (evt.get("data") or {}).get("content", "") or ""
        if content:
            payload = {
                "event": "agent_thinking",
                "data": {"agent_id": agent_id, "type": "text", "content": content, **extra},
            }
        else:
            return
    elif event_name == "done":
        payload = {
            "event": "agent_done",
            "data": {"agent_id": agent_id, **(evt.get("data") or {}), **extra},
        }
    elif event_name == "error":
        payload = {"event": "error", "data": {**(evt.get("data") or {}), **extra}}
    else:
        thinking = sse_to_thinking(evt)
        if not thinking:
            return
        payload = {"event": "agent_thinking", "data": {"agent_id": agent_id, **thinking, **extra}}

    publish_agent(agent_id, payload)
    if group_id and fanout_group:
        publish_group(group_id, payload)
