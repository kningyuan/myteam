#!/usr/bin/env python3
"""交付模板实例化 — 单元测试。

历史遗留测试曾期望 tds-ch3-product-planning / prd-lite 等早期模板，
现对齐当前模板集（research-report / review-report）与 task_type（research）。
机制不变：list/resolve/gate/goal_template/delete。
"""
from __future__ import annotations

import pytest

from common.delivery.delivery_templates import list_delivery_template_ids
from common.gate.gate import check_format
from common.runtime.goal_template import apply_goal_template_defaults, parse_goal_template_id
from common.gate.registry import get_spec, invalidate_registry_cache, resolve_format_spec


@pytest.fixture(autouse=True)
def _fresh_registry():
    invalidate_registry_cache()
    yield
    invalidate_registry_cache()


def test_list_delivery_templates():
    ids = list_delivery_template_ids()
    assert "research-report" in ids
    assert "review-report" in ids


def test_resolve_format_spec_research_report():
    """resolve_format_spec(task_type, template_id) 拿到模板约束。"""
    spec = resolve_format_spec("research", "research-report")
    assert spec is not None
    assert spec.template_id == "research-report"
    assert "调研背景" in spec.required_sections
    assert "关键发现" in spec.required_sections
    assert spec.stub_floor >= 200


def test_gate_format_research_report(tmp_path):
    """research-report 模板的强化约束（矩阵/维度/来源）通过 check_format。"""
    spec = resolve_format_spec("research", "research-report")
    content = (
        "# R\n\n## 调研背景\n足够具体的背景内容在此展开，覆盖核心功能、用户画像、"
        "变现模式、用户评价四维度调研目的与范围。\n\n"
        "## 信息来源\n| 来源 | 可信度 |\n|---|---|\n| [S1] A | 高 |\n\n"
        "## 关键发现\n"
        "| 对象 | 核心功能 | 用户画像 | 变现模式 | 用户评价 |\n|---|---|---|---|---|\n"
        "| A | X [S1] | P [S1] | 订阅 [S1] | 好 [S1] |\n\n"
        "核心功能与用户画像均有数据支撑。\n\n"
        "## 结论\n结论内容。\n"
    )
    md = tmp_path / "r.md"
    md.write_text(content, encoding="utf-8")
    res = check_format(spec, md.read_text(encoding="utf-8"), str(md))
    assert res.passed, res.failures


def test_resolve_format_spec_without_template_unchanged():
    """无 template_id 时回退到 default_for 模板（research → research-report）。

    base spec（get_spec）不挂模板；resolve_format_spec 即使无 template_id
    也会回退到 default_for=research 的模板拿到章节约束。
    """
    base = get_spec("research")
    resolved = resolve_format_spec("research", None)
    assert resolved is not None
    # base 不挂模板，resolved 回退到默认模板 → sections 更丰富
    assert len(resolved.required_sections) >= len(base.required_sections)
    assert resolved.template_id == "research-report"  # 回退到默认模板


def test_resolve_format_spec_research_report_constraints():
    """research-report 模板的强化约束字段被正确 resolve。"""
    spec = resolve_format_spec("research", "research-report")
    assert spec is not None
    assert spec.template_id == "research-report"
    assert spec.require_comparison_matrix is True
    assert spec.source_inline_required is True
    assert "核心功能" in spec.dimension_coverage
    assert "用户评价" in spec.dimension_coverage


def test_gate_format_missing_section_fails(tmp_path):
    """缺章节时 check_format 拦截。"""
    spec = resolve_format_spec("research", "research-report")
    content = "# R\n\n## 调研背景\n内容。\n"  # 缺信息来源/关键发现/结论
    res = check_format(spec, content)
    assert not res.passed
    rules = {f["rule"] for f in res.failures}
    assert "required_sections" in rules


def test_gate_format_stub_rejected():
    """stub 内容被拦截。"""
    spec = resolve_format_spec("research", "research-report")
    res = check_format(spec, "## 调研背景\n## 信息来源\n## 关键发现\n## 结论\nTODO")
    assert not res.passed
    assert any(f["rule"] == "stub" for f in res.failures)


def test_parse_goal_template_id():
    goal = "## 目标\n- template_id: research-report\n做竞品调研"
    assert parse_goal_template_id(goal) == "research-report"


def test_apply_goal_template_defaults():
    tasks = [{"id": "t1", "task_type": "research"}, {"id": "t2", "task_type": "research"}]
    out = apply_goal_template_defaults(tasks, "template_id: research-report")
    assert out[0]["template_id"] == "research-report"
    assert out[1]["template_id"] == "research-report"


def test_delete_template_blocked_when_workflow_references():
    from common.delivery.delivery_template_store import delete_template, workflows_using_template

    refs = workflows_using_template("research-report")
    if not refs:
        pytest.skip("无工作流引用 research-report")
    with pytest.raises(ValueError, match="仍被 Workflow 引用"):
        delete_template("research-report")


def test_list_templates_omits_missing_yaml(tmp_path, monkeypatch):
    from common.delivery.delivery_template_store import list_templates_for_api
    from common.delivery.delivery_templates import invalidate_delivery_templates_cache
    from common.paths import BUSINESS_DIR

    fp = BUSINESS_DIR / "delivery_templates" / "tmp-list-ghost.yaml"
    fp.write_text(
        "id: tmp-list-ghost\ndisplay_name: g\ntask_types: [research]\n"
        "deliverable_template:\n  sections:\n    - {name: x, required: true}\n"
        "check_rules:\n  required_sections: [x]\n",
        encoding="utf-8",
    )
    invalidate_delivery_templates_cache()
    try:
        assert "tmp-list-ghost" in [t["id"] for t in list_templates_for_api()]
        fp.unlink()
        invalidate_delivery_templates_cache()
        assert "tmp-list-ghost" not in [t["id"] for t in list_templates_for_api()]
    finally:
        if fp.is_file():
            fp.unlink()
        invalidate_delivery_templates_cache()
