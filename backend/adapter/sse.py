"""AgentEvent → SSE JSON 线协议（UI 消费）。"""

import json

from adapter.events import AgentEvent, EventKind


def encode_event(event: AgentEvent) -> str | None:
    if event.kind == EventKind.ERROR:
        return encode_error(event.data.get("message", ""))
    if event.kind == EventKind.SESSION:
        return None
    payload = event.to_thinking_payload()
    if payload is None:
        return None
    return json.dumps({"event": "thinking", "data": payload}, ensure_ascii=False)


def encode_error(message: str) -> str:
    return json.dumps({"event": "error", "data": {"message": message}}, ensure_ascii=False)


def encode_done(session_id: str = "") -> str:
    return json.dumps({"event": "done", "data": {"session_id": session_id}}, ensure_ascii=False)
