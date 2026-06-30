"""Claude Code CLI stream-json → 统一 AgentEvent（唯一允许 Claude Code 格式耦合处）。

行格式（--output-format stream-json --verbose）：
  - {"type":"system","subtype":"init","session_id":"...","model":"..."}
  - {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
  - {"type":"assistant","message":{"content":[{"type":"thinking","thinking":"..."}]}}
  - {"type":"assistant","message":{"content":[{"type":"tool_use","name":"...","input":{...}}]}}
  - {"type":"result","subtype":"success","result":"...","usage":{...}}
  - {"type":"result","subtype":"error","is_error":true,...}
"""

import json
from typing import Any

from adapter.core.events import AgentEvent, EventKind


def _num(v) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    return 0


def _thinking_text(block: dict) -> str:
    """从 assistant content 块提取可读思考文本（兼容 thinking / redacted_thinking）。"""
    for key in ("thinking", "text", "summary"):
        val = block.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_usage_tokens(raw: dict) -> dict:
    """从 Claude stream-json result 行提取 token 计量（兼容多种字段名）。"""
    usage = raw.get("usage") or {}
    model_usage = raw.get("modelUsage") or raw.get("model_usage") or {}

    inp = _num(usage.get("input_tokens") or usage.get("inputTokens"))
    out = _num(usage.get("output_tokens") or usage.get("outputTokens"))
    total = _num(usage.get("total_tokens") or usage.get("totalTokens"))

    for _mid, mu in (model_usage.items() if isinstance(model_usage, dict) else []):
        if not isinstance(mu, dict):
            continue
        cand = _num(mu.get("inputTokens")) + _num(mu.get("outputTokens"))
        total = max(total, cand)

    if not total:
        total = inp + out
    return {"input": inp, "output": out, "total": total}


def parse_line(line: str) -> list[AgentEvent]:
    """解析 Claude Code stream-json 的一行 stdout，返回 0~N 个事件。"""
    line = line.strip()
    if not line:
        return []
    try:
        raw: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError:
        return []

    events: list[AgentEvent] = []

    event_type = raw.get("type", "")

    if event_type == "system":
        subtype = raw.get("subtype", "")
        if subtype == "init":
            sid = raw.get("session_id", "")
            model = raw.get("model", "")
            data: dict[str, Any] = {}
            if sid:
                data["session_id"] = sid
            if model:
                data["model"] = model
            events.append(AgentEvent(EventKind.SESSION, data))

    elif event_type == "assistant":
        msg = raw.get("message") or {}
        contents = msg.get("content") or []
        for c in contents:
            ctype = c.get("type", "")
            if ctype == "text":
                text = c.get("text", "")
                if text:
                    events.append(AgentEvent(EventKind.TEXT, {"content": text}))
            elif ctype in ("thinking", "redacted_thinking"):
                text = _thinking_text(c)
                if text:
                    events.append(AgentEvent(EventKind.REASONING, {"content": text}))
            elif ctype == "tool_use":
                name = c.get("name", "")
                tool_input = c.get("input", {})
                payload = {
                    "name": name,
                    "input": json.dumps(tool_input, ensure_ascii=False),
                }
                result = c.get("result")
                if result:
                    payload["output"] = json.dumps(result, ensure_ascii=False)
                events.append(AgentEvent(EventKind.TOOL_USE, payload))
        usage = msg.get("usage") or {}
        inp = _num(usage.get("input_tokens") or usage.get("inputTokens"))
        out = _num(usage.get("output_tokens") or usage.get("outputTokens"))
        if inp or out:
            events.append(AgentEvent(EventKind.STEP_FINISH, {
                "reason": "assistant_message",
                "cumulative": False,
                "tokens": {"input": inp, "output": out, "total": inp + out},
            }))

    elif event_type == "result":
        subtype = raw.get("subtype", "")
        if subtype == "error" or raw.get("is_error"):
            msg = raw.get("result", raw.get("error", "未知错误"))
            events.append(AgentEvent(EventKind.ERROR, {"message": str(msg)}))
        else:
            result_text = raw.get("result", "")
            if isinstance(result_text, str) and result_text.strip():
                # 工具型回合可能无 assistant 文本块，最终答复仅在 result 行
                events.append(AgentEvent(EventKind.TEXT, {
                    "content": result_text.strip(),
                    "source": "result",
                }))
            events.append(AgentEvent(EventKind.STEP_FINISH, {
                "reason": "completed",
                "cumulative": True,
                "tokens": _extract_usage_tokens(raw),
            }))

    return events
