#!/usr/bin/env python3
"""Claude Code 工作区 Skill 同步。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapters.claude.skill_sync import (  # noqa: E402
    MANIFEST_NAME,
    sync_workspace_skills,
)


@pytest.fixture()
def skill_env(tmp_path, monkeypatch):
    skills_dir = tmp_path / "business" / "skills"
    monkeypatch.setattr("adapters.claude.skill_sync.SKILLS_DIR", skills_dir)
    for sid in ("alpha", "beta"):
        d = skills_dir / sid
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {sid}\n", encoding="utf-8")
    ws = tmp_path / "workspace-ceo"
    ws.mkdir()
    return ws, skills_dir


def test_sync_links_desired_skills(skill_env):
    ws, _ = skill_env
    result = sync_workspace_skills(ws, ["alpha", "beta"])
    assert result["success"] is True
    assert result["linked"] == ["alpha", "beta"]
    assert (ws / ".claude" / "skills" / "alpha" / "SKILL.md").is_file()
    assert (ws / ".claude" / "skills" / "beta" / "SKILL.md").is_file()
    manifest = json.loads((ws / ".claude" / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["skill_ids"] == ["alpha", "beta"]


def test_sync_removes_unmounted_skills(skill_env):
    ws, _ = skill_env
    stale = ws / ".claude" / "skills" / "stale"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("# stale\n", encoding="utf-8")

    result = sync_workspace_skills(ws, ["alpha"])
    assert result["success"] is True
    assert "stale" in result["removed"]
    assert not (ws / ".claude" / "skills" / "stale").exists()
    assert (ws / ".claude" / "skills" / "alpha" / "SKILL.md").is_file()


def test_sync_reports_missing(skill_env):
    ws, _ = skill_env
    result = sync_workspace_skills(ws, ["alpha", "missing-skill"])
    assert result["success"] is True
    assert result["linked"] == ["alpha"]
    assert result["missing"] == ["missing-skill"]


def test_adapter_sync_agent_skills(skill_env, monkeypatch):
    ws, _ = skill_env
    from adapters.claude.adapter import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    assert adapter.capabilities.native_skill_registry is True
    out = adapter.sync_agent_skills("ceo", str(ws), ["alpha"])
    assert out["success"] is True
    assert out["linked"] == ["alpha"]
    assert (ws / ".claude" / "skills" / "alpha" / "SKILL.md").read_text(encoding="utf-8").startswith("# alpha")
