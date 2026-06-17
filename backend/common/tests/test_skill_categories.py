#!/usr/bin/env python3
"""skill_categories — 分类目录与移动。"""
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
    assert (skills_env / "tools" / "category.yaml").is_file()


def test_move_skill_into_category(skills_env):
    create_skill_category("tools", name="工具箱")
    skill = skills_env / "alpha"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")

    result = move_skill_to_category("alpha", "tools")
    assert result["success"] is True
    assert (skills_env / "tools" / "alpha" / "SKILL.md").is_file()
    assert category_for_skill("alpha") == "tools"


def test_resolve_library_entry_category_vs_skill(skills_env):
    create_skill_category("tools", name="工具箱")
    skill = skills_env / "tools" / "beta"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")

    cat = resolve_library_entry("tools")
    assert cat and cat.get("kind") == "category"
    leaf = resolve_library_entry("beta")
    assert leaf and leaf.get("kind") != "category"
