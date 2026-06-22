#!/usr/bin/env python3
"""L1 / registry 测试。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from memstack.l1.native import NativeAgentMemory
from memstack.l1.protocol import memory_scope_dm, memory_scope_group
from memstack.l1.registry import get_agent_memory_provider


def test_native_session_keys():
    p = NativeAgentMemory()
    assert p.session_key(memory_scope_dm("a1")) == "workspace-a1"
    assert p.session_key(memory_scope_group("g1", "a1")) == "group:g1:a1"


def test_get_agent_memory_provider_native():
    prov = get_agent_memory_provider("native")
    assert prov.name == "native"
    assert prov.before_turn(memory_scope_dm("x"), "hi") == ""
