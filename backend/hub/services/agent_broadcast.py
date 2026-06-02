"""Agent 实时事件广播 — 任务执行时向 Agent 私聊 Tab 推送 thinking（对标 openclaw send_to_user）。"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_listeners: dict[str, list[asyncio.Queue[str | None]]] = defaultdict(list)


def subscribe(agent_id: str) -> asyncio.Queue[str | None]:
    q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=300)
    with _lock:
        _listeners[agent_id].append(q)
    return q


def unsubscribe(agent_id: str, q: asyncio.Queue[str | None]) -> None:
    with _lock:
        lst = _listeners.get(agent_id, [])
        if q in lst:
            lst.remove(q)


def publish(agent_id: str, event: dict[str, Any]) -> None:
    if not agent_id:
        return
    payload = json.dumps(event, ensure_ascii=False)
    with _lock:
        dead: list[asyncio.Queue[str | None]] = []
        for q in _listeners.get(agent_id, []):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _listeners[agent_id].remove(q)
