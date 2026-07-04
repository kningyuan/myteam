#!/usr/bin/env python3
"""agent_execution 互斥锁测试。"""
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent.agent_execution import agent_execution_lock  # noqa: E402


def test_nonblocking_rejects_when_held():
    with agent_execution_lock("agent-a", blocking=True) as outer:
        assert outer is True
        with agent_execution_lock("agent-a", blocking=False) as inner:
            assert inner is False


def test_different_agents_do_not_block():
    with agent_execution_lock("agent-a", blocking=True) as a:
        assert a is True
        with agent_execution_lock("agent-b", blocking=False) as b:
            assert b is True
