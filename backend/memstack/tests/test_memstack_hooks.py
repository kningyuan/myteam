#!/usr/bin/env python3
"""Hook 集成 smoke — TC-2-01~03 桩。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from memstack.facade import enabled, inject_for_execute, on_chat_turn
from memstack.l1.protocol import memory_scope_dm
from memstack.l1.registry import get_agent_memory_provider
from memstack.orchestration.context import ChatTurnContext, ExecuteInjectContext


def test_chat_turn_baseline():
    scope = memory_scope_dm("product")
    msg = on_chat_turn(
        ChatTurnContext(scope=scope, message="hello", owner_id="product"),
        provider=get_agent_memory_provider("native"),
    )
    assert "hello" in msg


def test_inject_execute_baseline():
    lines: list[str] = []
    inject_for_execute(
        ExecuteInjectContext(lines=lines, project_id="p", task_type="research")
    )
    assert isinstance(lines, list)


def test_enabled_default_true():
    """memstack 默认启用（升级后默认 True）。"""
    assert enabled() is True
