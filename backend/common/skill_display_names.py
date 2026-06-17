"""Skill 中文展示名 — vendor 上游 frontmatter 多为英文，在此覆盖 UI / Agent 展示名。"""

from __future__ import annotations

SKILL_DISPLAY_NAMES: dict[str, str] = {
    "browse": "浏览器操作",
    "officecli": "Office 文档工具",
    "officecli-docx": "Word 文档",
    "officecli-pptx": "PPT 演示文稿",
    "officecli-xlsx": "Excel 表格",
    "officecli-pitch-deck": "融资路演 PPT",
    "officecli-academic-paper": "学术论文",
    "officecli-data-dashboard": "数据仪表盘",
    "officecli-financial-model": "财务模型",
    "officecli-word-form": "Word 表单",
    "morph-ppt": "Morph 动画 PPT",
    "morph-ppt-3d": "3D Morph 动画 PPT",
    "workflow-design": "工作流设计",
    "quality-review": "质量评审",
}

# 列表简介：vendor skill 上游 description 过长，用短中文替代
SKILL_DISPLAY_DESCRIPTIONS: dict[str, str] = {
    "browse": "无头浏览器 QA、截图与页面交互",
    "officecli": "创建与分析 Word / Excel / PowerPoint",
    "officecli-docx": "Word 文档读写与排版",
    "officecli-pptx": "演示文稿与幻灯片编辑",
    "officecli-xlsx": "表格、公式与数据写入",
    "officecli-pitch-deck": "融资路演专用幻灯片",
    "officecli-academic-paper": "论文格式与引用规范",
    "officecli-data-dashboard": "数据看板与图表",
    "officecli-financial-model": "财务模型与预测",
    "officecli-word-form": "Word 表单与字段",
    "morph-ppt": "跨页 Morph 平滑动画",
    "morph-ppt-3d": "3D 模型与镜头运动",
}


def resolve_skill_display_name(skill_id: str, frontmatter_name: str = "") -> str:
    sid = (skill_id or "").strip()
    if sid in SKILL_DISPLAY_NAMES:
        return SKILL_DISPLAY_NAMES[sid]
    name = (frontmatter_name or "").strip()
    if name and name != sid:
        return name
    return sid


def resolve_skill_display_description(
    skill_id: str,
    frontmatter_description: str = "",
    *,
    max_len: int = 120,
) -> str:
    sid = (skill_id or "").strip()
    if sid in SKILL_DISPLAY_DESCRIPTIONS:
        return SKILL_DISPLAY_DESCRIPTIONS[sid]
    desc = (frontmatter_description or "").strip()
    if len(desc) > max_len:
        return desc[: max_len - 1].rstrip() + "…"
    return desc
