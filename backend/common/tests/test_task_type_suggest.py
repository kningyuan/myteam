#!/usr/bin/env python3
"""task_type_suggest — 规则推导，无 CLI。"""
from __future__ import annotations

import pytest

from common.task_type_suggest import (
    OUTCOME_KIND_CATALOG,
    suggest_task_type_from_description,
)


def test_suggest_research_from_chinese():
    r = suggest_task_type_from_description("对 GitHub 开源仓库做竞品调研")
    assert r["pattern"] == "research-survey"
    assert r["outcome_kind"] == "artifact"
    assert "调研背景" in r["required_sections"]
    assert r["engine"] == "rules"
    assert r["task_type"]


def test_suggest_code_project():
    r = suggest_task_type_from_description("实现一个可运行的脚本工具并交付")
    assert r["outcome_kind"] == "code_project"
    assert r["pattern"] in ("code-delivery", "code-writing")


def test_suggest_publish_action():
    r = suggest_task_type_from_description("文章发布到知乎并提交 URL 和截图")
    assert r["pattern"] == "publish-action"
    assert r["outcome_kind"] == "action"
    assert "已发布URL" in r["required_sections"]


def test_suggest_empty_raises():
    with pytest.raises(ValueError, match="描述"):
        suggest_task_type_from_description("  ")


def test_outcome_catalog_covers_three_kinds():
    ids = {o["id"] for o in OUTCOME_KIND_CATALOG}
    assert ids == {"artifact", "action", "code_project"}


def test_suggest_data_analysis():
    r = suggest_task_type_from_description("对用户留存做数据分析，输出指标口径和 SQL 报表")
    assert r["pattern"] == "data-analysis"
    assert r["outcome_kind"] == "artifact"


def test_suggest_geo_plan():
    r = suggest_task_type_from_description("制定 Perplexity GEO 优化策略")
    assert r["pattern"] == "geo-plan"
    assert "目标引擎" in " ".join(r["required_sections"])
