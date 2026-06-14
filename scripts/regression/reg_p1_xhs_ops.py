#!/usr/bin/env python3
"""REG-P1-XHS：小红书运营 workflow。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "regression"))
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402
from reg_workflow_common import reg_main, task_statuses  # noqa: E402

WORKFLOW = "小红书运营"
PROJECT_ID = os.environ.get("REG_P1_XHS_PROJECT_ID", "reg-p1-xhs-ops")
BUDGET = int(os.environ.get("REG_P1_XHS_BUDGET", str(REG_DEFAULT_BUDGET)))
LEAVES = ("t-research", "t-strategy", "t-content", "t-publish")


def _kpi(pid: str) -> tuple[bool, list[str]]:
    db = REPO / "business/tasks/state.db"
    tasks = task_statuses(db, pid)
    if not tasks:
        return False, ["no tasks in state.db"]
    issues = [f"{tid}={tasks.get(tid, 'missing')}" for tid in LEAVES
              if tasks.get(tid, "missing") not in ("completed", "needs_review")]
    return len(issues) == 0, issues


if __name__ == "__main__":
    goal = os.environ.get(
        "REG_P1_XHS_GOAL",
        "小红书笔记：myteam 多 Agent 协作框架入门（调研→策略→笔记→发布留痕）",
    )
    mode = os.environ.get("REG_P1_XHS_MODE", "one_shot")
    max_cycles = int(os.environ.get("REG_P1_XHS_MAX_CYCLES", "1"))
    sys.exit(reg_main(
        reg_id="REG-P1-XHS",
        workflow=WORKFLOW,
        project_id=PROJECT_ID,
        goal=goal,
        budget=BUDGET,
        check_only_env="REG_CHECK_ONLY",
        live_kpi=_kpi,
        mode=mode,
        max_cycles=max_cycles,
    ))
