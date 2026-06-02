"""OpenCode NDJSON → 统一 AgentEvent（唯一允许 OpenCode 格式耦合处）。"""

import json
from typing import Any

from adapter.events import AgentEvent, EventKind


def parse_line(line: str) -> list[AgentEvent]:
    """解析 OpenCode --format json 的一行 stdout。"""
    line = line.strip()
    if not line:
        return []
    try:
        raw: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError:
        return []

    event_type = raw.get("type", "")
    part = raw.get("part") or {}
    events: list[AgentEvent] = []

    sid = raw.get("sessionID")
    if sid:
        events.append(AgentEvent(EventKind.SESSION, {"session_id": sid}))

    if event_type in ("step_start", "step-start"):
        events.append(AgentEvent(EventKind.STEP_START, {}))

    elif event_type == "text":
        text = part.get("text", "")
        if text:
            events.append(AgentEvent(EventKind.TEXT, {"content": text}))

    elif event_type == "tool_use":
        name = part.get("tool") or part.get("name") or ""
        tool_input = part.get("input")
        if tool_input is None:
            tool_input = part.get("state", {}).get("input", {})
        events.append(AgentEvent(
            EventKind.TOOL_USE,
            {"name": name, "input": json.dumps(tool_input, ensure_ascii=False)},
        ))

    elif event_type == "tool_result":
        content = part.get("content", "")
        if not content:
            content = part.get("state", {}).get("output", "")
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        if content:
            events.append(AgentEvent(EventKind.TOOL_RESULT, {"content": str(content)}))

    elif event_type in ("step_finish", "step-finish"):
        tokens = part.get("tokens") or {}
        events.append(AgentEvent(
            EventKind.STEP_FINISH,
            {
                "reason": part.get("reason", ""),
                "tokens": {
                    "input": tokens.get("input", 0),
                    "output": tokens.get("output", 0),
                    "total": tokens.get("total", 0),
                    "reasoning": tokens.get("reasoning", 0),
                },
            },
        ))

    return events
