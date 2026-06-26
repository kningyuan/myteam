#!/usr/bin/env python3
"""达标后能力沉淀 — 将最优技能组合/合格案例/修复规则存入知识库。"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from common.store import Store

logger = logging.getLogger("execution_harness.post.capability_pool")

_POOL_TAG = "capability_pool"


def store_optimal_skills(
    agent_id: str,
    task_type: str,
    skill_combo: list[str],
    score: float,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """将本次最优技能组合存入知识库。"""
    if store is None:
        store = Store()
    content = json.dumps({
        "agent_id": agent_id,
        "task_type": task_type,
        "skills": skill_combo,
        "score": score,
        "timestamp": time.time(),
    }, ensure_ascii=False)
    return store.memory_write(
        "",
        f"optimal_skills:{agent_id}/{task_type}",
        content,
        tags=[_POOL_TAG, "optimal_skills", task_type, agent_id],
    )


def store_case(
    agent_id: str,
    task_type: str,
    task_id: str,
    score: float,
    defects: list[dict],
    output_snippet: str,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """将合格交付案例存入知识库。"""
    if store is None:
        store = Store()
    content_lines = [
        f"agent_id: {agent_id}",
        f"task_type: {task_type}",
        f"task_id: {task_id}",
        f"score: {score}",
        f"defect_count: {len(defects)}",
        "---",
        "合格案例摘要：",
        output_snippet[:500],
    ]
    return store.memory_write(
        "",
        f"case:{agent_id}/{task_type}:{task_id}",
        "\n".join(content_lines),
        tags=[_POOL_TAG, "case", task_type, agent_id],
    )


def store_defect_mapping(
    agent_id: str,
    task_type: str,
    defects: list[dict],
    fix_skills: list[str],
    fix_kb: list[str],
    score_before: float,
    score_after: float,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """留存缺陷修复映射规则，后续同类任务提前规避。"""
    if store is None:
        store = Store()
    content_lines = [
        f"agent_id: {agent_id}",
        f"task_type: {task_type}",
        f"score_before: {score_before}",
        f"score_after: {score_after}",
        f"fix_skills: {', '.join(fix_skills)}",
        f"fix_kb_fragments: {len(fix_kb)}",
        "---",
        "可复用的修复模式：",
    ]

    # 总结可复用的修复规则
    for d in defects:
        sub = d.get("sub_dim", "")
        detail = d.get("detail", "")
        if d.get("severity") in ("redline", "warning"):
            content_lines.append(f"- 【{sub}】{detail} → 下一次执行时应避免")

    return store.memory_write(
        "",
        f"fix_rules:{agent_id}/{task_type}:{hash(str(defects)) % 100000}",
        "\n".join(content_lines),
        tags=[_POOL_TAG, "fix_rules", task_type, agent_id],
    )


def update_baseline_from_score(
    score: float,
    task_type: str,
    agent_id: str,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """更新基线分数（滚动平均）。"""
    from execution_harness.post.self_eval import fetch_baseline, update_baseline

    if store is None:
        store = Store()
    current = fetch_baseline(task_type, agent_id, store=store)
    # 滚动平均值：新基线 = old * 0.7 + new * 0.3
    new_baseline = round(current * 0.7 + score * 0.3, 1)
    return update_baseline(new_baseline, task_type, agent_id, store=store)


def store_full_report(
    agent_id: str,
    task_type: str,
    task_id: str,
    report_data: dict,
    *,
    store: Optional[Store] = None,
) -> Optional[int]:
    """将完整量化报表存入知识库。"""
    if store is None:
        store = Store()
    content = json.dumps(report_data, ensure_ascii=False)
    return store.memory_write(
        "",
        f"report:{agent_id}/{task_type}:{task_id}",
        content,
        tags=[_POOL_TAG, "report", task_type, agent_id],
    )