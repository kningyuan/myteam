"""Hub 默认 ProjectHooks：自动建群 + 群进度通报。"""
from __future__ import annotations

import logging

from common.project_hooks import ProjectHooks

logger = logging.getLogger("project_hooks")


def hub_project_hooks() -> ProjectHooks:
    return ProjectHooks(
        on_team_ready=_on_team_ready,
        on_task_done=_on_task_done,
        on_wave=_on_wave,
    )


def _on_team_ready(project_id: str, agents: list[str], title: str) -> None:
    try:
        from hub.services.project_group_service import setup_project_group

        ok, msg, _gid = setup_project_group(project_id, agents, project_name=title)
        if ok and _gid:
            logger.info("project %s group ready: %s", project_id, msg)
    except Exception as e:
        logger.warning("setup_project_group failed for %s: %s", project_id, e)


def _on_task_done(project_id: str, task_id: str, status: str, agent_id: str) -> None:
    try:
        from hub.services.project_group_service import format_progress_message, post_project_progress

        if status == "completed":
            evt = "task_complete"
        elif status in ("failed", "blocked"):
            evt = "task_failed"
        else:
            return
        msg = format_progress_message(evt, project_id, agent_id=agent_id, task_id=task_id)
        post_project_progress(project_id, msg)
    except Exception as e:
        logger.debug("post_project_progress skipped: %s", e)


def _on_wave(project_id: str, wave: list[str]) -> None:
    if len(wave) <= 1:
        return
    try:
        from hub.services.project_group_service import post_project_progress

        post_project_progress(project_id, f"⚡ 并行波次（{len(wave)} 任务）：{', '.join(wave)}")
    except Exception as e:
        logger.debug("wave progress skipped: %s", e)
