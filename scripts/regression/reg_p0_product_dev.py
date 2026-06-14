#!/usr/bin/env python3
"""REG-P0：产品研发 workflow。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "regression"))
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402
from reg_workflow_common import reg_main, task_statuses  # noqa: E402

WORKFLOW = "产品研发"
PROJECT_ID = os.environ.get("REG_P0_PROJECT_ID", "reg-p0-product-dev")
BUDGET = int(os.environ.get("REG_P0_BUDGET", str(REG_DEFAULT_BUDGET)))
LEAVES = ("t-req", "t-arch", "t-dev", "t-test", "t-acc")


def _kpi(pid: str) -> tuple[bool, list[str]]:
    db = REPO / "business/tasks/state.db"
    tasks = task_statuses(db, pid)
    if not tasks:
        return False, ["no tasks in state.db"]
    issues = []
    for tid in LEAVES:
        st = tasks.get(tid, "missing")
        if st not in ("completed", "needs_review"):
            issues.append(f"{tid}={st}")
    return len(issues) == 0, issues


if __name__ == "__main__":
    goal = os.environ.get(
        "REG_P0_GOAL",
        "为 myteam Hub 配置保存前校验写一份 PRD 并实现最小 POC 需求说明",
    )
    sys.exit(reg_main(
        reg_id="REG-P0",
        workflow=WORKFLOW,
        project_id=PROJECT_ID,
        goal=goal,
        budget=BUDGET,
        check_only_env="REG_CHECK_ONLY",
        live_kpi=_kpi,
    ))
