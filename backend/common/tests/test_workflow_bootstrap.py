#!/usr/bin/env python3
"""workflow_bootstrap — PGD 角色准备与运行时校验。"""
from __future__ import annotations

import json

import pytest

from common import paths
from common.plan_gate import check_plan
from common.workflow_bootstrap import ensure_workflow_ready, load_pgd_agent_template
from common.workflow_loader import load_workflow


@pytest.fixture
def pgd_env(tmp_path, monkeypatch):
    """隔离 registry / workspace 的 PGD 测试环境。"""
    reg = tmp_path / "agents_registry.json"
    cfg = tmp_path / "agents_config.json"
    ws = tmp_path / "workspaces"
    ws.mkdir()
    reg.write_text(json.dumps({"version": "1.0", "agents": {}}), encoding="utf-8")
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", reg)
    monkeypatch.setattr(paths, "AGENTS_CONFIG_FILE", cfg)
    monkeypatch.setattr(paths, "WORKSPACES_DIR", ws)
    monkeypatch.setattr(paths, "WORKSPACE_PREFIX", "workspace-")
    return tmp_path


def test_pgd_agent_template_covers_workflow_rosters():
    template = load_pgd_agent_template()
    for wid in ("software-delivery", "content-campaign", "hotfix"):
        profile = load_workflow(wid)
        for aid in profile.roster:
            assert aid in template, f"{wid} roster {aid} missing in pgd-agents.json"
            tts = set(template[aid].get("task_types") or [])
            used = {t["task_type"] for t in profile.tasks if t.get("agent") == aid}
            assert used <= tts, f"{aid} in {wid}: missing task_types {used - tts}"


def test_ensure_workflow_ready_creates_registry(pgd_env):
    profile = ensure_workflow_ready("hotfix", backend="claude")
    assert profile.id == "hotfix"
    reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    for aid in profile.roster:
        assert aid in reg["agents"]
        assert reg["agents"][aid].get("task_types")
    tasks = profile.instantiate_tasks(goal="修复 DAG 空白")
    assert check_plan(tasks, set(profile.roster), check_capabilities=True).passed
