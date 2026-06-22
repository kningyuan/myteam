#!/usr/bin/env python3
"""Shim — L1 工作记忆实现已迁至 memstack.l1。"""
from __future__ import annotations

from memstack.l1 import (  # noqa: F401
    AgentMemoryProvider,
    MemoryScope,
    clear_group_agent_memory,
    get_agent_memory_provider,
    inject_memory_hints,
    memory_scope_dm,
    memory_scope_group,
    memory_scope_roundtable,
)
from memstack.l1.native import NativeAgentMemory  # noqa: F401

__all__ = [
    "AgentMemoryProvider",
    "MemoryScope",
    "NativeAgentMemory",
    "get_agent_memory_provider",
    "memory_scope_dm",
    "memory_scope_group",
    "memory_scope_roundtable",
    "clear_group_agent_memory",
    "inject_memory_hints",
]
