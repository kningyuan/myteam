#!/usr/bin/env python3
"""产出形态（三形态）单元测试。"""
from __future__ import annotations

import pytest

from common.gate import check_code_project, check_format
from common.registry import get_spec, invalidate_registry_cache, resolve_format_spec
from common.task_type_suggest import list_outcome_kind_catalog
from common.task_type_store import format_task_type_api


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


def test_deploy_run_is_action_form():
    spec = get_spec("deploy-run")
    assert spec is not None
    assert spec.outcome_kind == "action"


def test_code_deployment_is_artifact_form():
    spec = get_spec("code-deployment")
    assert spec is not None
    assert spec.outcome_kind == "artifact"
    assert "部署记录" in (spec.display_name or "")


def test_config_bundle_has_required_extensions():
    spec = get_spec("config-bundle")
    assert spec is not None
    assert spec.outcome_kind == "code_project"
    assert spec.required_extensions


def test_config_bundle_template_extensions(tmp_path):
    spec = resolve_format_spec("config-bundle", "config-bundle")
    assert spec is not None
    assert spec.required_extensions
    proj = tmp_path / "bundle"
    proj.mkdir()
    (proj / "README.md").write_text("# cfg", encoding="utf-8")
    (proj / "app.yaml").write_text("key: val", encoding="utf-8")
    res = check_code_project(spec, proj)
    assert res.passed, res.failures


def test_deploy_smoke_template_resolves():
    spec = resolve_format_spec("deploy-run", "deploy-smoke")
    assert spec is not None
    assert "服务URL" in spec.required_sections
    assert spec.evidence.get("screenshot_field") == "证据截图"


def test_format_task_type_api_includes_form_label():
    spec = get_spec("deploy-run")
    api = format_task_type_api(spec)
    assert api["outcome_form_label"] == "证据态"
    assert api["gate_algorithm"] == "check_action_evidence"


def test_list_delivery_templates_includes_new_templates():
    from common.delivery_templates import list_delivery_template_ids

    ids = list_delivery_template_ids()
    assert "deploy-smoke" in ids
    assert "config-bundle" in ids
