#!/usr/bin/env python3
"""noop L1 后端 — 禁用外挂记忆。"""
from __future__ import annotations

from memstack.l1.protocol import MemoryScope


class NoopAgentMemory:
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
