#!/usr/bin/env python3
"""将 workflow 任务步骤绑定到 Agent 已声明的 task_types（与 plan_gate 一致）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from common.agent_registry import agent_task_type_map, list_available_agent_ids

# task_type → 优先尝试的 agent_id（须已在 workspace 且勾选对应类型）
TASK_TYPE_AGENT_PRIORITY: dict[str, list[str]] = {
    "research": ["research", "product", "analyst", "arch", "developer", "geo", "seo"],
    "strategy": ["product", "main", "analyst"],
    "requirements": ["product"],
    "system-design": ["arch", "developer", "frontend"],
    "architecture-review": ["arch", "product", "qa", "frontend"],
    "code-writing": ["developer", "frontend", "analyst"],
    "code-review": ["arch", "developer", "qa", "frontend"],
    "code-testing": ["qa", "tester"],
    "test-plan": ["qa", "tester"],
    "content": ["content", "geo", "docs"],
    "publish-post": ["social_zhihu", "social_xhs", "social"],
    "acceptance-report": ["product"],
    "decision-record": ["main"],
    "code-deployment": ["main", "ops"],
    "data-analysis": ["analyst"],
    "geo-plan": ["geo"],
    "geo-audit": ["geo"],
    "geo-verification": ["geo"],
    "seo-plan": ["seo"],
}


def _agent_can(cap_map: dict[str, list[str]], available: set[str], aid: str, tt: str) -> bool:
    if not aid or aid not in available:
        return False
    allowed = cap_map.get(aid)
    if not allowed:
        return False
    return tt in allowed


def _pick_agent_for_task_type(
    tt: str,
    *,
    cap_map: dict[str, list[str]],
    available: set[str],
    prefer: str = "",
) -> str:
    candidates: list[str] = []
    if prefer:
        candidates.append(prefer)
    candidates.extend(TASK_TYPE_AGENT_PRIORITY.get(tt, []))
    for aid in cap_map:
        if aid not in candidates:
            candidates.append(aid)
    for aid in candidates:
        if _agent_can(cap_map, available, aid, tt):
            return aid
    return ""


def bind_workflow_tasks_to_capabilities(tasks: list[dict]) -> list[dict]:
    """按注册表 task_types 校正每步 agent / task_type，使推导结果可过 plan_gate。"""
    cap_map = agent_task_type_map()
    available = set(list_available_agent_ids())
    out = deepcopy(tasks)

    for t in out:
        aid = str(t.get("agent") or "").strip()
        tt = str(t.get("task_type") or "").strip()
        if not tt:
            continue

        if _agent_can(cap_map, available, aid, tt):
            continue

        replacement = _pick_agent_for_task_type(
            tt, cap_map=cap_map, available=available, prefer=aid,
        )
        if replacement:
            t["agent"] = replacement
            continue

        allowed = cap_map.get(aid) or []
        if allowed and aid in available:
            t["task_type"] = allowed[0]
            continue

        replacement = _pick_agent_for_task_type(tt, cap_map=cap_map, available=available)
        if replacement:
            t["agent"] = replacement

    return out


def capability_bind_warnings(tasks: list[dict]) -> list[str]:
    """推导后仍无法绑定的步骤（供 UI 提示）。"""
    cap_map = agent_task_type_map()
    available = set(list_available_agent_ids())
    warnings: list[str] = []
    for t in tasks:
        aid = str(t.get("agent") or "").strip()
        tt = str(t.get("task_type") or "").strip()
        if not aid or not tt:
            continue
        if aid not in available:
            warnings.append(f"任务「{t.get('id', '?')}」：Agent「{aid}」无 workspace")
            continue
        allowed = cap_map.get(aid)
        if not allowed:
            warnings.append(f"任务「{t.get('id', '?')}」：Agent「{aid}」未配置可执行任务类型")
        elif tt not in allowed:
            warnings.append(
                f"任务「{t.get('id', '?')}」：{aid} 不能执行「{tt}」（仅允许：{', '.join(allowed)}）",
            )
    return warnings
