#!/usr/bin/env python3
from __future__ import annotations

import pytest

from common.agent_task_type_suggest import suggest_task_types_for_agent


def test_suggest_analyst():
    r = suggest_task_types_for_agent("负责数据分析与 SQL 报表", name="数据分析师", agent_id="analyst")
    assert "data-analysis" in r["task_types"]


def test_suggest_geo():
    r = suggest_task_types_for_agent("GEO 与 Perplexity 可见性", name="GEO专家", agent_id="geo")
    assert "geo-plan" in r["task_types"]


def test_suggest_empty_raises():
    with pytest.raises(ValueError):
        suggest_task_types_for_agent("  ")
