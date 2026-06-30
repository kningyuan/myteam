#!/usr/bin/env python3
"""交付模板实例化 — 单元测试。"""
from __future__ import annotations

import pytest

from common.delivery.delivery_templates import DeliveryTemplateError, list_delivery_template_ids, load_delivery_template
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
    assert "tds-ch3-product-planning" in ids
    assert "prd-lite" in ids


def test_resolve_format_spec_prd_lite():
    spec = resolve_format_spec("requirements", "prd-lite")
    assert spec is not None
    assert spec.template_id == "prd-lite"
    assert spec.required_sections == ["背景与目标", "范围", "用户故事与验收标准"]
    assert spec.stub_floor >= 400


def test_gate_format_prd_lite(tmp_path):
    spec = resolve_format_spec("requirements", "prd-lite")
    content = "\n\n".join(
        f"## {s}\n" + ("需求正文内容。" * 40) for s in spec.required_sections
    )
    content += "\n\nOut of Scope: 本期不做移动端。\n"
    md = tmp_path / "req.md"
    md.write_text("# 需求说明\n\n" + content, encoding="utf-8")
    res = check_format(spec, md.read_text(encoding="utf-8"), str(md), enforce_must_include=True)
    assert res.passed, res.failures


def test_resolve_format_spec_without_template_unchanged():
    base = get_spec("product-planning")
    resolved = resolve_format_spec("product-planning", None)
    assert resolved is not None
    assert resolved.required_sections == base.required_sections
    assert not resolved.template_id


def test_resolve_format_spec_tds_ch3():
    spec = resolve_format_spec("product-planning", "tds-ch3-product-planning")
    assert spec is not None
    assert spec.template_id == "tds-ch3-product-planning"
    assert "优势分析" in spec.required_sections
    assert "第一期 MVP版本" in spec.required_sections
    assert spec.required_heading_level == 3
    assert "product-architecture.drawio" in spec.file_exists
    assert "functional-architecture.png" in spec.file_exists
    assert "product-architecture.png" in spec.must_include


def test_gate_format_requires_architecture_diagram_files(tmp_path):
    spec = resolve_format_spec("product-planning", "tds-ch3-product-planning")
    content = "\n\n".join(
        f"### {s}\n" + ("正文内容。" * 80) for s in spec.required_sections
    )
    content += "\n\n![](product-architecture.png)\n\n![](functional-architecture.png)\n"
    md = tmp_path / "doc.md"
    md.write_text("# 第三章 产品整体规划\n\n" + content, encoding="utf-8")
    for name in spec.file_exists:
        (tmp_path / name).write_bytes(b"x")
    res = check_format(spec, md.read_text(encoding="utf-8"), str(md), enforce_must_include=True)
    assert res.passed, res.failures


def test_gate_format_uses_template_sections(tmp_path):
    spec = resolve_format_spec("product-planning", "tds-ch3-product-planning")
    content = "\n\n".join(
        f"### {s}\n" + ("正文内容。" * 80) for s in spec.required_sections
    )
    content += "\n\n![](product-architecture.png)\n\n![](functional-architecture.png)\n"
    md = tmp_path / "doc.md"
    md.write_text("# 第三章 产品整体规划\n\n" + content, encoding="utf-8")
    for name in spec.file_exists:
        (tmp_path / name).write_bytes(b"x")
    res = check_format(spec, md.read_text(encoding="utf-8"), str(md), enforce_must_include=True)
    assert res.passed, res.failures


def test_parse_goal_template_id():
    goal = "## 目标\n- template_id: tds-ch3-product-planning\n写第三章"
    assert parse_goal_template_id(goal) == "tds-ch3-product-planning"


def test_apply_goal_template_defaults():
    tasks = [{"id": "t1", "task_type": "product-planning"}, {"id": "t2", "task_type": "product-planning"}]
    out = apply_goal_template_defaults(tasks, "template_id: tds-ch3-product-planning")
    assert out[0]["template_id"] == "tds-ch3-product-planning"
    assert out[1]["template_id"] == "tds-ch3-product-planning"


def test_delete_template_blocked_when_workflow_references():
    from common.delivery.delivery_template_store import delete_template, workflows_using_template
    import pytest

    refs = workflows_using_template("tds-ch3-product-planning")
    if not refs:
        pytest.skip("无工作流引用 tds-ch3-product-planning")
    with pytest.raises(ValueError, match="仍被 Workflow 引用"):
        delete_template("tds-ch3-product-planning")


def test_list_templates_omits_missing_yaml(tmp_path, monkeypatch):
    import shutil
    from common.delivery.delivery_template_store import list_templates_for_api
    from common.delivery.delivery_templates import invalidate_delivery_templates_cache
    from common.paths import BUSINESS_DIR

    fp = BUSINESS_DIR / "delivery_templates" / "tmp-list-ghost.yaml"
    fp.write_text(
        "id: tmp-list-ghost\ndisplay_name: g\ntask_types: [product-planning]\n"
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
