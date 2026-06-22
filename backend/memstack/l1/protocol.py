#!/usr/bin/env python3
"""L1 工作记忆 Protocol — Framework 层定义。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_SCOPE_DM = "dm"
_SCOPE_GROUP = "group"
_SCOPE_ROUNDTABLE = "roundtable"
_SCOPE_EXECUTE = "execute"


@dataclass(frozen=True)
class MemoryScope:
    """一次 Agent 交互的记忆作用域。"""

    agent_id: str
    mode: str = _SCOPE_DM
    group_id: str = ""
    project_id: str = ""

    def normalized_mode(self) -> str:
        m = (self.mode or _SCOPE_DM).strip().lower()
        if m in (_SCOPE_GROUP, _SCOPE_ROUNDTABLE, _SCOPE_EXECUTE, _SCOPE_DM):
            return m
        return _SCOPE_DM


@runtime_checkable
class AgentMemoryProvider(Protocol):
    """L1 工作记忆后端（非团队 KB）。"""

    name: str

    def session_key(self, scope: MemoryScope) -> str:
        ...

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        ...

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        ...

    def clear_scope(self, scope: MemoryScope) -> None:
        ...


def memory_scope_dm(agent_id: str) -> MemoryScope:
    return MemoryScope(agent_id=agent_id, mode=_SCOPE_DM)


def memory_scope_group(group_id: str, agent_id: str, *, project_id: str = "") -> MemoryScope:
    return MemoryScope(
        agent_id=agent_id,
        mode=_SCOPE_GROUP,
        group_id=group_id,
        project_id=project_id,
    )


def memory_scope_roundtable(group_id: str, agent_id: str, *, project_id: str = "") -> MemoryScope:
    return MemoryScope(
        agent_id=agent_id,
        mode=_SCOPE_ROUNDTABLE,
        group_id=group_id,
        project_id=project_id,
    )


def memory_scope_execute(agent_id: str, *, project_id: str = "", task_id: str = "") -> MemoryScope:
    return MemoryScope(
        agent_id=agent_id,
        mode=_SCOPE_EXECUTE,
        project_id=project_id or "",
    )


def inject_memory_hints(message: str, hint_block: str) -> str:
    block = (hint_block or "").strip()
    if not block:
        return message
    return f"{message}\n\n---\n【记忆召回】\n{block}"
