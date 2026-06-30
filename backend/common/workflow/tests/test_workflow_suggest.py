#!/usr/bin/env python3
from __future__ import annotations

import pytest

from common.workflow.workflow_suggest import suggest_workflow_from_description


def test_suggest_github_parallel():
    out = suggest_workflow_from_description("对 GitHub 开源项目做三视角调研并汇总")
    assert out["pattern"] == "github-parallel-research"
    tasks = out["workflow"]["tasks"]
    assert len(tasks) == 4
    assert out["workflow"]["options"]["parallel_enabled"] is True
    assert tasks[-1]["task_type"] == "strategy"


def test_suggest_smoke():
    out = suggest_workflow_from_description("最小冒烟调研")
    assert out["pattern"] == "smoke-research"
    assert len(out["workflow"]["tasks"]) == 2


def test_suggest_empty_raises():
    with pytest.raises(ValueError):
        suggest_workflow_from_description("   ")


def test_suggest_default_linear():
    out = suggest_workflow_from_description("完成某主题调研报告")
    assert out["pattern"] == "linear-research"
    assert len(out["workflow"]["tasks"]) == 2


def test_suggest_data_analysis():
    out = suggest_workflow_from_description("对用户留存做数据分析并输出 SQL 报表")
    assert out["pattern"] == "data-analysis-pipeline"
    agents = {t["agent"] for t in out["workflow"]["tasks"]}
    assert "analyst" in agents


def test_suggest_geo():
    out = suggest_workflow_from_description("制定 Perplexity GEO 优化策略并验证")
    assert out["pattern"] == "geo-pipeline"
    assert any(t["task_type"] == "geo-plan" for t in out["workflow"]["tasks"])


def test_suggest_delivery_uses_developer_for_impl():
    out = suggest_workflow_from_description("轻量软件交付与实现")
    impl = next(t for t in out["workflow"]["tasks"] if t["id"] == "t-implement")
    assert impl["agent"] == "developer"
    assert impl["task_type"] == "code-writing"
