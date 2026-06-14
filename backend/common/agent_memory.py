#!/usr/bin/env python3
"""Agent 外挂记忆 — 可插拔 L1 工作记忆（与 common.memory 的 L3 KB 分离）。

当前默认 ``native``：沿用 OpenCode session 映射 + 按 scope 隔离 session key。
后续可换 ``nexsandglass`` 等后端，Hub 只调本模块，不绑具体实现。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger("agent_memory")

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
    """外挂记忆后端协议（L1 工作记忆，非团队 KB）。"""

    name: str

    def session_key(self, scope: MemoryScope) -> str:
        """OpenCode / Adapter 多轮 session 映射用的 workspace_key。"""
        ...

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        """回合开始前注入 prompt 的记忆块（空串表示不注入）。"""
        ...

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """回合结束后落盘 / 同步外挂记忆。"""
        ...

    def clear_scope(self, scope: MemoryScope) -> None:
        """清空该 scope 下的会话记忆（不清 L3 团队 KB）。"""
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


def _default_session_key(scope: MemoryScope) -> str:
    """native：DM 与群/圆桌分 session，避免圆桌污染私聊。"""
    mode = scope.normalized_mode()
    if mode in (_SCOPE_GROUP, _SCOPE_ROUNDTABLE) and scope.group_id:
        return f"group:{scope.group_id}:{scope.agent_id}"
    return f"workspace-{scope.agent_id}"


def _clear_opencode_sessions(agent_id: str, workspace_key: str) -> None:
    from store.sessions import session_store

    session_store.remove_for_agent_workspace(agent_id, workspace_key)


def _clear_group_store_conversation(group_id: str) -> None:
    if not group_id:
        return
    try:
        from common.store import Store

        store = Store()
        try:
            store.clear_conversation(f"group:{group_id}")
        finally:
            store.close()
    except Exception as e:
        logger.debug("clear group store conversation skipped: %s", e)


class NativeAgentMemory:
    """当前 myteam 行为 — session 按 scope 隔离，无额外 L1 检索。"""

    name = "native"

    def session_key(self, scope: MemoryScope) -> str:
        return _default_session_key(scope)

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        return ""

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        return None

    def clear_scope(self, scope: MemoryScope) -> None:
        ws = self.session_key(scope)
        _clear_opencode_sessions(scope.agent_id, ws)
        mode = scope.normalized_mode()
        if mode in (_SCOPE_GROUP, _SCOPE_ROUNDTABLE) and scope.group_id:
            _clear_group_store_conversation(scope.group_id)


class NoopAgentMemory:
    """禁用外挂记忆；session 仍走 legacy 全局 key（兼容旧调用）。"""

    name = "noop"

    def session_key(self, scope: MemoryScope) -> str:
        return f"workspace-{scope.agent_id}"

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        return ""

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        return None

    def clear_scope(self, scope: MemoryScope) -> None:
        return None


_PROVIDERS: dict[str, type] = {
    "native": NativeAgentMemory,
    "noop": NoopAgentMemory,
}


def get_agent_memory_provider(backend: Optional[str] = None) -> AgentMemoryProvider:
    """按 skill_config / 环境变量解析外挂记忆后端。"""
    name = backend
    if not name:
        try:
            from common.skill_settings import agent_memory_backend

            name = agent_memory_backend()
        except Exception:
            name = ""
    if not name:
        name = os.environ.get("AGENT_MEMORY_BACKEND", "native")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise NotImplementedError(
            f"Agent 外挂记忆后端 '{name}' 未实现。"
            f"可用: {', '.join(sorted(_PROVIDERS))}。"
        )
    return cls()


def clear_group_agent_memory(group_id: str, member_agent_ids: list[str]) -> None:
    """清空群 scoped 的 Agent session（清空群消息时调用，不动 DM / 团队 KB）。"""
    provider = get_agent_memory_provider()
    seen: set[str] = set()
    for agent_id in member_agent_ids:
        if not agent_id or agent_id == "user" or agent_id in seen:
            continue
        seen.add(agent_id)
        scope = memory_scope_group(group_id, agent_id)
        try:
            provider.clear_scope(scope)
        except Exception as e:
            logger.warning("clear_group_agent_memory %s/%s: %s", group_id, agent_id, e)
    _clear_group_store_conversation(group_id)


def inject_memory_hints(message: str, hint_block: str) -> str:
    block = (hint_block or "").strip()
    if not block:
        return message
    return f"{message}\n\n---\n【记忆召回】\n{block}"
