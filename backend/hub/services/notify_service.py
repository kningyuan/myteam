"""myteam 同步通知 — 供 team-ok bridge 调用。"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from threading import Event
from typing import Optional

from base.agent_chat import stream_chat
from base.group_manager import find_group_by_project, send_group_message
from hub.services.group_broadcast import publish
from hub.services.stream_fanout import fanout_stream_event


def _collect_text_and_write_file(agent_id: str, message: str, response_file: str, timeout: int) -> None:
    """后台收集 Agent 文本回复并写入 response_file（同时推送到私聊）。"""
    import json as _json
    import re as _re
    from threading import Event as _Event

    cancel = _Event()
    parts: list[str] = []
    thinking: list[dict] = []
    try:
        for sse_json in stream_chat(agent_id, message, cancel_event=cancel):
            # fanout_stream_event 会自动包装为 agent_thinking 推送到私聊 SSE
            fanout_stream_event(agent_id, sse_json)
            try:
                evt = _json.loads(sse_json)
            except _json.JSONDecodeError:
                continue
            event = evt.get("event")
            if event == "error":
                return
            if event == "thinking":
                data = evt.get("data") or {}
                if data.get("type") in ("step_start", "tool_use", "tool_result", "step_finish"):
                    thinking.append(data)
                elif data.get("type") == "text":
                    text = data.get("content", "")
                    if text:
                        parts.append(text)
                continue
            if event in ("text",):
                content = evt.get("data", {}).get("content", "")
                if content:
                    parts.append(content)
            if event == "done":
                break
    except Exception:
        return

    text = "".join(parts).strip()
    if not text:
        return

    json_match = _re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, _re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    try:
        parsed = _json.loads(text)
    except _json.JSONDecodeError:
        return

    # 原子写入：先写临时文件再 rename，避免执行器读取到不完整的内容
    tmp = response_file + ".tmp"
    Path(tmp).parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(parsed, f, ensure_ascii=False, indent=2)
    Path(tmp).rename(response_file)

    # 持久化私聊记录：写 .chat 文件，前端可通过 API 获取
    chat_text = "".join(parts).strip()
    if chat_text:
        from common.paths import WORKSPACES_DIR
        chat_dir = WORKSPACES_DIR / f"workspace-{agent_id}" / ".chats"
        chat_dir.mkdir(parents=True, exist_ok=True)
        chat_file = chat_dir / f"{Path(response_file).stem}.chat"
        _json.dump({
            "role": "agent",
            "content": chat_text,
            "thinking": thinking,
            "ts": int(time.time() * 1000),
            "background": True,
        }, open(chat_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def _collect_text_from_stream(agent_id: str, message: str, timeout: int, cancel_event: Event) -> tuple[bool, str]:
    """从 stream_chat 收集 Agent 文本回复。"""
    parts: list[str] = []
    error = ""

    try:
        for sse_json in stream_chat(agent_id, message, cancel_event=cancel_event):
            if cancel_event.is_set():
                return False, "Timeout: Agent 调用超时"
            try:
                evt = json.loads(sse_json)
            except json.JSONDecodeError:
                continue
            event = evt.get("event")
            if event == "error":
                error = evt.get("data", {}).get("message", "unknown error")
            elif event == "thinking":
                fanout_stream_event(agent_id, sse_json)
                data = evt.get("data") or {}
                if data.get("type") == "text":
                    text = data.get("content", "")
                    if text:
                        parts.append(text)
            elif event == "text":
                content = evt.get("data", {}).get("content", "")
                if content:
                    parts.append(content)
            elif event == "done":
                fanout_stream_event(agent_id, sse_json)
                break
    except Exception as e:
        return False, str(e)

    if error:
        return False, error
    return True, "".join(parts).strip()


def notify_agent_sync(
    agent_id: str,
    message: str,
    *,
    timeout: Optional[int] = None,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    wait_response: bool = True,
) -> tuple[bool, str]:
    """同步通知 Agent。wait_response=False 时仅投递消息。"""
    if timeout is None:
        from common.skill.skill_settings import agent_msg_timeout
        timeout = agent_msg_timeout()
    if not wait_response:
        cancel = Event()

        def _fire():
            try:
                for sse_json in stream_chat(agent_id, message, cancel_event=cancel):
                    fanout_stream_event(agent_id, sse_json)
            except Exception:
                pass

        t = threading.Thread(target=_fire, daemon=True)
        t.start()
        t.join(timeout=min(30, timeout))
        if t.is_alive():
            return True, ""
        return True, ""

    cancel = Event()

    def _watchdog():
        cancel.wait(timeout)

    threading.Thread(target=_watchdog, args=(timeout,), daemon=True).start()
    return _collect_text_from_stream(agent_id, message, timeout, cancel)


def notify_via_project_group(
    project_id: str,
    agent_id: str,
    message: str,
    task_id: Optional[str] = None,
) -> tuple[bool, str]:
    """在项目绑定群中 @Agent 投递任务通知（不等待完整响应）。"""
    group = find_group_by_project(project_id)
    prefix = f"@{agent_id}"
    if task_id:
        prefix = f"@{agent_id} [{task_id}]"
    text = f"{prefix} {message}".strip()

    if group:
        cancel = Event()
        delivered = False
        err = ""
        group_id = group["id"]
        try:
            for evt in send_group_message(
                group_id, "system", text, cancel_event=cancel, route_mentions=True, route_only=True,
            ):
                if evt.get("event") not in ("agent_thinking", "agent_done"):
                    publish(group_id, evt)
                if evt.get("event") == "routing" and evt.get("data", {}).get("to") == agent_id:
                    delivered = True
                elif evt.get("event") == "error":
                    err = evt.get("data", {}).get("message", "")
        except Exception as e:
            return False, str(e)
        if err:
            return False, err
        if delivered:
            return True, ""
        return True, ""

    return notify_agent_sync(
        agent_id,
        message,
        project_id=project_id,
        task_id=task_id,
        wait_response=False,
    )