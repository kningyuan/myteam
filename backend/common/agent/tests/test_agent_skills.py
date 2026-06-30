#!/usr/bin/env python3
"""agent_skills — registry 显式配置 + 全入口注入（集成环境读真实 agents_registry）。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent.agent_skills import (  # noqa: E402
    build_skill_context,
    get_agent_mounted_skill_ids,
    get_agent_skill_ids,
    resolve_skill_ids,
    skill_file_path,
)


def test_developer_registry_methodology():
    ids = get_agent_skill_ids("developer")
    assert ids == ["backend-engineering-methodology"]
    assert skill_file_path(ids[0]) is not None


def test_frontend_has_engineering_and_architecture_skills():
    ids = get_agent_skill_ids("frontend")
    assert "frontend-engineering-methodology" in ids
    assert "frontend-architecture-methodology" in ids


def test_resolve_does_not_add_task_type_skill():
    ids = resolve_skill_ids("developer", task_type="code-writing")
    assert ids == ["backend-engineering-methodology"]
    assert "code-writing" not in ids


def test_chat_system_prompt_includes_agent_skills():
    from hub.services.chat_service import ChatService

    svc = ChatService()
    block = build_skill_context("developer")
    assert "【已挂载 Skill】" in block
    assert "backend-engineering-methodology" in block

    prompt = svc._build_system_prompt("developer", "/tmp/ws", profile="interactive")
    assert "backend-engineering-methodology" in prompt


def test_worker_prompt_uses_registry_skills_only():
    from common.agent.agent_transport import build_worker_prompt
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
    assert "【已挂载 Skill】" in prompt
    assert "backend-engineering-methodology" in prompt
    assert "code-writing/SKILL" not in prompt
    assert "【用法】" in prompt
    assert "Read 工具" in prompt


def test_all_methodology_skill_files_exist():
    from common.skill.skill_catalog import list_skill_library

    ids = [
        "product-methodology",
        "backend-engineering-methodology",
        "frontend-engineering-methodology",
        "frontend-architecture-methodology",
        "qa-methodology",
        "coordination-methodology",
        "system-architecture-methodology",
    ]
    lib_ids = {s["id"] for s in list_skill_library()}
    for sid in ids:
        assert sid in lib_ids, sid
        assert skill_file_path(sid) is not None, sid


@pytest.mark.skip(reason="officecli skill 套件已移除（上游软链失效），待重新引入后恢复")
def test_product_officecli_group_expands():
    ids = get_agent_skill_ids("product")
    assert "officecli" in ids
    mounted = get_agent_mounted_skill_ids("product")
    assert "officecli-pptx" in mounted
    assert "product-methodology" in mounted
