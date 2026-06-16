#!/usr/bin/env python3
"""workflow_validate — validate_workflow_payload 单元测试。

覆盖：基础结构、task_type 注册、agent 合法性、plan_gate DAG、多错误累积。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.workflow_validate import validate_workflow_payload  # noqa: E402


@pytest.fixture
def valid_payload():
    """一个合法的 workflow dict（agent + task_type 均在注册表内）。"""
    return {
        "id": "test-flow",
        "version": "1.0",
        "description": "测试 workflow",
        "tasks": [
            {
                "id": "t1",
                "name": "调研",
                "agent": "research",
                "task_type": "research",
                "dependencies": [],
                "description": "【对象】x",
            },
        ],
    }


@pytest.fixture
def available_agents():
    """Mock 可用 agent 集合，使测试不依赖 filesystem。"""
    return {"research", "main", "frontend", "ops"}


# ---- 基础结构校验 ----


class TestBasicStructure:
    def test_non_dict_raises_error(self):
        errors = validate_workflow_payload("not a dict")
        assert len(errors) == 1
        assert "必须是对象" in errors[0]

    def test_empty_dict(self):
        errors = validate_workflow_payload({})
        assert len(errors) >= 1
        assert any("缺少 id" in e for e in errors)
        assert any("未定义 tasks" in e for e in errors)

    def test_missing_id(self):
        errors = validate_workflow_payload({"tasks": []})
        assert any("缺少 id" in e for e in errors)

    def test_id_path_traversal(self):
        errors = validate_workflow_payload({"id": "../etc/passwd", "tasks": []})
        assert any("id 非法" in e for e in errors)

    def test_id_starts_with_dot(self):
        errors = validate_workflow_payload({"id": ".hidden", "tasks": []})
        assert any("id 非法" in e for e in errors)

    def test_tasks_empty_list(self):
        errors = validate_workflow_payload({"id": "x", "tasks": []})
        assert any("未定义 tasks" in e for e in errors)

    def test_tasks_not_list(self):
        errors = validate_workflow_payload({"id": "x", "tasks": "not-a-list"})
        assert any("未定义 tasks" in e for e in errors)


# ---- task_type 校验 ----


class TestTaskTypes:
    def test_unknown_task_type(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "task_type": "fake_type", "dependencies": []},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("fake_type" in e for e in errors)

    def test_missing_task_type(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "dependencies": []},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("t1" in e and "task_type" in e for e in errors)

    def test_loop_anchor_task_skips_task_type(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t-loop", "name": "循环", "loop": "loop1", "dependencies": []},
            ],
            "loops": [
                {
                    "id": "loop1",
                    "body": [
                        {"id": "s1", "agent": "research", "task_type": "research", "dependencies": []},
                    ],
                    "until": [{"type": "gate_passed", "task": "s1"}],
                },
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        task_type_errors = [e for e in errors if "t-loop" in e and "task_type" in e]
        assert len(task_type_errors) == 0


# ---- Agent 合法性校验 ----


class TestAgents:
    def test_valid_agent(self, valid_payload, available_agents):
        errors = validate_workflow_payload(valid_payload, available_agents=available_agents)
        # 可能仍有 plan_gate 错误（取决于注册表状态），但不应有 agent 错误
        agent_errors = [e for e in errors if "不存在的 Agent" in e]
        assert len(agent_errors) == 0

    def test_invalid_agent(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "ghost_agent", "task_type": "research", "dependencies": []},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("ghost_agent" in e and "不存在的 Agent" in e for e in errors)

    def test_missing_agent_field(self, available_agents):
        """agent 字段为空字符串 → 不报 agent 错误。"""
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "", "task_type": "research", "dependencies": []},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        agent_errors = [e for e in errors if "不存在的 Agent" in e]
        assert len(agent_errors) == 0


# ---- plan_gate 校验 ----


class TestPlanGate:
    def test_valid_plan(self, valid_payload, available_agents):
        """合法 plan 不应产生 plan_gate 错误。"""
        errors = validate_workflow_payload(valid_payload, available_agents=available_agents)
        plan_errors = [e for e in errors if any(kw in e for kw in ("环", "重复", "不在团队", "未注册", "能力边界"))]
        assert len(plan_errors) == 0, f"unexpected plan gate errors: {plan_errors}"

    def test_duplicate_task_ids(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
                {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("重复" in e for e in errors)

    def test_dangling_dependency(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "task_type": "research", "dependencies": ["nonexistent"]},
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("nonexistent" in e for e in errors)


# ---- 多错误累积 ----


class TestErrorAccumulation:
    def test_multiple_errors_collected(self, available_agents):
        """同时存在缺失 task_type + 非法 agent → 至少 2 条错误。"""
        payload = {
            "id": "test",
            "tasks": [
                {
                    "id": "t1",
                    "agent": "ghost",
                    "task_type": "fake_type",
                    "dependencies": [],
                },
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert len(errors) >= 2

    def test_null_data(self):
        errors = validate_workflow_payload(None)
        assert len(errors) == 1
        assert "必须是对象" in errors[0]


# ---- Loop body agent 校验 ----


class TestLoopParseErrors:
    def test_bodies_and_body_mutual_exclusion_returns_error(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
            ],
            "loops": [
                {
                    "id": "loop1",
                    "bodies": {
                        "default": [
                            {"id": "s1", "agent": "research", "task_type": "research", "dependencies": []},
                        ],
                    },
                    "default_body": "default",
                    "body": [
                        {"id": "s1", "agent": "research", "task_type": "research", "dependencies": []},
                    ],
                },
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("bodies 与 body 互斥" in e for e in errors)


class TestLoopAgents:
    def test_loop_with_invalid_agent(self, available_agents):
        payload = {
            "id": "test",
            "tasks": [
                {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
            ],
            "loops": [
                {
                    "id": "loop1",
                    "cycle": 1,
                    "body": [
                        {"id": "l1", "agent": "ghost", "task_type": "research", "dependencies": []},
                    ],
                    "until": ["l1"],
                },
            ],
        }
        errors = validate_workflow_payload(payload, available_agents=available_agents)
        assert any("ghost" in e and "不存在的 Agent" in e for e in errors)
