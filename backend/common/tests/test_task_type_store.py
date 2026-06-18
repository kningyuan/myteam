#!/usr/bin/env python3
"""task_type_store — templates.yaml CRUD。"""
from __future__ import annotations

import json

import pytest
import yaml

from common import paths
from common.registry import get_spec, load_registry
from common.task_type_store import (
    delete_task_type,
    list_task_types_for_api,
    upsert_task_type,
)


@pytest.fixture
def tpl_env(tmp_path, monkeypatch):
    tpl = tmp_path / "templates.yaml"
    tpl.write_text("research:\n  display_name: 调研\n", encoding="utf-8")
    reg = tmp_path / "agents_registry.json"
    reg.write_text(json.dumps({"version": "1.0", "agents": {}}), encoding="utf-8")
    monkeypatch.setattr(paths, "templates_file", lambda: tpl)
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", reg, raising=False)
    from common.registry import invalidate_registry_cache
    invalidate_registry_cache()
    return tpl


def test_create_and_list_task_type(tpl_env):
    upsert_task_type("custom-survey", {
        "display_name": "自定义调研",
        "required_sections": ["背景", "结论"],
    })
    spec = get_spec("custom-survey")
    assert spec is not None
    assert spec.display_name == "自定义调研"
    assert "背景" in spec.required_sections
    api = list_task_types_for_api()
    assert any(t["task_type"] == "custom-survey" for t in api)


def test_delete_task_type_blocked_when_agent_uses(tpl_env):
    upsert_task_type("my-type", {"display_name": "我的类型"})
    reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    reg["agents"]["a1"] = {"name": "A", "task_types": ["my-type"]}
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="引用"):
        delete_task_type("my-type")


def test_data_analysis_spec_from_yaml(tpl_env):
    upsert_task_type("data-analysis", {
        "display_name": "数据分析",
        "outcome_kind": "artifact",
        "check_rules": {
            "required_sections": [
                "分析问题与口径",
                "数据来源与质量",
                "分析过程与方法",
                "关键发现",
                "结论与行动建议",
            ],
        },
    })
    spec = get_spec("data-analysis")
    assert spec is not None
    assert spec.outcome_kind == "artifact"
    assert "分析问题与口径" in spec.required_sections


def test_delete_task_type_ok(tpl_env):
    upsert_task_type("tmp-type", {"display_name": "临时"})
    delete_task_type("tmp-type")
    assert get_spec("tmp-type") is None
