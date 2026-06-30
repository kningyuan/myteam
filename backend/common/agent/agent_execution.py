"""Per-agent 执行互斥 — 编排 AgentPort 与 Hub 交互聊天共用。"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def lock_for(agent_id: str) -> threading.Lock:
    with _guard:
        if agent_id not in _locks:
            _locks[agent_id] = threading.Lock()
        return _locks[agent_id]


@contextmanager
def agent_execution_lock(agent_id: str, *, blocking: bool = True) -> Iterator[bool]:
    """获取 agent 执行锁。blocking=False 时拿不到锁立即 yield False。"""
    lock = lock_for(agent_id)
    acquired = lock.acquire(blocking=blocking)
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()
