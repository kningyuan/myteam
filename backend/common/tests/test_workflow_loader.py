#!/usr/bin/env python3
"""workflow_loader 与 PGD profile DAG 校验。"""
from __future__ import annotations

import pytest

from common.plan_gate import topological_order
from common.workflow_loader import (
    delete_workflow,
    list_workflows,
    load_workflow,
    read_workflow_raw,
    roster_from_tasks,
    write_workflow_raw,
)


def test_list_workflows_includes_profiles():
    ids = list_workflows()
    assert "GitHub项目调研" in ids
    assert "GEO优化" in ids
    assert "内容运营" in ids


@pytest.mark.parametrize("wid", ["GitHub项目调研", "内容运营"])
def test_load_workflow_passes_plan_gate(wid: str):
    profile = load_workflow(wid)
    assert profile.id == wid
    assert "main" in profile.roster
    tasks = profile.instantiate_tasks(goal="测试目标注入")
    assert tasks[0]["description"].startswith("【项目目标】测试目标注入")
    order = topological_order(tasks)
    assert order[0] in {t["id"] for t in tasks}
    assert len(order) == len(tasks)


def test_roster_from_tasks_derives_agents():
    tasks = [
        {"id": "t1", "agent": "research", "task_type": "research", "dependencies": []},
        {"id": "t2", "agent": "product", "task_type": "research", "dependencies": ["t1"]},
    ]
    assert roster_from_tasks(tasks) == ["main", "research", "product"]


def test_write_read_delete_workflow_raw(monkeypatch, tmp_path):
    monkeypatch.setattr("common.workflow_loader.workflows_dir", lambda: tmp_path)
    data = {
        "id": "ui-test-flow",
        "version": "1.0",
        "description": "测试",
        "options": {"parallel_enabled": False},
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
    wid = write_workflow_raw(data)
    assert wid == "ui-test-flow"
    raw = read_workflow_raw(wid)
    assert raw["description"] == "测试"
    assert "roster" not in raw
    profile = load_workflow(wid)
    assert profile.roster == ["main", "research"]
    assert profile.id == wid
    delete_workflow(wid)
    assert wid not in list_workflows()


def test_数据分析_has_required_task_types():
    profile = load_workflow("数据分析")
    kinds = {t["task_type"] for t in profile.tasks}
    assert "requirements" in kinds
    assert "data-analysis" in kinds
    assert "acceptance-report" in kinds


def test_self_upgrade_workflow_loads():
    assert "self-upgrade" in list_workflows()
    profile = load_workflow("self-upgrade")
    assert profile.id == "self-upgrade"
    assert profile.options.get("skill_extract_enabled") is True
    task_ids = {t["id"] for t in profile.tasks}
    assert "skill-extract" in task_ids
    assert "upgrade-plan" in task_ids
