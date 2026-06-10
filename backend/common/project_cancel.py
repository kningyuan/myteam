#!/usr/bin/env python3
"""项目级取消信号 — Hub API cancel 与 AgentPort 子进程联动。"""
from __future__ import annotations

import threading
import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.agent_port import DeliveryContext


class ProjectCancelRegistry:
    """同一 Hub 进程内：project cancel → 所有活跃 DeliveryContext 收到 cancel_event。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags: dict[str, threading.Event] = {}
        self._contexts: dict[str, list[weakref.ref]] = {}

    def register(self, project_id: str) -> None:
        with self._lock:
            self._flags.setdefault(project_id, threading.Event())

    def is_cancelled(self, project_id: str) -> bool:
        with self._lock:
            ev = self._flags.get(project_id)
            return bool(ev and ev.is_set())

    def cancel(self, project_id: str) -> None:
        with self._lock:
            ev = self._flags.setdefault(project_id, threading.Event())
            ev.set()
            for ref in list(self._contexts.get(project_id, [])):
                ctx = ref()
                if ctx is not None:
                    ctx._cancel.set()

    def attach(self, project_id: str, ctx: DeliveryContext) -> None:
        if not project_id:
            return
        with self._lock:
            refs = self._contexts.setdefault(project_id, [])
            refs.append(weakref.ref(ctx))
            ev = self._flags.get(project_id)
            if ev and ev.is_set():
                ctx._cancel.set()

    def clear(self, project_id: str) -> None:
        with self._lock:
            self._flags.pop(project_id, None)
            self._contexts.pop(project_id, None)


cancel_registry = ProjectCancelRegistry()
