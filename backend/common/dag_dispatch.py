#!/usr/bin/env python3
"""DAG 调度纯函数 — 依赖阻塞与项目终态推导（无 I/O，便于单测）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from common.process_types import TERMINAL_BAD, TERMINAL_OK

if TYPE_CHECKING:
    from common.process_types import TaskOutcome


def deps_block(task: dict, outcomes: dict[str, TaskOutcome], *,
               needs_review_blocks: bool) -> str:
    """上游未就绪时返回阻塞原因；可调度则返回空串。"""
    for dep in task.get("dependencies", []):
        o = outcomes.get(dep)
        if o is None:
            continue
        if o.status in TERMINAL_BAD:
            return f"上游 {dep} 为 {o.status}"
        if o.status == "needs_review" and needs_review_blocks:
            return f"上游 {dep} 待评审（阻塞策略）"
    return ""


def ready_tasks(order: list[str], by_id: dict, outcomes: dict[str, "TaskOutcome"], *,
                needs_review_blocks: bool) -> list[str]:
    """返回当前波次可调度任务 id（全部上游已有 outcome 且未阻塞）。"""
    ready: list[str] = []
    for tid in order:
        if tid in outcomes:
            continue
        task = by_id.get(tid)
        if not task:
            continue
        deps = task.get("dependencies") or []
        if any(dep not in outcomes for dep in deps):
            continue
        if deps_block(task, outcomes, needs_review_blocks=needs_review_blocks):
            continue
        ready.append(tid)
    return ready


def derive_project_status(outcomes: dict[str, TaskOutcome], *,
                          aborted: bool = False,
                          paused: bool = False,
                          cancelled: bool = False) -> str:
    """由任务终态集合推导项目级 status。"""
    statuses = {o.status for o in outcomes.values()}
    if cancelled:
        return "cancelled"
    if aborted:
        return "aborted"
    if paused:
        return "paused"
    if statuses <= TERMINAL_OK:
        return "completed"
    if statuses & {"completed", "needs_review"}:
        return "partially_failed"
    return "failed"
