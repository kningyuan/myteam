#!/usr/bin/env python3
"""子模块协作联动测试：skill → agent。

验证协作链路：
  1. skill_catalog.list_skill_library / get_skill_library_entry 能扫描 business/skills 下
     含 SKILL.md 的目录并解析 frontmatter（name/description/task_type）
  2. skill_link.resolve_skill_source_dir / business_skill_anchor 解析 skill 源目录
     （skill_catalog 与 skill_link 共用 SKILLS_DIR 常量）
  3. agent_skills.get_agent_skill_ids 从 agents_registry.json 读 skill 配置 →
     expand_skill_mounts 展开为叶子 id → build_skill_context 拼出含 skill 名的 prompt 块
  4. append_skill_instructions 把 skill 块追加到 worker prompt lines（skill → agent 对接）

不依赖真实 vendor skill；用 tmp_path 造一个最小 skill 目录隔离测试。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
import common.agent.agent_registry as agent_registry_mod  # noqa: E402
import common.skill.skill_catalog as skill_catalog_mod  # noqa: E402
import common.skill.skill_link as skill_link_mod  # noqa: E402
import common.skill.skill_categories as skill_categories_mod  # noqa: E402
from common.agent.agent_skills import (  # noqa: E402
    append_skill_instructions,
    build_skill_context,
    get_agent_skill_ids,
    resolve_skill_ids,
    skill_file_path,
)
from common.skill.skill_catalog import (  # noqa: E402
    get_skill_library_entry,
    list_skill_library,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离 skills 目录 + agents_registry，避免读工程文件污染。"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # 造一个最小生产 skill：含 frontmatter（name/description/task_type）+ 正文
    skill_dir = skills_dir / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: "我的技能"
description: "协作联动测试用例 skill"
task_type: "research"
updated_at: "1700000000"
---

# 我的技能

## 用途
演示 skill → agent 挂载链路。

## 步骤
1. 读取材料
2. 产出交付物
""",
        encoding="utf-8",
    )

    # 三处 SKILLS_DIR 都指向 tmp_path/skills（skill_catalog / skill_link / skill_categories
    # 各自在 import 时从 skill_catalog 绑定了同名常量，须分别 monkeypatch）
    monkeypatch.setattr(skill_catalog_mod, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skill_link_mod, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skill_categories_mod, "SKILLS_DIR", skills_dir)

    # 隔离 agents_registry.json：research agent 挂载 my-skill
    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "version": "2.0",
        "agents": {
            "research": {
                "name": "调研",
                "task_types": ["research"],
                "skills": ["my-skill"],
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)

    # 隔离 workspaces 目录（build_skill_context 内部拼 workspace_dir 路径字符串）
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")

    yield tmp_path
    # list_skill_library 等无 lru_cache，无需 invalidate
    return


def test_skill_catalog_scans_dir_consumable_by_agent_skills(env):
    """skill_catalog 扫描出的 skill，能被 agent_skills.skill_file_path 解析为路径。"""
    # 1) skill_catalog.list_skill_library 扫到 my-skill（生产 skill，非 auto-* 草案）
    items = list_skill_library()
    ids = [it["id"] for it in items]
    assert "my-skill" in ids
    entry = next(it for it in items if it["id"] == "my-skill")
    assert entry["name"] == "我的技能"
    assert entry["description"] == "协作联动测试用例 skill"

    # 2) get_skill_library_entry 返回完整 entry（含 path/content/sections）
    full = get_skill_library_entry("my-skill")
    assert full is not None
    assert "content" in full and "我的技能" in full["content"]
    assert "sections" in full and full["sections"]  # frontmatter 之后的正文按 ## 分章
    assert "body" in full and "读取材料" in full["body"]

    # 3) agent_skills.skill_file_path 解析出有效 Path（skill → agent 挂载路径对接）
    p = skill_file_path("my-skill")
    assert p is not None and p.is_file()
    assert p.name == "SKILL.md"


def test_agent_skills_mounts_registry_skill_to_prompt_block(env):
    """agent_skills 从 registry 读 skills 配置，build_skill_context 产出含 skill 名的块。"""
    # 1) get_agent_skill_ids 从 registry 读出 research 挂载的 my-skill
    ids = get_agent_skill_ids("research")
    assert ids == ["my-skill"]

    # 2) resolve_skill_ids 展开为叶子 id（my-skill 非组，原样返回）
    expanded = resolve_skill_ids("research", task_type="research")
    assert expanded == ["my-skill"]

    # 3) build_skill_context 拼出含 skill 名与 SKILL.md 路径的 prompt 块
    block = build_skill_context("research", task_type="research")
    assert "【已挂载 Skill】" in block
    assert "my-skill" in block
    assert "我的技能" in block           # frontmatter name 进入展示
    assert "协作联动测试用例 skill" in block  # description 进入展示
    assert "SKILL.md" in block           # 路径提示进入展示

    # 4) append_skill_instructions 把 skill 块追加到 worker prompt lines（skill → agent 对接）
    lines: list[str] = ["【任务】做调研。"]
    before = len(lines)
    append_skill_instructions(lines, "research", task_type="research")
    assert len(lines) > before
    joined = "\n".join(lines)
    assert "【任务】做调研。" in joined   # 原有内容保留
    assert "【已挂载 Skill】" in joined   # skill 块已追加
    assert "my-skill" in joined


def test_agent_without_skills_returns_boundary_block(env):
    """未挂载 skill 的 agent，build_skill_context 返回边界提示块（接口契约）。"""
    # seo agent 未在 registry 配置 skills → 返回「未挂载任何 Skill」边界块
    block = build_skill_context("seo", task_type="research")
    assert "未挂载任何 Skill" in block
    # append_skill_instructions 仍会追加该块（非空）
    lines: list[str] = []
    append_skill_instructions(lines, "seo", task_type="research")
    assert lines and "未挂载任何 Skill" in "\n".join(lines)
