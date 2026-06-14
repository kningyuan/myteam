#!/usr/bin/env python3
"""Agent 思考链轨迹 — SSE / run_event 统一 shape，供圆桌、私聊、项目 execute 复用。

UI 契约（ThinkingEvent）：
  step_start | tool_use | tool_result | step_finish | stream_text | milestone
"""
from __future__ import annotations

from typing import Any, Optional

TRACE_PART_TYPES = frozenset({"step_start", "tool_use", "tool_result", "step_finish", "reasoning"})
MAX_TRACE_PARTS = 120

# run_event 中不适合折叠进工具链、但需在时间线展示的里程碑
MILESTONE_RUN_KINDS = frozenset({
    "gate_failed",
    "gate_passed",
    "gate_retry_session",
    "review_done",
    "review_unreachable",
    "plan_rejected",
    "prompt_sent",
    "request_snapshot",
    "response_snapshot",
    "error",
    "transport_error",
    "watchdog_soft_idle",
    "watchdog_hard_kill",
    "deliverable_adopted",
    "resume_adopted",
})


def append_thinking_payload(
    data: dict,
    reply_parts: list[str],
    trace_parts: list[dict],
    *,
    max_parts: int = MAX_TRACE_PARTS,
) -> None:
    """合并单条 thinking.data（或等价 payload）到正文与轨迹。"""
    if not data:
        return
    t = data.get("type")
    if t == "text":
        content = data.get("content", "")
        if content:
            reply_parts.append(content)
            if (
                any(p.get("type") == "tool_use" for p in trace_parts)
                and len(trace_parts) < max_parts
            ):
                trace_parts.append({"type": "stream_text", "content": content})
        return
    if t in TRACE_PART_TYPES and len(trace_parts) < max_parts:
        trace_parts.append(dict(data))


def append_thinking_sse(
    evt: dict,
    reply_parts: list[str],
    trace_parts: list[dict],
    *,
    max_parts: int = MAX_TRACE_PARTS,
) -> None:
    """从 stream_chat SSE 事件收集正文与思考链。"""
    if evt.get("event") == "text":
        content = (evt.get("data") or {}).get("content", "")
        if content:
            reply_parts.append(content)
        return
    if evt.get("event") != "thinking":
        return
    append_thinking_payload(evt.get("data") or {}, reply_parts, trace_parts, max_parts=max_parts)


def thinking_from_run_event(kind: str, payload: Optional[dict] = None) -> Optional[dict]:
    """run_event(kind, payload) → UI ThinkingEvent（或 milestone）。"""
    k = (kind or "").strip()
    p = payload if isinstance(payload, dict) else {}
    if k == "text":
        content = p.get("content", "")
        return {"type": "stream_text", "content": content} if content else None
    if k == "reasoning":
        content = p.get("content", "")
        return {"type": "reasoning", "content": content} if content else None
    if k == "step_start":
        return {"type": "step_start"}
    if k == "tool_use":
        out: dict[str, Any] = {
            "type": "tool_use",
            "name": p.get("name") or p.get("tool") or "",
            "input": p.get("input"),
        }
        if p.get("output") is not None:
            out["output"] = p.get("output")
        if p.get("status"):
            out["status"] = p.get("status")
        return out
    if k == "tool_result":
        content = p.get("content", "")
        return {"type": "tool_result", "content": content} if content else None
    if k in ("step_finish", "step-finish"):
        return {
            "type": "step_finish",
            "reason": p.get("reason", ""),
            "tokens": p.get("tokens"),
        }
    if k in MILESTONE_RUN_KINDS:
        return {"type": "milestone", "kind": k, "payload": p}
    return None


def thinking_chain_from_run_events(events: list[dict]) -> list[dict]:
    """按 run_event 列表顺序生成 UI 思考链（含里程碑节点）。"""
    chain: list[dict] = []
    for ev in events:
        part = thinking_from_run_event(ev.get("kind", ""), ev.get("payload"))
        if part:
            chain.append(part)
    return chain
