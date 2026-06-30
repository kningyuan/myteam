#!/usr/bin/env python3
"""Phase 1 契约一致性测试（D11）。

验证标准：每信封合法时通过；非法 JSON / 缺字段 / 自评缺失 被拒而非被修。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.contracts import (  # noqa: E402
    response_json_schema,
    validate_response_dict,
)
from common.delivery.submit_result import SubmitError, submit  # noqa: E402


def _quality():
    return {"score": 0.8, "known_gaps": [], "notes": "ok"}


# ── 各 kind 合法信封 ─────────────────────────────────────────


def test_team_config_ok():
    ok, model, errs = validate_response_dict({
        "interaction_id": "i1", "kind": "team_config", "status": "ok",
        "result": {"agents": ["research", "seo"]},
    })
    assert ok, errs
    assert model.result.agents == ["research", "seo"]


def test_task_plan_ok():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "i2", "kind": "task_plan", "status": "ok",
        "result": {"tasks": [{
            "id": "task_001", "name": "调研", "agent": "research",
            "task_type": "research", "description": "做调研", "dependencies": [],
        }]},
    })
    assert ok, errs


def test_evaluate_ok():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "i3", "kind": "evaluate", "status": "ok",
        "result": {"should_split": False, "reason": "无需拆", "sub_tasks": []},
    })
    assert ok, errs


def test_execute_artifact_ok():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "i4", "kind": "execute", "status": "ok",
        "quality": _quality(),
        "result": {"outcome": {
            "kind": "artifact",
            "artifact": {"path": "deliverables/x.md", "format": "markdown", "title": "X"},
        }},
    })
    assert ok, errs


def test_execute_action_ok():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "i5", "kind": "execute", "status": "ok",
        "quality": _quality(),
        "result": {"outcome": {
            "kind": "action",
            "artifact": {"path": "deliverables/record.md", "title": "发布记录"},
            "evidence": {"action_type": "publish", "url": "https://zhuanlan.zhihu.com/p/1",
                         "screenshots": ["evidence/a.png"]},
        }},
    })
    assert ok, errs


def test_review_ok():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "i6", "kind": "review", "status": "ok",
        "quality": _quality(),
        "result": {"passed": True, "feedback": "good", "checklist": []},
    })
    assert ok, errs


# ── 拒绝（不抢救）────────────────────────────────────────────


def test_reject_unknown_kind():
    ok, _m, errs = validate_response_dict({"interaction_id": "x", "kind": "nope", "result": {}})
    assert not ok and errs


def test_reject_missing_required_field():
    # task_plan 缺 result.tasks
    ok, _m, errs = validate_response_dict({
        "interaction_id": "x", "kind": "task_plan", "result": {},
    })
    assert not ok and errs


def test_reject_execute_without_quality():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "x", "kind": "execute", "status": "ok",
        "result": {"outcome": {"kind": "artifact", "artifact": {"path": "x.md"}}},
    })
    assert not ok
    assert any("quality" in e for e in errs)


def test_reject_action_without_evidence():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "x", "kind": "execute", "status": "ok", "quality": _quality(),
        "result": {"outcome": {"kind": "action", "artifact": {"path": "r.md"}}},
    })
    assert not ok
    assert any("evidence" in e for e in errs)


def test_reject_split_without_subtasks():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "x", "kind": "evaluate", "status": "ok",
        "result": {"should_split": True, "sub_tasks": []},
    })
    assert not ok and errs


def test_reject_triage_split_without_subtasks():
    ok, _m, errs = validate_response_dict({
        "interaction_id": "x", "kind": "triage", "status": "ok",
        "result": {"decision": "split", "sub_tasks": []},
    })
    assert not ok and errs


# ── submit_result：合法原子写 / 非法拒绝 ─────────────────────


def test_submit_writes_when_valid(tmp_path):
    out = tmp_path / "i.response"
    submit({
        "interaction_id": "i7", "kind": "team_config", "status": "ok",
        "result": {"agents": ["research"]},
    }, out)
    assert out.exists()
    assert json.loads(out.read_text())["kind"] == "team_config"


def test_submit_rejects_when_invalid(tmp_path):
    out = tmp_path / "i.response"
    with pytest.raises(SubmitError):
        submit({"interaction_id": "x", "kind": "task_plan", "result": {}}, out)
    assert not out.exists()  # 拒绝即不写回


def test_response_schema_export():
    schema = response_json_schema("execute")
    assert schema["properties"]["kind"]
