#!/usr/bin/env python3
"""skill_catalog — Skill 库扫描。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill_catalog import (  # noqa: E402
    get_skill_library_entry,
    list_all_skills,
    list_skill_library,
    update_skill_name,
)


def test_library_lists_production_skills():
    items = list_skill_library()
    ids = {i["id"] for i in items}
    assert "backend-engineering-methodology" in ids
    assert not any(i.startswith("auto-") for i in ids)


def test_vendor_skill_display_name_in_library():
    items = {i["id"]: i for i in list_skill_library()}
    if "officecli" in items:
        assert items["officecli"]["name"] == "Office 文档工具"
    if "browse" in items:
        assert items["browse"]["name"] == "浏览器操作"


def test_get_library_entry():
    entry = get_skill_library_entry("product-methodology")
    assert entry is not None
    assert entry["id"] == "product-methodology"
    assert "content" in entry or entry.get("path")
    desc = (entry.get("description") or "").strip()
    assert desc and desc != ">-"
    assert "方法论" in desc
    tree = entry.get("tree") or []
    assert isinstance(tree, list)
    assert any(n.get("name") == "SKILL.md" and n.get("type") == "file" for n in tree)


def test_skill_tree_structure(tmp_path, monkeypatch):
    from common.skill_catalog import get_skill_entry

    skills_dir = tmp_path / "business" / "skills"
    skill_dir = skills_dir / "tree-demo"
    (skill_dir / "bin").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# root\n", encoding="utf-8")
    (skill_dir / "bin" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_catalog.MYTEAM_ROOT", tmp_path)

    entry = get_skill_entry("tree-demo")
    assert entry is not None
    tree = entry["tree"]
    names = {n["name"] for n in tree}
    assert names == {"SKILL.md", "bin"}
    bin_node = next(n for n in tree if n["name"] == "bin")
    assert bin_node["type"] == "dir"
    assert len(bin_node["children"]) == 1
    assert bin_node["children"][0]["path"] == "bin/run.sh"


def test_methodology_descriptions_are_parsed_not_yaml_markers():
    """多行 description: >- 须解析为完整功能介绍，不能只留 YAML 折叠标记。"""
    for sid in (
        "product-methodology",
        "backend-engineering-methodology",
        "frontend-engineering-methodology",
        "frontend-architecture-methodology",
        "system-architecture-methodology",
        "qa-methodology",
        "coordination-methodology",
    ):
        entry = get_skill_library_entry(sid)
        assert entry is not None, sid
        desc = (entry.get("description") or "").strip()
        assert desc and desc != ">-", f"{sid} description broken: {desc!r}"
        assert len(desc) >= 20, sid


def test_update_skill_name_bumps_updated_at(tmp_path, monkeypatch):
    skills_dir = tmp_path / "business" / "skills"
    skill_id = "sort-bump-test"
    skill_dir = skills_dir / skill_id
    skill_dir.mkdir(parents=True)
    old_ts = 1_700_000_000.0
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: "旧名"\nupdated_at: {old_ts}\n---\n# body\n',
        encoding="utf-8",
    )

    other_dir = skills_dir / "other-skill"
    other_dir.mkdir(parents=True)
    (other_dir / "SKILL.md").write_text(
        f'---\nname: "其他"\nupdated_at: {old_ts + 100}\n---\n# other\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("common.skill_catalog.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_catalog.MYTEAM_ROOT", tmp_path)

    before_top = list_all_skills()[0]["id"]
    assert before_top == "other-skill"

    update_skill_name(skill_id, "新名")
    items = list_all_skills()
    assert items[0]["id"] == skill_id
    assert items[0]["name"] == "新名"
    assert items[0]["updated_at"] > old_ts + 100
