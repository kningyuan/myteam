#!/usr/bin/env python3
"""agent_skills 严格模式 — 仅 registry 配置的 Skill 生效。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent_skills import (  # noqa: E402
    build_skill_context,
    get_agent_skill_ids,
    resolve_skill_ids,
)


def test_no_skills_when_registry_empty():
    with patch("common.agent_skills.get_agent_info", return_value={}):
        assert get_agent_skill_ids("developer") == []


def test_only_registry_skills_no_task_type_auto_add():
    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["backend-engineering-methodology"]},
    ):
        assert resolve_skill_ids("developer", task_type="code-writing") == [
            "backend-engineering-methodology"
        ]


def test_build_skill_context_lists_only_configured():
    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["backend-engineering-methodology"]},
    ):
        ctx = build_skill_context("developer")
        assert "【已挂载 Skill】" in ctx
        assert "backend-engineering-methodology" in ctx
        assert "禁止查阅未列出的" in ctx


def test_empty_skills_boundary_message():
    with patch("common.agent_skills.get_agent_info", return_value={"skills": []}):
        ctx = build_skill_context("developer")
        assert "未挂载任何 Skill" in ctx
        assert "禁止查阅" in ctx


def test_chat_system_prompt_includes_skills():
    from base.agent_chat import build_system_prompt

    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["product-methodology"]},
    ):
        prompt = build_system_prompt("product", "/tmp/ws", profile="interactive")
        assert "product-methodology" in prompt
        assert "【已挂载 Skill】" in prompt


def test_worker_prompt_includes_skills_not_task_type_implicit():
    from common.agent_transport import build_worker_prompt
    from common.contracts import parse_request

    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["backend-engineering-methodology"]},
    ):
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
        assert "backend-engineering-methodology" in prompt
        assert "code-writing" not in prompt or "code-writing/SKILL" not in prompt
