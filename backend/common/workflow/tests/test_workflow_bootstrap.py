#!/usr/bin/env python3
"""workflow_bootstrap — PGD 角色准备与运行时校验。"""
from __future__ import annotations

import json

import pytest

from common import paths
from common.process.plan_gate import check_plan
from common.workflow.workflow_bootstrap import _resolve_agent_meta, ensure_workflow_ready, load_pgd_agent_template
from common.workflow.workflow_loader import load_workflow


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
    for wid in ("方案完善",):
        profile = load_workflow(wid)
        for aid in profile.roster:
            assert aid in template, f"{wid} roster {aid} missing in pgd-agents.json"
            tts = set(template[aid].get("task_types") or [])
            used = {t["task_type"] for t in profile.tasks if t.get("agent") == aid}
            assert used <= tts, f"{aid} in {wid}: missing task_types {used - tts}"


def test_ensure_workflow_ready_creates_registry(pgd_env):
    for aid in ("main", "product"):
        paths.workspace_dir(aid).mkdir(parents=True, exist_ok=True)
    profile = ensure_workflow_ready("方案完善", backend="claude")
    assert profile.id == "方案完善"
    reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    for aid in profile.roster:
        assert aid in reg["agents"]
        assert reg["agents"][aid].get("task_types")
    tasks = profile.instantiate_tasks(goal="测试方案完善目标")
    assert check_plan(tasks, set(profile.roster), check_capabilities=True).passed


def test_resolve_agent_meta_prefers_management_workspace(pgd_env):
    """与「管理」Tab 一致：有 workspace 即可；无 workspace 时可从注册表 bootstrap。"""
    template = load_pgd_agent_template()
    assert _resolve_agent_meta("product", template) is not None

    reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    reg["agents"]["custom_dev"] = {
        "name": "自定义研发",
        "role": "worker",
        "description": "测试用",
        "task_types": ["research"],
    }
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    assert _resolve_agent_meta("custom_dev", template)["name"] == "自定义研发"

    ws = paths.workspace_dir("ws_only_agent")
    ws.mkdir(parents=True)
    meta = _resolve_agent_meta("ws_only_agent", template)
    assert meta is not None and meta["name"] == "ws_only_agent"
    assert _resolve_agent_meta("no_such_agent", template) is None


def test_ensure_workflow_ready_enforces_agent_task_types(pgd_env, monkeypatch, tmp_path):
    """Agent 配置了 task_types 时，workflow 须匹配才能启动。"""
    reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
    reg["agents"]["arch"] = {
        "name": "架构师",
        "role": "worker",
        "task_types": ["system-design"],
    }
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("common.agent.agent_registry.REGISTRY_FILE", paths.AGENTS_REGISTRY_FILE)
    for aid in ("main", "arch"):
        paths.workspace_dir(aid).mkdir(parents=True, exist_ok=True)

    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "arch-research.yaml").write_text(
        """id: arch-research
version: "1.0"
description: test
tasks:
  - id: t1
    name: 架构调研
    agent: arch
    task_type: research
    dependencies: []
    description: test
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("common.workflow.workflow_loader.workflows_dir", lambda: wf_dir)
    with pytest.raises((RuntimeError, ValueError), match="research"):
        ensure_workflow_ready("arch-research", backend="claude")

    reg["agents"]["arch"]["task_types"] = ["research", "system-design"]
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    profile = ensure_workflow_ready("arch-research", backend="claude")
    assert profile.id == "arch-research"

def test_merge_agent_meta_preserves_skills():
    from common.workflow.workflow_bootstrap import _merge_agent_meta

    existing = {
        "name": "产品专家",
        "skills": ["deck-build", "section-authoring"],
        "mcp_servers": ["officecli"],
        "task_types": ["deck-build"],
    }
    incoming = {
        "name": "产品专家",
        "capabilities": ["需求"],
        "task_types": ["section-authoring"],
    }
    merged = _merge_agent_meta(existing, incoming)
    assert merged["skills"] == ["deck-build", "section-authoring"]
    assert merged["mcp_servers"] == ["officecli"]
    assert "section-authoring" in merged["task_types"]

def test_merge_agent_meta_ignores_incoming_skills():
    from common.workflow.workflow_bootstrap import _merge_agent_meta

    existing = {"name": "产品专家", "task_types": ["deck-build"]}
    incoming = {
        "name": "产品专家",
        "skills": ["product-methodology"],
        "task_types": ["section-authoring"],
    }
    merged = _merge_agent_meta(existing, incoming)
    assert "skills" not in merged
    assert "section-authoring" in merged["task_types"]

