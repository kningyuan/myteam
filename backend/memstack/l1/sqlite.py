#!/usr/bin/env python3
"""sqlite L1 工作记忆 — 默认可用后端（无需外部 SaaS）。"""
from __future__ import annotations

import logging
from typing import Optional

from common.store import Store
from memstack.l1.native import NativeAgentMemory, clear_group_store_conversation, default_session_key
from memstack.l1.protocol import MemoryScope

logger = logging.getLogger("memstack.l1.sqlite")

L1_PROJECT_ID = "__memstack_l1__"
_MAX_HINT_ENTRIES = 5
_CLIP = 320


def _clip(text: str, n: int = _CLIP) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def scope_tags(scope: MemoryScope) -> list[str]:
    tags = ["l1", scope.normalized_mode(), f"agent:{scope.agent_id}"]
    if scope.group_id:
        tags.append(f"group:{scope.group_id}")
    if scope.project_id:
        tags.append(f"project:{scope.project_id}")
    return tags


class SqliteAgentMemory:
    """L1 工作记忆：store.memory 表，按 scope 标签隔离。"""

    name = "sqlite"

    def __init__(self, store: Optional[Store] = None) -> None:
        self._store = store or Store()
        self._native = NativeAgentMemory()

    def session_key(self, scope: MemoryScope) -> str:
        return default_session_key(scope)

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        tags = scope_tags(scope)
        query = (user_text or "").strip()
        try:
            hits = self._store.memory_search(
                tags=tags,
                text=query[:200] if query else "",
                project_id=L1_PROJECT_ID,
            )
            hits = [
                e for e in hits
                if set(tags).issubset(set(e.get("tags") or []))
            ]
            if not hits and query:
                hits = self._store.memory_search(
                    tags=tags,
                    project_id=L1_PROJECT_ID,
                )
                hits = [
                    e for e in hits
                    if set(tags).issubset(set(e.get("tags") or []))
                ]
            if not hits:
                return ""
            lines = []
            seen: set[str] = set()
            for entry in hits[: _MAX_HINT_ENTRIES * 2]:
                body = _clip(entry.get("content") or "")
                if not body or body in seen:
                    continue
                seen.add(body)
                lines.append(f"- {body}")
                if len(lines) >= _MAX_HINT_ENTRIES:
                    break
            return "\n".join(lines)
        except Exception as e:
            logger.warning("sqlite L1 before_turn: %s", e)
            return ""

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        user = (user_text or "").strip()
        assistant = (assistant_text or "").strip()
        if not user and not assistant:
            return
        content = f"User: {_clip(user, 400)}\nAssistant: {_clip(assistant, 400)}"
        title = f"turn:{scope.agent_id}:{scope.normalized_mode()}"
        try:
            self._store.memory_write(
                L1_PROJECT_ID,
                title,
                content,
                tags=scope_tags(scope),
            )
        except Exception as e:
            logger.warning("sqlite L1 after_turn: %s", e)

    def clear_scope(self, scope: MemoryScope) -> None:
        tags = scope_tags(scope)
        try:
            for entry in self._store.memory_search(tags=tags, project_id=L1_PROJECT_ID):
                mid = entry.get("id")
                if mid is not None:
                    self._store.memory_delete(int(mid))
        except Exception as e:
            logger.warning("sqlite L1 clear_scope: %s", e)
        self._native.clear_scope(scope)
        mode = scope.normalized_mode()
        if mode in ("group", "roundtable") and scope.group_id:
            clear_group_store_conversation(scope.group_id)
