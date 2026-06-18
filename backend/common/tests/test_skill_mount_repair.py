#!/usr/bin/env python3
"""Skill 分类移动后：registry 路径规范化 + CLI 工作区重挂。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapters.claude.skill_sync import sync_workspace_skills  # noqa: E402
from common.skill_catalog import canonical_skill_mount_id  # noqa: E402
from common.skill_categories import create_skill_category, move_skill_to_category  # noqa: E402
from common.skill_link import resolve_skill_source_dir  # noqa: E402
from hub.services.agent_registry import (  # noqa: E402
    _load_registry_file,
    normalize_agent_skill_mounts,
)


@pytest.fixture()
def skills_env(tmp_path, monkeypatch):
    skills_dir = tmp_path / "business" / "skills"
    skills_dir.mkdir(parents=True)
    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_categories.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    return skills_dir


def test_canonical_skill_mount_id_path_form(skills_env):
    create_skill_category("tools", name="工具箱")
    skill = skills_env / "alpha"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")

    assert canonical_skill_mount_id("alpha") == "alpha"
    assert canonical_skill_mount_id("tools/alpha") == "alpha"
    assert canonical_skill_mount_id("business/skills/tools/alpha") == "alpha"


def test_move_skill_remounts_workspace_symlink(skills_env, tmp_path, monkeypatch):
    create_skill_category("tools", name="工具箱")
    flat = skills_env / "alpha"
    flat.mkdir()
    (flat / "SKILL.md").write_text("# alpha\n", encoding="utf-8")

    workspaces = tmp_path / "workspaces"
    ws = workspaces / "workspace-dev"
    ws.mkdir(parents=True)
    sync_workspace_skills(ws, ["alpha"])
    old_link = ws / ".claude" / "skills" / "alpha"
    assert old_link.resolve() == flat.resolve()

    registry_path = tmp_path / "config" / "agents_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "agents": {
                    "dev": {
                        "name": "dev",
                        "role": "worker",
                        "skills": ["tools/alpha"],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("hub.services.agent_registry.AGENTS_REGISTRY_FILE", registry_path)
    monkeypatch.setattr("hub.paths.AGENTS_REGISTRY_FILE", registry_path)
    monkeypatch.setattr("common.paths.AGENTS_REGISTRY_FILE", registry_path)
    monkeypatch.setattr("common.agent_registry.REGISTRY_FILE", registry_path)
    monkeypatch.setattr("hub.services.agent_registry.WORKSPACES_DIR", workspaces)
    monkeypatch.setattr("hub.paths.WORKSPACES_DIR", workspaces)

    from common.agent_skills import get_agent_mounted_skill_ids

    def _sync_cli(agent_id: str, *, workspace: str | None = None):
        aid_ws = Path(workspace) if workspace else workspaces / f"workspace-{agent_id}"
        return sync_workspace_skills(aid_ws, get_agent_mounted_skill_ids(agent_id))

    monkeypatch.setattr("common.adapter_skill_registry.sync_agent_skills_to_cli", _sync_cli)

    cursor_root = tmp_path / ".cursor" / "skills"
    monkeypatch.setattr("common.skill_link.CURSOR_SKILLS_DIR", cursor_root)

    result = move_skill_to_category("alpha", "tools")
    assert result["success"] is True
    assert resolve_skill_source_dir("alpha") == skills_env / "tools" / "alpha"

    raw = _load_registry_file()
    assert raw["agents"]["dev"]["skills"] == ["alpha"]

    new_link = ws / ".claude" / "skills" / "alpha"
    assert new_link.is_symlink()
    assert new_link.resolve() == (skills_env / "tools" / "alpha").resolve()
    assert result["remount"]["success"] is True


def test_normalize_agent_skill_mounts_dedupes_path_and_id(skills_env, tmp_path, monkeypatch):
    create_skill_category("tools", name="工具箱")
    nested = skills_env / "tools" / "beta"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")

    registry_path = tmp_path / "config" / "agents_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "agents": {
                    "qa": {
                        "name": "qa",
                        "role": "worker",
                        "skills": ["tools/beta", "beta"],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("hub.services.agent_registry.AGENTS_REGISTRY_FILE", registry_path)

    updated = normalize_agent_skill_mounts(skill_id="beta")
    assert updated == ["qa"]
    raw = _load_registry_file()
    assert raw["agents"]["qa"]["skills"] == ["beta"]
