#!/usr/bin/env python3
"""POST — ledger promote + KB + references/。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from common.store.store import Store
from execution_harness.context import TaskCompleteContext
from execution_harness.skill.references import write_reference_from_ledger
from execution_harness.skill.umbrella import resolve_umbrella_skill

logger = logging.getLogger("execution_harness.post.promote")


def promote_task_artifacts(ctx: TaskCompleteContext) -> Optional[str]:
    """Gate 通过后沉淀：references/ + KB ledger。"""
    if not ctx.gate_passed:
        return None
    ref_path: Optional[Path] = None
    umbrella = resolve_umbrella_skill(ctx.task_type)
    if umbrella:
        try:
            ref_path = write_reference_from_ledger(
                umbrella, ctx.base_dir, ctx.task_type, ctx.task_id
            )
        except Exception as e:
            logger.warning("write reference failed: %s", e)
    kb_ref: Optional[str] = None
    try:
        from memstack.orchestration.experience import promote_ledger_to_memory

        kb_ref = promote_ledger_to_memory(
            ctx.base_dir,
            ctx.project_id,
            ctx.task_id,
            ctx.task_type,
            ctx.store,
        )
    except Exception as e:
        logger.warning("promote ledger to kb failed: %s", e)
    if kb_ref:
        return kb_ref
    if ref_path is not None:
        return f"reference:{ref_path}"
    return None
