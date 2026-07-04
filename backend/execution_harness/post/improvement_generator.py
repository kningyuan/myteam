#!/usr/bin/env python3
"""从 rubric 评估结果生成可执行的改进建议。

输入: RubricResult (来自 rubric_eval.evaluate_deliverable) + 交付物原文
输出: list[ImprovementSuggestion] — 每个建议包含维度、问题描述、修复方法
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from execution_harness.post.rubric_eval import RubricResult


@dataclass
class ImprovementSuggestion:
    """一条改进建议。"""
    dimension: str           # 评估维度名称
    what_to_fix: str         # 要修什么（问题描述）
    how_to_fix: str          # 怎么修（具体方法）
    priority: str = "normal"  # high / normal / low


def generate_improvements(
    rubric_result: "RubricResult",
    deliverable_content: str,
    *,
    task_type: str = "",
    max_suggestions: int = 10,
) -> list[ImprovementSuggestion]:
    """从 rubric 评估结果中提取可修复的缺陷，生成改进建议。

    Args:
        rubric_result: RubricResult 实例（来自 rubric_eval.evaluate_deliverable）
        deliverable_content: 交付物原文（用于上下文分析）
        task_type: 任务类型（影响建议模板）
        max_suggestions: 最多返回的建议条数

    Returns:
        改进建议列表，按优先级排序
    """
    # Lazy import to avoid circular dependency

    suggestions: list[ImprovementSuggestion] = []
    seen_what: set[str] = set()

    # ── 1. 从 dimension_failures 提取建议 ──
    for dim, failures in rubric_result.dimension_failures.items():
        for failure in failures:
            what = f"[{dim}] {failure}"
            if what in seen_what:
                continue
            seen_what.add(what)

            how = _suggest_how_to_fix(dim, failure, deliverable_content, task_type)
            if not how:
                continue

            priority = _infer_priority(dim, failure, rubric_result.hit_redlines)
            suggestions.append(ImprovementSuggestion(
                dimension=dim,
                what_to_fix=what,
                how_to_fix=how,
                priority=priority,
            ))

    # ── 2. 从 redlines 提取建议 ──
    for redline in rubric_result.hit_redlines:
        what = f"[红线] {redline}"
        if what in seen_what:
            continue
        seen_what.add(what)

        how = _suggest_redline_fix(redline, deliverable_content)
        if how:
            suggestions.append(ImprovementSuggestion(
                dimension="红线",
                what_to_fix=what,
                how_to_fix=how,
                priority="high",
            ))

    # ── 3. 从 missing_items 提取建议 ──
    for item in rubric_result.missing_items:
        what = f"[缺失] {item}"
        if what in seen_what:
            continue
        seen_what.add(what)

        how = _suggest_missing_fix(item, deliverable_content)
        if how:
            suggestions.append(ImprovementSuggestion(
                dimension="完整性",
                what_to_fix=what,
                how_to_fix=how,
                priority="normal",
            ))

    # ── 4. 从交付物内容本身提取通用建议（始终运行，不受 feedback 控制） ──
    generic = _extract_generic_suggestions(rubric_result.feedback or "", deliverable_content)
    for g in generic:
        if g.what_to_fix not in seen_what:
            seen_what.add(g.what_to_fix)
            suggestions.append(g)

    # ── 5. 去重 + 排序 + 截断 ──
    priority_order = {"high": 0, "normal": 1, "low": 2}
    suggestions.sort(key=lambda s: (priority_order.get(s.priority, 1), s.dimension))

    return suggestions[:max_suggestions]


def _suggest_how_to_fix(
    dimension: str,
    failure: str,
    content: str,
    task_type: str,
) -> str:
    """根据维度和失败原因生成具体修复建议。"""
    dim_hints: dict[str, list[tuple[str, str]]] = {
        "需求目标匹配度": [
            ("未标注业务约束", "在文档开头增加【业务约束与边界】小节，明确列出系统边界、前提条件和不做的事项。"),
            ("未识别目标用户", "补充【目标用户/角色】章节，使用用户画像或角色定义描述目标人群。"),
        ],
        "交付物完整度": [
            ("缺失章节", f"根据模板要求补充缺失章节。task_type={task_type} 对应的标准章节请参考 rubric 模板。"),
            ("流程图未使用结构化", "将文字描述的流程图替换为 Mermaid/PlantUML/Graphviz 代码块。"),
        ],
        "专业准确率": [
            ("缺少来源标注", "请将所有行业数据、市场数据补充来源标注，格式如：（来源：XXX报告/官网）。"),
            ("模糊不可量化词", "将「提升体验」「更加便捷」等模糊表述替换为可量化的指标，如「将页面加载时间从 3s 降至 1s」。"),
        ],
        "落地可行性": [
            ("未考虑落地约束", "增加【落地约束与技术方案】章节，讨论技术成本、现有系统限制、分阶段实施计划。"),
        ],
        "任务拆解": [
            ("缺少任务拆解", "将方案拆分为明确的阶段（阶段一/阶段二/阶段三），每阶段列出可交付物。"),
            ("未标注优先级", "功能清单中为每项标注 P0/P1/P2 优先级，P0 为必须实现的核心功能。"),
        ],
        "信息调研": [
            ("未标注信息缺口", "增加【已知不足与信息缺口】章节，诚实列出尚未获取到的数据和需要进一步调研的内容。"),
        ],
        "产品思维完整性": [
            ("产品思维不完整", "确保覆盖四个要素：目标用户定位、核心痛点拆解、对应解决方案、效果衡量数据指标。"),
        ],
        "思考可解释性": [
            ("缺少推导依据", "在功能决策后增加「为什么这样做」的解释段落，使用「基于」「因为」「考虑到」等推导词。"),
        ],
        "执行效率": [
            ("执行轮次过多", "减少不必要的迭代，一次交付完整方案而非分步猜测。"),
            ("重试次数过多", "执行前充分理解需求，避免因理解偏差导致的多次重试。"),
            ("含过多无关科普", "删除「什么是XX」「XX是指」等科普内容，直接进入方案本身。"),
        ],
        "业务鲁棒性": [
            ("未覆盖异常场景", "增加【异常场景与边界条件】章节，覆盖空数据、失败、无权限、超时等场景。"),
        ],
        "合规与风险": [
            ("未标注合规风险", "增加【合规与风险】章节，讨论隐私、数据安全、权限管控等问题。"),
        ],
        "交付可复用": [
            ("章节结构不清晰", "使用清晰的 Markdown 标题层级（# ## ###），确保文档至少有 3 个以上的一二级标题。"),
        ],
    }

    for dim_rules in dim_hints.get(dimension, []):
        if dim_rules[0] in failure:
            return dim_rules[1]

    # Generic fallback
    return f"修复 [{dimension}] 问题：{failure}。请仔细阅读失败原因，针对性修改交付物内容。"


def _suggest_redline_fix(redline: str, content: str) -> str:
    """针对红线问题的修复建议。"""
    if "编造" in redline or "无来源" in redline or "数据无来源标注" in redline:
        return (
            "红线：数据必须标注来源。请将所有没有来源标注的数据删除或补充来源。"
            "格式示例：「据 XXX 报告，2024 年市场规模为 500 亿元（来源：XXX 研究院 2024 报告）」"
        )
    if "纯ASCII" in redline:
        return "红线：禁止使用纯 ASCII 图表。请将 ASCII 图表替换为 Mermaid/PlantUML/Graphviz 代码块。"
    if "不覆盖异常" in redline:
        return "红线：必须覆盖异常场景。请增加空数据、失败、无权限、超时等边界条件的处理说明。"
    if "流程图" in redline or "DSL" in redline:
        return "红线：流程图必须使用结构化 DSL（Mermaid/PlantUML/Graphviz），请将文字描述替换为代码块。"
    return f"红线修复：{redline}。这是严重问题，请务必彻底解决后重新提交。"


def _suggest_missing_fix(item: str, content: str) -> str:
    """针对缺失项的修复建议。"""
    if "缺失章节" in item:
        chapter = item.replace("缺失章节：", "")
        return f"请在交付物中补充「{chapter}」章节。参考标准模板结构，确保内容完整。"
    return f"请补充缺失项：{item}。"


def _extract_generic_suggestions(
    feedback: str,
    content: str,
) -> list[ImprovementSuggestion]:
    """从反馈文本中提取通用改进建议。"""
    suggestions: list[ImprovementSuggestion] = []

    # Detect overly short content
    if len(content) < 500 and content.strip():
        suggestions.append(ImprovementSuggestion(
            dimension="内容充实度",
            what_to_fix="交付物内容过短，可能缺乏深度分析",
            how_to_fix="扩展每个章节的内容，增加具体的数据、案例、分析过程。建议至少 1000 字。",
            priority="normal",
        ))

    # Detect lack of structure
    heading_count = len(re.findall(r"^#{1,3}\s", content, re.MULTILINE))
    if heading_count < 3:
        suggestions.append(ImprovementSuggestion(
            dimension="文档结构",
            what_to_fix=f"文档标题结构薄弱（仅 {heading_count} 个一二级标题），建议至少 3 个",
            how_to_fix="使用清晰的 Markdown 标题层级组织内容，至少包含：# 标题、## 章节标题。",
            priority="normal",
        ))

    return suggestions


def _infer_priority(
    dimension: str,
    failure: str,
    redlines: list[str],
) -> str:
    """根据问题和红线推断建议优先级。"""
    # High if related to redlines
    if redlines:
        return "high"

    # High for critical dimensions
    critical_dims = {"业务鲁棒性", "专业准确率", "合规与风险"}
    if dimension in critical_dims:
        return "high"

    return "normal"


def format_improvement_prompt(suggestions: list[ImprovementSuggestion]) -> str:
    """将改进建议列表格式化为 agent 可读的 prompt 片段。

    用于注入到下一轮 agent 执行的约束中。
    """
    if not suggestions:
        return ""

    lines = [
        "【自我提升 — 基于评估结果的改进要求】",
        "",
        "上一轮评估发现以下问题，请逐一修复：",
        "",
    ]

    high_count = 0
    for i, s in enumerate(suggestions, 1):
        marker = "【高优先级】" if s.priority == "high" else "【建议】"
        lines.append(f"{marker} #{i} [{s.dimension}]")
        lines.append(f"  问题：{s.what_to_fix}")
        lines.append(f"  修复方法：{s.how_to_fix}")
        lines.append("")
        if s.priority == "high":
            high_count += 1

    if high_count:
        lines.append(
            f"注意：以上 {high_count} 条为高优先级修复项，必须在下一轮交付中完全解决。"
        )

    return "\n".join(lines)
