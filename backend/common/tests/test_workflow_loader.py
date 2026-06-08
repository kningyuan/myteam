#!/usr/bin/env python3
"""workflow_loader 与 PGD profile DAG 校验。"""
from __future__ import annotations

import pytest

from common.plan_gate import topological_order
from common.workflow_loader import list_workflows, load_workflow


def test_list_workflows_includes_profiles():
    ids = list_workflows()
    assert "software-delivery" in ids
    assert "content-campaign" in ids
    assert "hotfix" in ids


@pytest.mark.parametrize("wid", ["software-delivery", "content-campaign"])
def test_load_workflow_passes_plan_gate(wid: str):
    profile = load_workflow(wid)
    assert profile.id == wid
    assert "main" in profile.roster
    tasks = profile.instantiate_tasks(goal="测试目标注入")
    assert tasks[0]["description"].startswith("【项目目标】测试目标注入")
    order = topological_order(tasks)
    assert order[0] in {t["id"] for t in tasks}
    assert len(order) == len(tasks)


def test_software_delivery_has_decision_gates():
    profile = load_workflow("software-delivery")
    kinds = {t["task_type"] for t in profile.tasks}
    assert "requirements" in kinds
    assert "decision-record" in kinds
    assert "acceptance-report" in kinds
    decisions = [t["id"] for t in profile.tasks if t["task_type"] == "decision-record"]
    assert "req-decision" in decisions
    assert "design-decision" in decisions
    assert "release-decision" in decisions
