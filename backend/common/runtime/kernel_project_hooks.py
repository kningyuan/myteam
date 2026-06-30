#!/usr/bin/env python3
"""内核默认 ProjectHooks — CLI 与 Hub 共用（建群 + loop 群讨论）。"""
from __future__ import annotations

import logging

from common.loop.loop_discussion_dispatch import dispatch_loop_round_done
from common.loop.loop_discussion_runtime import setup_project_group_if_needed
from common.project.project_hooks import ProjectHooks

logger = logging.getLogger("kernel_project_hooks")


def _on_team_ready(project_id: str, agents: list[str], title: str) -> None:
    setup_project_group_if_needed(project_id, agents, title)


def _on_task_done(project_id: str, task_id: str, status: str, agent_id: str) -> None:
    if status != "completed":
        return
    try:
        from hub.services.project_group_service import format_progress_message, post_project_progress

        msg = format_progress_message("task_complete", project_id, agent_id=agent_id, task_id=task_id)
        post_project_progress(project_id, msg, sender=agent_id or "system")
    except Exception as e:
        logger.debug("post_project_progress skipped: %s", e)


def _on_loop_round_done(
    project_id: str,
    loop_id: str,
    round_num: int,
    passed: bool,
    work_task_id: str,
    review_task_id: str,
) -> None:
    max_rounds = 5
    try:
        from common.store.store import Store
        from common.workflow.workflow_loader import load_workflow

        store = Store()
        try:
            proj = store.get_project(project_id) or {}
            wf_id = (proj.get("meta") or {}).get("workflow")
            if wf_id:
                spec = next(
                    (lp for lp in load_workflow(wf_id).loops if lp.id == loop_id),
                    None,
                )
                if spec:
                    max_rounds = spec.max_rounds
        finally:
            store.close()
    except Exception:
        pass
    dispatch_loop_round_done(
        project_id,
        loop_id,
        round_num,
        passed=passed,
        work_task_id=work_task_id,
        review_task_id=review_task_id,
        max_rounds=max_rounds,
    )


def kernel_project_hooks() -> ProjectHooks:
    return ProjectHooks(
        on_team_ready=_on_team_ready,
        on_task_done=_on_task_done,
        on_loop_round_done=_on_loop_round_done,
    )
