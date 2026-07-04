#!/usr/bin/env python3
"""产出形态（三形态）单元测试。"""
from __future__ import annotations

import pytest

from common.gate.gate import check_code_project
from common.gate.registry import get_spec, invalidate_registry_cache, resolve_format_spec
from common.gate.task_type_suggest import list_outcome_kind_catalog
from common.gate.task_type_store import format_task_type_api


@pytest.fixture(autouse=True)
def _fresh_registry():
    invalidate_registry_cache()
    yield
    invalidate_registry_cache()


def test_outcome_kind_catalog_has_three_forms():
    kinds = list_outcome_kind_catalog()
    assert len(kinds) == 3
    ids = {k["id"] for k in kinds}
    assert ids == {"artifact", "action", "code_project"}
    for k in kinds:
        assert k.get("form_label_zh")
        assert k.get("gate_algorithm")


def test_publish_post_is_action_form():
    """publish-post 是 action 形态：有 evidence_url 配置。"""
    spec = get_spec("publish-post")
    assert spec is not None
    assert spec.outcome_kind == "action"


def test_research_is_artifact_form():
    """research 是 artifact 形态。"""
    spec = get_spec("research")
    assert spec is not None
    assert spec.outcome_kind == "artifact"
    assert "竞品调研" in (spec.display_name or "")


def test_code_deliverable_has_required_files():
    """code-deliverable 是 code_project 形态：要求项目文件数与代码文件。"""
    spec = get_spec("code-deliverable")
    assert spec is not None
    assert spec.outcome_kind == "code_project"
    assert spec.require_code_file or spec.min_project_files > 1


def test_code_deliverable_project_extensions(tmp_path):
    """code-deliverable 工程目录通过 check_code_project。"""
    spec = resolve_format_spec("code-deliverable")
    assert spec is not None
    proj = tmp_path / "bundle"
    proj.mkdir()
    (proj / "README.md").write_text("# cfg", encoding="utf-8")
    (proj / "main.py").write_text("print('hi')", encoding="utf-8")
    res = check_code_project(spec, proj)
    assert res.passed, res.failures


def test_publish_post_evidence_config():
    """publish-post 的 evidence 配置（host_contains/screenshot_field）。"""
    spec = resolve_format_spec("publish-post")
    assert spec is not None
    assert spec.evidence.get("host_contains") == "zhihu.com"
    assert spec.evidence.get("screenshot_field") == "证据截图"


def test_format_task_type_api_includes_form_label():
    """format_task_type_api 返回形态标签和门禁算法名。"""
    spec = get_spec("publish-post")
    api = format_task_type_api(spec)
    assert api["outcome_form_label"] == "证据态"
    assert api["gate_algorithm"] == "check_action_evidence"


def test_list_delivery_templates_includes_new_templates():
    from common.delivery.delivery_templates import list_delivery_template_ids

    ids = list_delivery_template_ids()
    assert "research-report" in ids
    assert "review-report" in ids
