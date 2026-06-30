#!/usr/bin/env python3
"""AGENTS.md 不再写入 Skill/MCP 挂载节；启动/保存时清理历史自动同步段落。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.agent.agent_mcp import strip_agents_md_mcp_section  # noqa: E402
from common.agent.agent_skills import strip_agents_md_skills_section  # noqa: E402
from common import paths  # noqa: E402


@pytest.fixture()
def tmp_agent_workspace(tmp_path, monkeypatch):
    aid = "test-strip-agent"
    monkeypatch.setattr(paths, "MYTEAM_ROOT", tmp_path)
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "business" / "workspaces")
    monkeypatch.setattr(paths, "AGENTS_REGISTRY_FILE", tmp_path / "business" / "config" / "agents_registry.json")
    ws = paths.workspace_dir(aid)
    ws.mkdir(parents=True)
    reg = {"version": "2.0", "agents": {aid: {"name": "测试", "skills": ["demo-skill"]}}}
    paths.AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg), encoding="utf-8")
    import common.agent.agent_registry as agent_registry_mod  # noqa: E402

    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", paths.AGENTS_REGISTRY_FILE)
    return aid, ws


def test_strip_skills_section_removes_legacy_block(tmp_agent_workspace):
    aid, ws = tmp_agent_workspace
    agents_md = ws / "AGENTS.md"
    agents_md.write_text(
        "# Test\n\n## 已挂载 Skill\n\n> auto\n\n- `demo-skill`\n\n## 工作流程\n1. x\n",
        encoding="utf-8",
    )
    assert strip_agents_md_skills_section(aid)
    text = agents_md.read_text(encoding="utf-8")
    assert "## 已挂载 Skill" not in text
    assert "`demo-skill`" not in text
    assert "## 工作流程" in text
    assert strip_agents_md_skills_section(aid) is False


def test_strip_mcp_section_removes_legacy_block(tmp_agent_workspace):
    aid, ws = tmp_agent_workspace
    agents_md = ws / "AGENTS.md"
    agents_md.write_text(
        "# Test\n\n## 已挂载 MCP\n\n> auto\n\n| MCP ID |\n| --- |\n| `playwright` |\n\n## 角色\nok\n",
        encoding="utf-8",
    )
    assert strip_agents_md_mcp_section(aid)
    text = agents_md.read_text(encoding="utf-8")
    assert "## 已挂载 MCP" not in text
    assert "playwright" not in text
    assert "## 角色" in text
