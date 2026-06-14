#!/usr/bin/env python3
"""REG-P2：产品经理交付 workflow。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "regression"))
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402
from reg_workflow_common import reg_main, task_statuses  # noqa: E402

WORKFLOW = "产品经理交付"
PROJECT_ID = os.environ.get("REG_P2_PROJECT_ID", "reg-p2-pm-pack")
BUDGET = int(os.environ.get("REG_P2_BUDGET", str(REG_DEFAULT_BUDGET)))
LEAVES = ("t-plan", "t-req", "t-deck")


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
        "REG_P2_GOAL",
        "输出一份 SaaS 协作工具的产品方案、需求说明与 10 页演示文稿大纲",
    )
    sys.exit(reg_main(
        reg_id="REG-P2",
        workflow=WORKFLOW,
        project_id=PROJECT_ID,
        goal=goal,
        budget=BUDGET,
        check_only_env="REG_CHECK_ONLY",
        live_kpi=_kpi,
    ))
