#!/usr/bin/env python3
"""L1 后端注册表。"""
from __future__ import annotations

import logging
import os
from typing import Optional, Type

from memstack.config import l1_backend_name
from memstack.l1.mem0 import Mem0AgentMemory
from memstack.l1.native import NativeAgentMemory, clear_group_store_conversation
from memstack.l1.noop import NoopAgentMemory
from memstack.l1.sqlite import SqliteAgentMemory
from memstack.l1.protocol import AgentMemoryProvider, MemoryScope, memory_scope_group

logger = logging.getLogger("memstack.l1")

_L1_BACKENDS: dict[str, Type] = {
    "sqlite": SqliteAgentMemory,
    "native": NativeAgentMemory,
    "noop": NoopAgentMemory,
    "mem0": Mem0AgentMemory,
}


def list_l1_backends() -> list[str]:
    return sorted(_L1_BACKENDS.keys())


def get_agent_memory_provider(backend: Optional[str] = None) -> AgentMemoryProvider:
    name = (backend or l1_backend_name()).strip().lower()
    if not name:
        name = os.environ.get("AGENT_MEMORY_BACKEND", "sqlite")
    cls = _L1_BACKENDS.get(name)
    if cls is None:
        raise NotImplementedError(
            f"L1 后端 '{name}' 未注册。可用: {', '.join(list_l1_backends())}。"
        )
    return cls()


def clear_group_agent_memory(group_id: str, member_agent_ids: list[str]) -> None:
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
    clear_group_store_conversation(group_id)
