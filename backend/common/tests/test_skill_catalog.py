#!/usr/bin/env python3
"""skill_catalog — Skill 库扫描。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill_catalog import list_skill_library, get_skill_library_entry  # noqa: E402


def test_library_lists_production_skills():
    items = list_skill_library()
    ids = {i["id"] for i in items}
    assert "backend-engineering-methodology" in ids
    assert not any(i.startswith("auto-") for i in ids)


def test_get_library_entry():
    entry = get_skill_library_entry("product-methodology")
    assert entry is not None
    assert entry["id"] == "product-methodology"
    assert "content" in entry or entry.get("path")
