"""Hub 默认 ProjectHooks：自动建群 + 群进度通报 + loop 群讨论。"""
from __future__ import annotations

import logging

from common.runtime.kernel_project_hooks import kernel_project_hooks
from common.project.project_hooks import ProjectHooks

logger = logging.getLogger("project_hooks")


def hub_project_hooks() -> ProjectHooks:
    base = kernel_project_hooks()
    return ProjectHooks(
        on_team_ready=base.on_team_ready,
        on_task_done=base.on_task_done,
        on_wave=_on_wave,
        on_loop_round_done=base.on_loop_round_done,
    )


def _on_wave(project_id: str, wave: list[str]) -> None:
    if len(wave) <= 1:
        return
    try:
        from hub.services.project_group_service import post_project_progress

        post_project_progress(project_id, f"⚡ 并行波次（{len(wave)} 任务）：{', '.join(wave)}")
    except Exception as e:
        logger.debug("wave progress skipped: %s", e)
