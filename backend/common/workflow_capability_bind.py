#!/usr/bin/env python3
"""将 workflow 任务步骤绑定到 Agent 已声明的 task_types（与 plan_gate 一致）。"""
from __future__ import annotations

import json
from copy import deepcopy

from common.agent_registry import agent_task_type_map, list_available_agent_ids
from common.paths import BUSINESS_CONFIG_DIR

_PRIORITY_CACHE: dict[str, list[str]] | None = None


def _load_task_type_agent_priority() -> dict[str, list[str]]:
    global _PRIORITY_CACHE
    if _PRIORITY_CACHE is not None:
        return _PRIORITY_CACHE
    path = BUSINESS_CONFIG_DIR / "task_type_agent_priority.json"
    if path.is_file():
        try:
            _PRIORITY_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return _PRIORITY_CACHE
        except (OSError, json.JSONDecodeError):
            pass
    _PRIORITY_CACHE = {}
    return _PRIORITY_CACHE


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
    priority = _load_task_type_agent_priority()
    candidates: list[str] = []
    if prefer:
        candidates.append(prefer)
    candidates.extend(priority.get(tt, []))
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
