#!/usr/bin/env python3
"""分级自动补强引擎 — 基于评测结果自动执行补强动作。

分级规则：
  ① 小幅提升（距达标线 3-7 分）：定向调用短板对应 Skill + 补充专项知识库
  ② 提升不足（距达标线 <3 分）：批量拉取全部关联技能 + 完整模块知识库，重载偏好重执行
  ③ 严重不达标（距达标线 >7 分）：全域刷新技能与知识库，从零拆解任务重构交付物
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from common.store import Store
from common.skill_catalog import list_all_skills, get_skill_library_entry

logger = logging.getLogger("execution_harness.post.self_improve")

_IMPROVEMENT_THRESHOLD_MINOR = 3    # 距达标 3-7 → 小幅
_IMPROVEMENT_THRESHOLD_MAJOR = 7    # 距达标 >7 → 严重


@dataclass
class ImprovementAction:
    action_type: str = ""    # "minor" / "major" / "severe"
    target_skills: list[str] = field(default_factory=list)
    kb_fragments: list[str] = field(default_factory=list)
    reload_preferences: bool = False
    full_rebuild: bool = False
    description: str = ""


def classify_defects(defects: list[dict]) -> dict:
    """将缺陷按短板维度分类。"""
    classified = {}
    for d in defects:
        dim = d.get("dimension", "unknown")
        sub = d.get("sub_dim", "")
        if dim not in classified:
            classified[dim] = []
        classified[dim].append({"sub_dim": sub, "detail": d.get("detail", "")})
    return classified


def suggest_skills_for_defects(
    defects: list[dict],
    task_type: str,
) -> list[str]:
    """根据缺陷类型推荐针对性的 Skill。"""
    defect_keywords = {
        "流程图": ["mermaid", "plantuml", "graphviz"],
        "架构图": ["mermaid", "system-architecture"],
        "验收": ["product-methodology", "qa"],
        "异常": ["product-methodology"],
        "数据来源": ["research"],
        "功能清单": ["product-methodology"],
        "落地": ["system-architecture"],
        "优先级": ["product-methodology"],
    }

    suggested = set()
    for d in defects:
        detail = d.get("detail", "") + d.get("sub_dim", "")
        for keyword, skills in defect_keywords.items():
            if keyword in detail:
                for s in skills:
                    entry = get_skill_library_entry(s)
                    if entry:
                        suggested.add(s)

    return list(suggested)[:3]


def suggest_kb_for_defects(
    defects: list[dict],
    task_type: str,
    agent_id: str,
    *,
    store: Optional[Store] = None,
    limit: int = 5,
) -> list[dict]:
    """根据缺陷从 KB 检索补强知识片段。"""
    if store is None:
        store = Store()
    fragments: list[dict] = []
    seen: set = set()

    search_terms = set()
    for d in defects:
        detail = d.get("detail", "") + d.get("sub_dim", "")
        # 提取中文关键词
        import re
        terms = re.findall(r'[\w一-鿿]{2,}', detail)
        search_terms.update(terms)

    for term in list(search_terms)[:5]:
        try:
            entries = store.memory_search(tags=["quality", "lesson", task_type], limit=limit)
            for e in entries:
                eid = e.get("id")
                if eid not in seen:
                    seen.add(eid)
                    content = (e.get("content") or "")[:300]
                    if term in content:
                        fragments.append({
                            "title": e.get("title", ""),
                            "content": content,
                            "matched_term": term,
                        })
        except Exception:
            continue

    return fragments[:limit]


def determine_improvement_level(
    score: float,
    baseline: float,
    defects: list[dict],
    redline_count: int,
) -> ImprovementAction:
    """根据得分和基线决定补强等级。"""
    gap = baseline - score
    action = ImprovementAction()

    severity_count = sum(1 for d in defects if d.get("severity") == "redline")

    if gap > _IMPROVEMENT_THRESHOLD_MAJOR or severity_count >= 2:
        # 严重不达标
        action.action_type = "severe"
        action.full_rebuild = True
        action.reload_preferences = True
        action.description = (
            f"严重不达标：得分{score:.1f}距基线{baseline:.1f}差{gap:+.1f}分，"
            f"{severity_count}条红线。需全域刷新技能与知识库，从零拆解重构。"
        )
    elif gap > _IMPROVEMENT_THRESHOLD_MINOR:
        # 小幅提升
        action.action_type = "minor"
        action.target_skills = suggest_skills_for_defects(defects, "")
        action.kb_fragments = [f.get("content", "") for f in suggest_kb_for_defects(defects, "", "")]
        action.description = (
            f"小幅提升：得分{score:.1f}距基线{baseline:.1f}差{gap:+.1f}分，"
            f"定向补强 {action.target_skills} + {len(action.kb_fragments)}条KB知识"
        )
    else:
        # 提升不足，批量补强
        action.action_type = "major"
        action.target_skills = list_all_skills()[:5]
        action.reload_preferences = True
        action.description = (
            f"提升不足：得分{score:.1f}距基线{baseline:.1f}差{gap:+.1f}分，"
            f"批量拉取全部关联技能 + 完整知识库，重载偏好重执行"
        )

    return action


def build_improvement_prompt(
    action: ImprovementAction,
    original_task: str,
    eval_summary: str,
    defects: list[dict],
) -> str:
    """构造补强提示词，让 agent 重新执行。"""
    lines = [
        "【补强执行 — 基于上一轮评估结果重新交付】",
        "",
        f"原任务：{original_task}",
        "",
        "上一轮评估结果：",
        eval_summary,
        "",
    ]

    if defects:
        lines.append("需要修复的缺陷：")
        for d in defects[:8]:
            lines.append(f"  - [{d.get('severity','')}] {d.get('sub_dim')}: {d.get('detail')}")
        lines.append("")

    if action.full_rebuild:
        lines.append("【重新执行要求】")
        lines.append("请忽略之前的所有输出，从零开始重新设计完整方案。")
        lines.append("必须包含：业务背景、目标用户、核心痛点、解决方案、架构图(Mermaid)、")
        lines.append("流程图(Mermaid)、In/Out of Scope、功能清单(P0/P1/P2)、异常分支、验收标准。")

    if action.target_skills:
        skill_names = []
        for sid in action.target_skills[:5]:
            entry = get_skill_library_entry(sid) if isinstance(sid, str) else None
            if entry:
                skill_names.append(f"{entry.get('name','')}({sid})")
        if skill_names:
            lines.append(f"参考 Skill：{', '.join(skill_names)}")

    if action.kb_fragments:
        lines.append("参考知识片段：")
        for frag in action.kb_fragments[:3]:
            lines.append(f"  - {frag[:200]}")

    if action.reload_preferences:
        lines.append("已重新加载全部用户偏好，请严格遵循。")

    lines.append("")
    lines.append("直接输出完整内容。")

    return "\n".join(lines)