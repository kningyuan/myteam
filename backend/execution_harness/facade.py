#!/usr/bin/env python3
"""execution_harness facade — Layer A 对执行质量层的唯一入口。"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from execution_harness.config import harness_enabled
from execution_harness.context import ExecuteHarnessContext, TaskCompleteContext
from execution_harness.post.promote import promote_task_artifacts
from execution_harness.post.review import schedule_skill_review
from execution_harness.post.lesson import write_lesson_entry
from execution_harness.config import lesson_promote_enabled
from execution_harness.pre.prepare import prepare_execute
from execution_harness.pre.inject import inject_execute_prompt

logger = logging.getLogger("execution_harness.facade")


def enabled() -> bool:
    return harness_enabled()


def prepare_execute_harness(ctx: ExecuteHarnessContext) -> dict:
    """H-PRE — execute 派发前（workspace identity + prompt 块）。"""
    try:
        return prepare_execute(ctx)
    except Exception as e:
        logger.warning("prepare_execute_harness failed: %s", e)
        return {}


def inject_for_execute(ctx: ExecuteHarnessContext) -> None:
    """H-PRE — 仅 prompt 注入（build_worker_prompt 内调用）。"""
    try:
        inject_execute_prompt(ctx)
    except Exception as e:
        logger.warning("inject_for_execute failed: %s", e)


def on_task_complete(
    ctx: TaskCompleteContext,
    *,
    port_run: Optional[Callable[[dict], Any]] = None,
) -> Optional[str]:
    """H-POST — execute 成功后：promote + lesson 沉淀 + 可选 skill_review。"""
    ref: Optional[str] = None
    try:
        ref = promote_task_artifacts(ctx)
    except Exception as e:
        logger.warning("promote_task_artifacts failed: %s", e)
    try:
        if lesson_promote_enabled() and ctx.gate_passed and ctx.attempt and ctx.attempt > 1:
            mem_id = write_lesson_entry(
                store=ctx.store,
                project_id=ctx.project_id,
                task_id=ctx.task_id,
                task_type=ctx.task_type,
                agent_id=ctx.agent_id,
                base_dir=ctx.base_dir,
                attempt=ctx.attempt,
            )
            if mem_id is not None:
                logger.info(
                    "lesson written to kb for %s/%s (mem_id=%s)",
                    ctx.project_id, ctx.task_id, mem_id,
                )
    except Exception as e:
        logger.warning("write_lesson_entry failed: %s", e)
    try:
        schedule_skill_review(ctx, ctx.store, port_run=port_run, daemon=True)
    except Exception as e:
        logger.warning("schedule_skill_review failed: %s", e)
    return ref
