#!/usr/bin/env python3
"""Mem0 L1 adapter — 有 API key 时用 Mem0，否则降级 sqlite L1。"""
from __future__ import annotations

import logging
import os

from memstack.config import vendor_path
from memstack.l1.protocol import MemoryScope
from memstack.l1.sqlite import SqliteAgentMemory

logger = logging.getLogger("memstack.l1.mem0")

_CLIP = 400


def _clip(text: str, n: int = _CLIP) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


class Mem0AgentMemory:
    """Mem0 云/ SDK；不可用时自动使用 sqlite L1（仍可用）。"""

    name = "mem0"

    def __init__(self) -> None:
        self._client = None
        self._fallback = SqliteAgentMemory()
        api_key = os.environ.get("MEM0_API_KEY", "").strip()
        if not api_key and not vendor_path("mem0").is_dir():
            logger.info("Mem0 未配置，L1 使用 sqlite 降级")
            return
        try:
            from mem0 import MemoryClient

            self._client = MemoryClient(api_key=api_key) if api_key else None
            if self._client is None:
                from mem0 import Memory

                self._client = Memory()
        except ImportError:
            logger.info("mem0ai 未安装 (pip install mem0ai)，L1 使用 sqlite 降级")
        except Exception as e:
            logger.warning("Mem0 初始化失败，L1 使用 sqlite 降级: %s", e)

    @property
    def _use_fallback(self) -> bool:
        return self._client is None

    def _mem0_user_id(self, scope: MemoryScope) -> str:
        parts = [scope.agent_id, scope.normalized_mode()]
        if scope.group_id:
            parts.append(scope.group_id)
        return ":".join(p for p in parts if p)

    def session_key(self, scope: MemoryScope) -> str:
        return self._fallback.session_key(scope)

    def before_turn(self, scope: MemoryScope, user_text: str) -> str:
        if self._use_fallback:
            return self._fallback.before_turn(scope, user_text)
        try:
            user_id = self._mem0_user_id(scope)
            query = (user_text or "").strip() or "recent context"
            if hasattr(self._client, "search"):
                raw = self._client.search(
                    query,
                    user_id=user_id,
                    agent_id=scope.agent_id,
                )
            else:
                raw = self._client.search(
                    query,
                    filters={"user_id": user_id},
                )
            memories = raw if isinstance(raw, list) else raw.get("results", raw.get("memories", []))
            lines = []
            for item in memories[:5]:
                if isinstance(item, dict):
                    text = item.get("memory") or item.get("text") or item.get("content") or ""
                else:
                    text = str(item)
                text = _clip(str(text))
                if text:
                    lines.append(f"- {text}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Mem0 before_turn failed, fallback sqlite: %s", e)
            return self._fallback.before_turn(scope, user_text)

    def after_turn(
        self,
        scope: MemoryScope,
        user_text: str,
        assistant_text: str,
    ) -> None:
        if self._use_fallback:
            self._fallback.after_turn(scope, user_text, assistant_text)
            return
        user = (user_text or "").strip()
        assistant = (assistant_text or "").strip()
        if not user and not assistant:
            return
        try:
            user_id = self._mem0_user_id(scope)
            messages = []
            if user:
                messages.append({"role": "user", "content": user})
            if assistant:
                messages.append({"role": "assistant", "content": assistant})
            if hasattr(self._client, "add"):
                self._client.add(
                    messages,
                    user_id=user_id,
                    agent_id=scope.agent_id,
                )
        except Exception as e:
            logger.warning("Mem0 after_turn failed, fallback sqlite: %s", e)
            self._fallback.after_turn(scope, user_text, assistant_text)

    def clear_scope(self, scope: MemoryScope) -> None:
        if not self._use_fallback:
            try:
                user_id = self._mem0_user_id(scope)
                if hasattr(self._client, "delete_all"):
                    self._client.delete_all(user_id=user_id, agent_id=scope.agent_id)
            except Exception as e:
                logger.warning("Mem0 clear_scope: %s", e)
        self._fallback.clear_scope(scope)
