#!/usr/bin/env python3
"""skill_groups — vendor 套件分组与展开。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill_groups import (  # noqa: E402
    expand_skill_mounts,
    is_skill_group,
    list_skill_groups,
)


def test_officecli_is_skill_group():
    assert is_skill_group("officecli")
    assert not is_skill_group("officecli-pptx")


def test_officecli_group_expands_all_members():
    expanded = expand_skill_mounts(["officecli"])
    assert "officecli" in expanded
    assert "officecli-pptx" in expanded
    assert "morph-ppt" in expanded
    assert len(expanded) == len(list_skill_groups()[0]["members"])


def test_single_member_mount():
    expanded = expand_skill_mounts(["officecli-pptx", "product-methodology"])
    assert expanded == ["officecli-pptx", "product-methodology"]


def test_group_plus_member_dedupes():
    expanded = expand_skill_mounts(["officecli", "officecli-pptx"])
    assert expanded.count("officecli-pptx") == 1


def test_validate_accepts_group():
    from common.skill_catalog import validate_skill_ids

    valid, unknown = validate_skill_ids(["officecli", "not-a-skill"])
    assert "officecli" in valid
    assert "not-a-skill" in unknown
