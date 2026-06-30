#!/usr/bin/env python3
"""任务前置资产加载 — 接收任务后依次执行：加载全量用户偏好库→语义匹配Skill→检索知识库。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from common.store.store import Store
from common.agent.agent_registry import get_agent_info
from common.skill.skill_catalog import list_all_skills
from common.paths import MYTEAM_ROOT

logger = logging.getLogger("execution_harness.pre.self_improve")

_PREFERENCE_KEYWORDS = {
    "prd": {"prd", "需求", "product", "product-methodology"},
    "research": {"调研", "research", "竞品"},
    "competitive-analysis": {"竞品", "competitive"},
    "requirements": {"需求", "requirements"},
    "product-planning": {"规划", "规划"},
    "business-diagnosis": {"诊断", "diagnosis"},
}


def load_preferences(agent_id: str, task_type: str = "") -> list[str]:
    """加载全量用户偏好库。

    从 agent 工作区的 USER.md + 数据库偏好表 加载。
    """
    prefs: list[str] = []

    # 1. 从 USER.md 加载
    user_md = MYTEAM_ROOT / "business" / "workspaces" / f"workspace-{agent_id}" / "USER.md"
    if user_md.is_file():
        text = user_md.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            prefs.append(text.strip())

    # 2. 从 Store 的偏好表加载
    store = Store()
    try:
        stored = store.get_preferences(agent_id) if hasattr(store, "get_preferences") else None
        if stored and isinstance(stored, str) and stored.strip():
            prefs.append(stored.strip())
    except Exception:
        pass

    # 3. 从 KB 加载偏好相关条目
    if task_type:
        try:
            kb = store.memory_search(tags=["preference", agent_id, task_type], limit=5)
            for e in kb:
                content = (e.get("content") or "").strip()
                if content:
                    prefs.append(f"[KB偏好] {content[:300]}")
        except Exception:
            pass

    logger.info("loaded %d preferences for %s", len(prefs), agent_id)
    return prefs


def semantic_match_skills(task_type: str, intent: str = "") -> list[dict]:
    """语义匹配并调取相关 Skill 库。

    通过 task_type 映射 + intent 关键词匹配，返回最相关的 3-5 个 Skill。
    """
    all_skills = list_all_skills()
    if not all_skills:
        return []

    intent_lower = intent.lower()
    type_keywords = _PREFERENCE_KEYWORDS.get(task_type, {task_type})

    scored: list[tuple[float, dict]] = []
    for s in all_skills:
        score = 0.0
        sid = (s.get("id") or "").lower()
        name = (s.get("name") or "").lower()
        desc = (s.get("description") or "").lower()
        body_all = f"{sid} {name} {desc}"

        # task_type 匹配：+3
        for kw in type_keywords:
            if kw in body_all:
                score += 3.0
                break

        # intent 关键词匹配：+1/个
        if intent_lower:
            words = set(re.findall(r'[\w一-鿿]+', intent_lower))
            hits = sum(1 for w in words if len(w) > 1 and w in body_all)
            score += hits * 1.0

        # 新近度加成（新 skill 优先）
        updated = s.get("updated_at", 0)
        if isinstance(updated, (int, float)) and updated > 0:
            score += 0.1

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: -x[0])
    top = [s for _, s in scored[:5]]

    logger.info("semantic matched %d skills for task_type=%s", len(top), task_type)
    return top


def retrieve_knowledge(
    task_type: str,
    agent_id: str,
    *,
    store: Optional[Store] = None,
    limit: int = 10,
) -> list[dict]:
    """检索对应业务知识库。

    按优先级检索：
    1. quality 标签（历史质量画像）
    2. rubric 标签（历史评分）
    3. lesson 标签（经验教训）
    4. 泛 task_type 匹配
    """
    if store is None:
        store = Store()
    entries: list[dict] = []

    tag_sets = [
        ["quality", "rubric", agent_id, task_type],
        ["quality", agent_id, task_type],
        ["lesson", task_type, agent_id],
        ["preference", agent_id, task_type],
    ]

    seen_ids: set = set()
    for tags in tag_sets:
        try:
            batch = store.memory_search(tags=tags, limit=limit)
            for e in batch:
                eid = e.get("id")
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    entries.append(e)
                    if len(entries) >= limit:
                        return entries
        except Exception:
            continue

    # Fallback: task_type 泛匹配
    try:
        fallback = store.memory_search(tags=[task_type], limit=limit // 2)
        for e in fallback:
            eid = e.get("id")
            if eid not in seen_ids:
                seen_ids.add(eid)
                entries.append(e)
    except Exception:
        pass

    return entries[:limit]


def merge_constraints(
    agent_id: str,
    task_type: str,
    task_name: str,
    *,
    intent: str = "",
    store: Optional[Store] = None,
) -> dict:
    """三步前置资产加载入口：偏好→Skill→KB → 合并约束。

    Returns:
        {"preferences": [...], "skills": [...], "kb": [...], "constraints_text": str}
    """
    if store is None:
        store = Store()

    # 1. 加载偏好
    prefs = load_preferences(agent_id, task_type)

    # 2. 匹配 Skill
    skills = semantic_match_skills(task_type, intent)

    # 3. 检索知识库
    kb = retrieve_knowledge(task_type, agent_id, store=store)

    # 4. 合并约束文本
    lines = ["【本次执行约束 — 由前置资产合并生成】", ""]

    if prefs:
        lines.append("【用户偏好】")
        for p in prefs:
            lines.append(p)
        lines.append("")

    if skills:
        lines.append("【关联 Skill】")
        for s in skills:
            spath = s.get("path", "")
            desc = s.get("description", "")
            lines.append(f"  - {s.get('name')} ({s.get('id')}): {desc}")
            if spath:
                lines.append(f"    路径: {spath}")
        lines.append("")

    if kb:
        lines.append("【参考知识库】")
        for e in kb:
            t = e.get("title", "entry")
            content = (e.get("content") or "").strip().replace("\n", " ")
            lines.append(f"  - {t}: {content[:200]}")
        lines.append("")

    lines.append("【质量标准 — 红线】")
    lines.append("  - 禁止编造无来源数据（行业数据须标注报告/官网来源）")
    lines.append("  - 流程图须用结构化 DSL（Mermaid/PlantUML/Graphviz），纯 ASCII → 缺陷")
    lines.append("  - 重复检索阈值 N 按偏好配置，仅语义无新增信息算冗余")
    lines.append("  - 必须覆盖异常场景和边界条件")
    lines.append("")

    return {
        "preferences": prefs,
        "skills": [{"id": s.get("id"), "name": s.get("name")} for s in skills],
        "kb": [{"title": e.get("title"), "content": (e.get("content") or "")[:200]} for e in kb],
        "constraints_text": "\n".join(lines),
    }