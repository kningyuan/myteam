"""项目群实时事件广播 — 任务 dispatch 时向已打开的群组 Tab 推送 agent_thinking。"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_listeners: dict[str, list[asyncio.Queue[str | None]]] = defaultdict(list)


def subscribe(group_id: str) -> asyncio.Queue[str | None]:
    q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=300)
    with _lock:
        _listeners[group_id].append(q)
    return q


def unsubscribe(group_id: str, q: asyncio.Queue[str | None]) -> None:
    with _lock:
        lst = _listeners.get(group_id, [])
        if q in lst:
            lst.remove(q)


def publish(group_id: str, event: dict[str, Any]) -> None:
    if not group_id:
        return
    payload = json.dumps(event, ensure_ascii=False)
    with _lock:
        dead: list[asyncio.Queue[str | None]] = []
        for q in _listeners.get(group_id, []):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _listeners[group_id].remove(q)
