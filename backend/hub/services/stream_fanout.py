"""将 stream_chat SSE 转为 agent_thinking 并广播到群组 / Agent Tab。"""

from __future__ import annotations

import json
from typing import Optional

from hub.services.agent_broadcast import publish as publish_agent
from hub.services.group_broadcast import publish as publish_group


def sse_to_thinking(evt: dict) -> Optional[dict]:
    if evt.get("event") == "thinking":
        return evt.get("data")
    if evt.get("event") != "raw":
        return None
    oc = evt.get("data", {}).get("opencode", {})
    t = oc.get("type", "")
    part = oc.get("part", {}) or {}
    if t in ("step_start", "step-start"):
        return {"type": "step_start"}
    if t == "text":
        return {"type": "text", "content": part.get("text", "")}
    if t == "tool_use":
        name = part.get("tool") or part.get("name") or ""
        inp = part.get("input")
        if inp is None:
            inp = part.get("state", {}).get("input", {})
        return {"type": "tool_use", "name": name, "input": json.dumps(inp, ensure_ascii=False)}
    if t == "tool_result":
        content = part.get("content") or part.get("state", {}).get("output", "")
        return {"type": "tool_result", "content": str(content)}
    if t in ("step_finish", "step-finish"):
        tokens = part.get("tokens") or {}
        return {"type": "step_finish", "tokens": tokens}
    return None


def fanout_stream_event(
    agent_id: str,
    sse_json: str,
    *,
    group_id: str = "",
) -> None:
    """解析单条 SSE JSON，广播 agent_thinking / done / error。"""
    try:
        evt = json.loads(sse_json)
    except json.JSONDecodeError:
        return

    event_name = evt.get("event")
    if event_name == "thinking":
        data = evt.get("data") or {}
        payload = {"event": "agent_thinking", "data": {"agent_id": agent_id, **data}}
    elif event_name == "done":
        payload = {"event": "agent_done", "data": {"agent_id": agent_id, **(evt.get("data") or {})}}
    elif event_name == "error":
        payload = {"event": "error", "data": evt.get("data") or {}}
    else:
        thinking = sse_to_thinking(evt)
        if not thinking:
            return
        payload = {"event": "agent_thinking", "data": {"agent_id": agent_id, **thinking}}

    publish_agent(agent_id, payload)
    if group_id:
        publish_group(group_id, payload)
