#!/usr/bin/env python3
"""skill_display_names — 中文展示名与简介。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.skill.skill_display_names import (  # noqa: E402
    resolve_skill_display_description,
    resolve_skill_display_name,
)


def test_vendor_skill_chinese_name():
    assert resolve_skill_display_name("officecli", "officecli") == "Office 文档工具"
    assert resolve_skill_display_name("browse", "browse") == "浏览器操作"


def test_methodology_keeps_frontmatter_name():
    assert resolve_skill_display_name("product-methodology", "产品方法论") == "产品方法论"


def test_vendor_short_description():
    desc = resolve_skill_display_description(
        "officecli-pptx",
        "Create and edit PowerPoint presentations with officecli...",
    )
    assert desc == "演示文稿与幻灯片编辑"
    assert len(desc) < 40
