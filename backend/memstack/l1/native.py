#!/usr/bin/env python3
"""native L1 后端 — session 按 scope 隔离，无额外检索。"""
from __future__ import annotations

import logging

from memstack.l1.protocol import MemoryScope

logger = logging.getLogger("memstack.l1.native")

_SCOPE_GROUP = "group"
_SCOPE_ROUNDTABLE = "roundtable"


def default_session_key(scope: MemoryScope) -> str:
    mode = scope.normalized_mode()
    if mode in (_SCOPE_GROUP, _SCOPE_ROUNDTABLE) and scope.group_id:
        return f"group:{scope.group_id}:{scope.agent_id}"
    return f"workspace-{scope.agent_id}"


def _clear_opencode_sessions(agent_id: str, workspace_key: str) -> None:
    from store.sessions import session_store

    session_store.remove_for_agent_workspace(agent_id, workspace_key)


def clear_group_store_conversation(group_id: str) -> None:
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
    name = "native"

    def session_key(self, scope: MemoryScope) -> str:
        return default_session_key(scope)

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
            clear_group_store_conversation(scope.group_id)
