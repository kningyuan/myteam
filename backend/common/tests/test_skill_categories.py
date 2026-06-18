#!/usr/bin/env python3
"""skill_categories — 分类元数据（categories.yaml）与标签分配。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.skill_categories import (  # noqa: E402
    category_for_skill,
    create_skill_category,
    is_skill_category_dir,
    move_skill_to_category,
    resolve_library_entry,
)


@pytest.fixture()
def skills_env(tmp_path, monkeypatch):
    skills_dir = tmp_path / "business" / "skills"
    skills_dir.mkdir(parents=True)
    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_categories.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    return skills_dir


def test_create_and_detect_category(skills_env):
    out = create_skill_category("tools", name="工具箱", description="test")
    assert out["success"] is True
    assert is_skill_category_dir("tools")
    assert (skills_env / "categories.yaml").is_file()
    assert not (skills_env / "tools").is_dir()


def test_move_skill_updates_registry_not_disk(skills_env):
    create_skill_category("tools", name="工具箱")
    skill = skills_env / "alpha"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")

    result = move_skill_to_category("alpha", "tools")
    assert result["success"] is True
    assert (skills_env / "alpha" / "SKILL.md").is_file()
    assert not (skills_env / "tools" / "alpha").exists()
    assert category_for_skill("alpha") == "tools"


def test_resolve_library_entry_category_vs_skill(skills_env):
    create_skill_category("tools", name="工具箱")
    skill = skills_env / "beta"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")
    move_skill_to_category("beta", "tools")

    cat = resolve_library_entry("tools")
    assert cat and cat.get("kind") == "category"
    leaf = resolve_library_entry("beta")
    assert leaf and leaf.get("kind") != "category"


def test_get_category_file_member_symlink_skill_md(skills_env, tmp_path, monkeypatch):
    """分类成员 SKILL.md 为软链时，get_category_file 可读。"""
    from common.skill_categories import create_skill_category, get_category_file

    create_skill_category("suite", name="套件")
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text("# member\n", encoding="utf-8")
    anchor = skills_env / "member-a"
    anchor.symlink_to(upstream / "pkg", target_is_directory=True)
    (upstream / "pkg").mkdir()
    (upstream / "pkg" / "SKILL.md").symlink_to("../SKILL.md")

    data = {"version": "1", "categories": {"suite": {"name": "套件", "description": "", "members": ["member-a"]}}}
    import yaml

    (skills_env / "categories.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    out = get_category_file("suite", "member-a/SKILL.md")
    assert out is not None
    assert out.get("exists") is True
    assert "member" in out.get("content", "")
