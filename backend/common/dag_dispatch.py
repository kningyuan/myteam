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
