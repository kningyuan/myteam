#!/usr/bin/env python3
"""PRE — execute 前 workspace 准备。"""
from __future__ import annotations

import logging
from pathlib import Path

from common.paths import workspace_dir
from execution_harness.config import execute_harness_enabled
from execution_harness.context import ExecuteHarnessContext
from execution_harness.identity.bounded import sync_bounded_identity
from execution_harness.skill.umbrella import resolve_umbrella_skill

logger = logging.getLogger("execution_harness.pre.prepare")


def prepare_execute(ctx: ExecuteHarnessContext) -> dict:
    """CLI 派发前：刷新 workspace identity 文件。prompt 注入由 inject_for_execute 负责。"""
    summary: dict = {"identity": {}, "umbrella": None}
    if not execute_harness_enabled():
        return summary
    try:
        ws = ctx.workspace or Path(workspace_dir(ctx.agent_id))
        ctx.workspace = ws
        summary["identity"] = sync_bounded_identity(
            ctx.agent_id,
            owner_id=ctx.owner_id or ctx.agent_id,
            workspace=ws,
        )
        summary["umbrella"] = resolve_umbrella_skill(ctx.task_type)
    except Exception as e:
        logger.warning("prepare_execute failed: %s", e)
    return summary
