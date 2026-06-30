#!/usr/bin/env python3
from __future__ import annotations

import json

import pytest

from common import paths
from common.workflow.workflow_capability_bind import bind_workflow_tasks_to_capabilities


@pytest.fixture
def cap_env(tmp_path, monkeypatch):
    reg = tmp_path / "agents_registry.json"
    ws = tmp_path / "workspaces"
    ws.mkdir()
    (ws / "workspace-developer").mkdir()
    (ws / "workspace-arch").mkdir()
    reg.write_text(json.dumps({
        "version": "1.0",
        "agents": {
            "arch": {"name": "架构师", "task_types": ["system-design", "research"]},
            "developer": {"name": "研发", "task_types": ["code-writing", "research"]},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", reg)
    monkeypatch.setattr(paths, "WORKSPACES_DIR", ws)
    monkeypatch.setattr(paths, "WORKSPACE_PREFIX", "workspace-")
    monkeypatch.setattr("common.agent.agent_registry.REGISTRY_FILE", reg)
    return tmp_path


def test_bind_swaps_agent_for_code_writing(cap_env):
    tasks = [{
        "id": "t1",
        "agent": "arch",
        "task_type": "code-writing",
        "dependencies": [],
    }]
    out = bind_workflow_tasks_to_capabilities(tasks)
    assert out[0]["agent"] == "developer"
    assert out[0]["task_type"] == "code-writing"
