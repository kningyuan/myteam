#!/usr/bin/env python3
"""Skill 懒加载注入测试 — 验证三层注入（摘要+章节+路径）。"""
from __future__ import annotations

from pathlib import Path

from execution_harness.injection.blocks import (
    _extract_sections,
    _extract_toc,
    append_umbrella_skill_block,
)


def test_extract_sections_basic():
    """按 ## heading 截取指定章节正文"""
    md = """# 产品方法论

## 方法论
- RICE 评分：Reach × Impact × Confidence / Effort
- Kano 模型：基本/期望/兴奋三层

## 检查清单
- [ ] 是否覆盖用户场景
- [ ] 是否有优先级排序

## 其他章节
这段不应该出现
"""
    result = _extract_sections(md, ["方法论", "检查清单"])
    assert "RICE 评分" in result
    assert "是否覆盖用户场景" in result
    assert "这段不应该出现" not in result


def test_extract_sections_case_insensitive():
    """章节名匹配不区分大小写"""
    md = "## Methodology\n内容A\n## Checklist\n内容B"
    result = _extract_sections(md, ["methodology", "checklist"])
    assert "内容A" in result
    assert "内容B" in result


def test_extract_toc():
    """提取 ## 二级标题列表"""
    md = "# 标题\n\n## 第一章\n内容\n\n## 第二章\n内容\n\n### 三级\n不应出现"
    toc = _extract_toc(md)
    assert toc == ["第一章", "第二章"]


def test_skill_sections_injection(tmp_path):
    """指定章节时，prompt 包含章节正文 + 目录 + 路径（层1+层2）"""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "# 产品方法论\n\n"
        "## 方法论\n- RICE 评分\n- Kano 模型\n\n"
        "## 检查清单\n- [ ] 覆盖用户场景\n\n"
        "## 其他\n这段不应出现\n",
        encoding="utf-8",
    )
    lines: list[str] = []
    append_umbrella_skill_block(
        lines,
        "product-methodology",
        str(skill_md),
        skill_sections=["方法论", "检查清单"],
    )
    prompt = "\n".join(lines)
    # 层2：章节正文
    assert "RICE 评分" in prompt
    assert "覆盖用户场景" in prompt
    assert "这段不应出现" not in prompt
    # 层1：标题 + 目录 + 路径
    assert "本任务方法论 Skill" in prompt
    assert "product-methodology" in prompt
    assert "章节目录" in prompt
    assert "方法论" in prompt  # 目录中包含章节名
    assert "检查清单" in prompt
    assert str(skill_md) in prompt


def test_skill_lazy_loading_without_sections(tmp_path):
    """无 skill_sections 时，只注入目录+路径（层1），不注入全文"""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "# 方法论\n\n## 章节A\n全文内容在这里\n\n## 章节B\n更多内容",
        encoding="utf-8",
    )
    lines: list[str] = []
    append_umbrella_skill_block(
        lines, "test-skill", str(skill_md), skill_sections=None
    )
    prompt = "\n".join(lines)
    # 层1：目录 + 路径
    assert "本任务方法论 Skill" in prompt
    assert "章节目录" in prompt
    assert "章节A" in prompt  # 目录中包含
    assert "章节B" in prompt
    assert str(skill_md) in prompt
    assert "按需 Read" in prompt
    # 不应注入全文
    assert "全文内容在这里" not in prompt
    assert "更多内容" not in prompt


def test_skill_truncation_with_sections(tmp_path):
    """指定章节超过 max_chars 时截断"""
    skill_md = tmp_path / "SKILL.md"
    long_text = "A" * 3000
    skill_md.write_text(
        f"# 方法论\n\n## 长章节\n{long_text}\n\n## 短章节\n短内容",
        encoding="utf-8",
    )
    lines: list[str] = []
    append_umbrella_skill_block(
        lines, "test-skill", str(skill_md),
        skill_sections=["长章节"], max_chars=500,
    )
    prompt = "\n".join(lines)
    assert "…" in prompt
    # 章节正文截断后不应超过 max_chars + 开销
    assert len(prompt) < 900


def test_skill_not_found_fallback_pointer(tmp_path):
    """文件不存在时降级为指针注入"""
    lines: list[str] = []
    append_umbrella_skill_block(
        lines,
        "nonexistent",
        str(tmp_path / "NO_SUCH_FILE.md"),
        skill_sections=None,
    )
    prompt = "\n".join(lines)
    assert "nonexistent" in prompt
    assert "读取失败" in prompt


def test_skill_sections_not_found_warning(tmp_path):
    """指定章节不存在时显示告警，不注入全文"""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# 方法论\n\n## 实际章节\n内容A", encoding="utf-8")
    lines: list[str] = []
    append_umbrella_skill_block(
        lines,
        "test-skill",
        str(skill_md),
        skill_sections=["不存在的章节"],
    )
    prompt = "\n".join(lines)
    # 显示告警
    assert "指定章节未找到" in prompt
    # 仍有目录和路径
    assert "实际章节" in prompt  # 目录中
    assert str(skill_md) in prompt
    # 不注入全文
    assert "内容A" not in prompt
