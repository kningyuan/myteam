#!/usr/bin/env python3
"""skill_methodology — 委托 agent_skills（registry 显式配置）。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill_methodology import (  # noqa: E402
    methodology_skill_path,
    methodology_skill_paths,
    resolve_methodology_skill_ids,
)


@pytest.fixture
def dev_skills():
    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["backend-engineering-methodology"]},
    ):
        yield


def test_developer_gets_registry_methodology(dev_skills):
    ids = resolve_methodology_skill_ids("code-writing", "developer")
    assert ids == ["backend-engineering-methodology"]


def test_methodology_paths_exist(dev_skills):
    paths = methodology_skill_paths("code-writing", "developer")
    assert any("backend-engineering-methodology" in str(p) for p in paths)


def test_prompt_injects_skill_block(dev_skills):
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
    assert "【已挂载 Skill】" in prompt
    assert "backend-engineering-methodology" in prompt
    assert "后端工程方法论" in prompt
    assert ">- " not in prompt


def test_all_registered_methodology_files_exist():
    from common.skill_catalog import list_skill_library

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
        assert methodology_skill_path(sid) is not None, sid
