#!/usr/bin/env python3
"""build_skill_context 注入 Skill frontmatter description。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent_skills import build_skill_context  # noqa: E402


def test_build_skill_context_includes_name_and_description():
    with patch(
        "common.agent_skills.get_agent_info",
        return_value={"skills": ["demo-skill"]},
    ), patch(
        "common.agent_skills.get_skill_library_entry",
        return_value={
            "id": "demo-skill",
            "name": "演示 Skill",
            "description": "用于单元测试的示例能力说明。",
            "path": "business/skills/demo-skill/SKILL.md",
        },
    ), patch(
        "common.agent_skills.skill_file_path",
        return_value=Path("/tmp/business/skills/demo-skill/SKILL.md"),
    ), patch(
        "common.agent_skills.workspace_dir",
        return_value=Path("/tmp/ws"),
    ):
        ctx = build_skill_context("demo-agent")
        assert "demo-skill（演示 Skill）：用于单元测试的示例能力说明。" in ctx
        assert "先根据上表 description 判断是否需要某 Skill" in ctx
