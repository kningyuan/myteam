#!/usr/bin/env python3
"""AGENTS.md skills 节与 registry 同步。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.agent_skills import (  # noqa: E402
    render_agents_md_skills_section,
    sync_agents_md_skills_section,
)
from common import paths  # noqa: E402


@pytest.fixture()
def tmp_agent_workspace(tmp_path, monkeypatch):
    aid = "test-sync-agent"
    monkeypatch.setattr(paths, "MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "business" / "workspaces")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", tmp_path / "business" / "config" / "agents_registry.json")
    ws = paths.workspace_dir(aid)
    ws.mkdir(parents=True)
    reg = {"version": "2.0", "agents": {aid: {"name": "测试", "skills": ["demo-skill"]}}}
    paths.AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg), encoding="utf-8")
    import common.agent_registry as agent_registry_mod  # noqa: E402

    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", paths.AGENTS_REGISTRY_FILE)
    skill_dir = tmp_path / "business" / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", tmp_path / "business" / "skills")
    monkeypatch.setattr("common.skill_catalog.MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr("common.agent_skills.SKILLS_DIR", tmp_path / "business" / "skills")
    monkeypatch.setattr("common.agent_skills.MYTEAM_ROOT", tmp_path)
    return aid, ws


def test_render_empty_skills():
    section = render_agents_md_skills_section("no-such-agent")
    assert "## 已挂载 Skill" in section
    assert "未挂载任何 Skill" in section


def test_sync_appends_section(tmp_agent_workspace):
    aid, ws = tmp_agent_workspace
    agents_md = ws / "AGENTS.md"
    agents_md.write_text("# Test\n\n## 核心定位\nhello\n", encoding="utf-8")
    assert sync_agents_md_skills_section(aid)
    text = agents_md.read_text(encoding="utf-8")
    assert "## 已挂载 Skill" in text
    assert "`demo-skill`" in text
    assert "## 核心定位" in text


def test_sync_replaces_existing_section(tmp_agent_workspace):
    aid, ws = tmp_agent_workspace
    agents_md = ws / "AGENTS.md"
    agents_md.write_text(
        "# Test\n\n## 已挂载 Skill\n\n旧内容\n\n## 工作流程\n1. x\n",
        encoding="utf-8",
    )
    sync_agents_md_skills_section(aid)
    text = agents_md.read_text(encoding="utf-8")
    assert "旧内容" not in text
    assert "`demo-skill`" in text
    assert "## 工作流程" in text
