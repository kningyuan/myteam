#!/usr/bin/env python3
from __future__ import annotations

import pytest

from common.agent.agent_task_type_suggest import suggest_task_types_for_agent


def test_suggest_analyst():
    r = suggest_task_types_for_agent("负责数据分析与 SQL 报表", name="数据分析师", agent_id="analyst")
    assert "data-analysis" in r["task_types"]


def test_suggest_geo():
    # 用现有 task_type（research）的关键词验证 suggest 机制
    r = suggest_task_types_for_agent("做竞品调研与分析", name="调研员", agent_id="research")
    assert "research" in r["task_types"]


def test_suggest_empty_raises():
    with pytest.raises(ValueError):
        suggest_task_types_for_agent("  ")
