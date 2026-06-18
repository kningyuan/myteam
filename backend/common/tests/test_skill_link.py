#!/usr/bin/env python3
"""Skill 软链挂载（vendor / cursor / workspace）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.skill_link import (  # noqa: E402
    ensure_vendor_skill_link,
    link_skill_dir,
    resolve_skill_source_dir,
    sync_cursor_skill_links,
)


def test_link_skill_dir_creates_symlink(tmp_path):
    src = tmp_path / "vendor" / "browse"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("# browse\n", encoding="utf-8")
    (src / "bin").mkdir()
    (src / "bin" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    dest = tmp_path / "business" / "skills" / "browse"
    mode = link_skill_dir(dest, src)
    assert mode == "linked"
    assert dest.is_symlink()
    assert (dest / "bin" / "run.sh").is_file()


def test_ensure_vendor_replaces_stub(tmp_path, monkeypatch):
    vendor = tmp_path / "upstream" / "browse"
    vendor.mkdir(parents=True)
    (vendor / "SKILL.md").write_text("# full browse\n", encoding="utf-8")
    (vendor / "dist").mkdir()

    skills_dir = tmp_path / "business" / "skills"
    skills_dir.mkdir(parents=True)
    stub = skills_dir / "browse"
    stub.mkdir()
    (stub / "SKILL.md").write_text("# stub\n", encoding="utf-8")

    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "common.skill_link.VENDOR_SKILL_SOURCES",
        {"browse": [str(vendor)]},
    )

    out = ensure_vendor_skill_link("browse")
    assert out["status"] == "linked"
    linked = skills_dir / "browse"
    assert linked.is_symlink()
    assert (linked / "dist").is_dir()


def test_resolve_skill_source_prefers_business_dir(tmp_path, monkeypatch):
    skills_dir = tmp_path / "business" / "skills"
    local = skills_dir / "officecli"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text("# office\n", encoding="utf-8")
    (local / "bin").mkdir()

    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("common.skill_link.VENDOR_SKILL_SOURCES", {})

    resolved = resolve_skill_source_dir("officecli")
    assert resolved == local.resolve()


def test_ensure_vendor_links_flat_anchor(tmp_path, monkeypatch):
    """vendor skill 挂载在 business/skills/<id>/ 顶层。"""
    skills_dir = tmp_path / "business" / "skills"
    skills_dir.mkdir(parents=True)
    vendor = tmp_path / "upstream" / "officecli"
    vendor.mkdir(parents=True)
    (vendor / "SKILL.md").write_text("# office\n", encoding="utf-8")

    monkeypatch.setattr("common.skill_link.SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "common.skill_link.VENDOR_SKILL_SOURCES",
        {"officecli": [str(vendor)]},
    )

    out = ensure_vendor_skill_link("officecli")
    assert out["status"] == "linked"
    dest = skills_dir / "officecli"
    assert dest.is_symlink()
    assert (dest / "SKILL.md").is_file()


def test_sync_cursor_skill_links(tmp_path, monkeypatch):
    business = tmp_path / "business" / "skills"
    cursor = tmp_path / "cursor-skills"
    alpha = business / "alpha"
    alpha.mkdir(parents=True)
    (alpha / "SKILL.md").write_text("# alpha\n", encoding="utf-8")

    monkeypatch.setattr("common.skill_link.SKILLS_DIR", business)
    out = sync_cursor_skill_links(skill_ids=["alpha"], cursor_root=cursor, business_root=business)
    assert out["success"] is True
    assert "alpha" in out["linked"]
    dest = cursor / "alpha"
    assert dest.is_symlink()
    assert (dest / "SKILL.md").read_text(encoding="utf-8").startswith("# alpha")
