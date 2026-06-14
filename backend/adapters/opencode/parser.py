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

    elif event_type == "reasoning":
        text = part.get("text", "")
        if text:
            events.append(AgentEvent(EventKind.REASONING, {"content": text}))

    elif event_type == "tool_use":
        name = part.get("tool") or part.get("name") or ""
        state = part.get("state", {}) or {}
        tool_input = part.get("input")
        if tool_input is None:
            tool_input = state.get("input", {})
        payload = {"name": name, "input": json.dumps(tool_input, ensure_ascii=False)}
        # opencode 把工具返回放在同一个 tool_use 事件的 state.output（无独立 tool_result 事件）
        output = state.get("output", "")
        if output:
            payload["output"] = output if isinstance(output, str) \
                else json.dumps(output, ensure_ascii=False)
        if state.get("status"):
            payload["status"] = state["status"]
        events.append(AgentEvent(EventKind.TOOL_USE, payload))

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

    elif event_type == "error":
        err = raw.get("error") or {}
        msg = _opencode_error_message(err)
        events.append(AgentEvent(EventKind.ERROR, {"message": msg, "error": err}))

    return events


def _opencode_error_message(err) -> str:
    if isinstance(err, dict):
        data = err.get("data") or {}
        if isinstance(data, dict):
            for key in ("message", "detail", "error"):
                val = data.get(key)
                if val:
                    return str(val)
        for key in ("message", "name"):
            val = err.get(key)
            if val:
                return str(val)
    return str(err) if err else "opencode error"
