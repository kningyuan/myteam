#!/usr/bin/env python3
"""skill_methodology — task_type + agent_id → 方法论 skill 路径。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill_methodology import (  # noqa: E402
    methodology_skill_path,
    methodology_skill_paths,
    resolve_methodology_skill_ids,
)


def test_product_task_gets_product_methodology():
    ids = resolve_methodology_skill_ids("requirements", "product")
    assert "product-methodology" in ids


def test_developer_code_writing_gets_backend_methodology():
    ids = resolve_methodology_skill_ids("code-writing", "developer")
    assert ids == ["backend-engineering-methodology"]


def test_frontend_code_writing_gets_frontend_engineering():
    ids = resolve_methodology_skill_ids("code-writing", "frontend")
    assert ids == ["frontend-engineering-methodology"]


def test_frontend_architecture_review_gets_both_fe_and_system():
    ids = resolve_methodology_skill_ids("architecture-review", "frontend")
    assert ids[0] == "frontend-architecture-methodology"
    assert "system-architecture-methodology" in ids


def test_arch_system_design_default_system_only():
    ids = resolve_methodology_skill_ids("system-design", "arch")
    assert ids == ["system-architecture-methodology"]


def test_arch_section_review_gets_system_architecture_methodology():
    ids = resolve_methodology_skill_ids("section-review", "arch")
    assert ids == ["system-architecture-methodology"]


def test_qa_code_testing():
    paths = methodology_skill_paths("code-testing", "qa")
    assert any(p.name == "SKILL.md" and "qa-methodology" in str(p) for p in paths)


def test_qa_test_plan():
    ids = resolve_methodology_skill_ids("test-plan", "qa")
    assert ids == ["qa-methodology"]


def test_qa_code_review_gets_qa_methodology():
    ids = resolve_methodology_skill_ids("code-review", "qa")
    assert ids == ["qa-methodology"]


def test_qa_architecture_review_gets_qa_methodology():
    ids = resolve_methodology_skill_ids("architecture-review", "qa")
    assert ids == ["qa-methodology"]


def test_all_registered_methodology_files_exist():
    sample = [
        ("requirements", "product"),
        ("code-writing", "developer"),
        ("code-writing", "frontend"),
        ("code-testing", "qa"),
        ("system-design", "arch"),
        ("architecture-review", "frontend"),
    ]
    for task_type, agent_id in sample:
        for sid in resolve_methodology_skill_ids(task_type, agent_id):
            assert methodology_skill_path(sid) is not None, sid


def test_prompt_injects_methodology_block():
    from common.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "i1",
        "kind": "execute",
        "project_id": "pro_x",
        "task_id": "task_001",
        "agent_id": "developer",
        "intent": "实现",
        "input": {"deliverable_path": "task_001_deliverable.md"},
        "constraints": {"task_type": "code-writing"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i1.response"), Path("/tmp/deliv"))
    assert "【方法论】" in prompt
    assert "backend-engineering-methodology" in prompt
    assert "【任务类型执行指引】" in prompt
    assert "code-writing" in prompt


def test_main_decision_record_gets_coordination_methodology():
    ids = resolve_methodology_skill_ids("decision-record", "main")
    assert ids == ["coordination-methodology"]
    assert methodology_skill_path("coordination-methodology") is not None


def test_prompt_injects_task_skill_for_code_deliverable():
    from common.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    req = parse_request({
        "interaction_id": "i2",
        "kind": "execute",
        "project_id": "pro_x",
        "task_id": "task_002",
        "agent_id": "developer",
        "intent": "交付代码",
        "input": {"deliverable_path": "task_002_deliverable.md"},
        "constraints": {"task_type": "code-deliverable"},
        "response_schema": "execute.result@1.0",
    })
    prompt = build_worker_prompt(req, Path("/tmp/i2.response"), Path("/tmp/deliv"))
    assert "code-deliverable" in prompt
    assert "backend-engineering-methodology" in prompt
