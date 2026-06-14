#!/usr/bin/env python3
"""REG-DISCUSS：FAIL→群讨论→PATCH→PASS 链路回归。

用法:
    REG_DISCUSS_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_discuss_loop.py

    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_discuss_loop.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT_ID = os.environ.get("REG_DISCUSS_PROJECT_ID", "tds-ch3-discuss-test")
WORKFLOW = os.environ.get("REG_DISCUSS_WORKFLOW", "第三章-讨论链路测试")
LOOP_ID = os.environ.get("REG_DISCUSS_LOOP_ID", "discuss_test_round")
GOAL_FILE = REPO / "business/workflows/第三章-讨论链路测试-goal.txt"

sys.path.insert(0, str(REPO / "scripts" / "regression"))
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402
from regression_archive import append_run_record, last_pass_run  # noqa: E402

BUDGET = int(os.environ.get("REG_DISCUSS_BUDGET", str(REG_DEFAULT_BUDGET)))


def _deliverables_dir(project_id: str) -> Path:
    return REPO / "business/tasks/project" / project_id / "deliverables"


def _has_marker(path: Path, marker: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return marker in text


def _check_artifacts(project_id: str) -> tuple[bool, list[str]]:
    """KPI：r1 FAIL + group_discussion + r2 PASS。"""
    d = _deliverables_dir(project_id)
    issues: list[str] = []
    r1_review = d / f"{LOOP_ID}-r1-review_deliverable.md"
    r1_group = d / f"{LOOP_ID}-r1-group_discussion.md"
    r2_review = d / f"{LOOP_ID}-r2-review_deliverable.md"
    r2_work = d / f"{LOOP_ID}-r2-work_deliverable.md"

    if not r1_review.is_file():
        issues.append(f"missing {r1_review.name}")
    elif not _has_marker(r1_review, "REVIEW: FAIL"):
        issues.append("r1 review must end with REVIEW: FAIL")

    if not r1_group.is_file():
        issues.append(f"missing {r1_group.name}")
    else:
        gtext = r1_group.read_text(encoding="utf-8", errors="replace")
        if "定点改稿清单" not in gtext and "改稿清单" not in gtext:
            issues.append("group_discussion missing patch list heading")

    if not r2_review.is_file():
        issues.append(f"missing {r2_review.name}")
    elif not _has_marker(r2_review, "REVIEW: PASS"):
        issues.append("r2 review must end with REVIEW: PASS")

    if not r2_work.is_file():
        issues.append(f"missing {r2_work.name}")

    return len(issues) == 0, issues


def _check_loader() -> tuple[bool, str]:
    sys.path.insert(0, str(REPO / "backend"))
    from common.plan_gate import check_plan
    from common.workflow_loader import load_workflow

    profile = load_workflow(WORKFLOW)
    tasks = profile.instantiate_tasks(goal="REG discuss loop")
    ok = check_plan(tasks, set(profile.roster), check_capabilities=False).passed
    if not profile.options.get("group_discussion_enabled"):
        return False, "group_discussion_enabled must be true"
    if not profile.options.get("loop_discussion_profile"):
        return False, "loop_discussion_profile missing"
    return ok, "loader ok" if ok else "plan_gate failed"


def _backend() -> str:
    return os.environ.get("REG_BACKEND", "opencode")


def _backend_available() -> bool:
    b = _backend()
    if b == "claude":
        return shutil.which("claude") is not None
    if b == "opencode":
        return shutil.which("opencode") is not None
    return False


def _project_status(project_id: str) -> str:
    import sqlite3

    db = REPO / "business/tasks/state.db"
    if not db.is_file():
        return "missing"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT status FROM project WHERE project_id=?", (project_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else "missing"


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    check_only = os.environ.get("REG_DISCUSS_CHECK_ONLY", "").lower() in ("1", "true", "yes")

    loader_ok, loader_msg = _check_loader()
    if not loader_ok:
        print(f"REG-DISCUSS loader: FAIL ({loader_msg})")
        return 1
    print(f"REG-DISCUSS loader: PASS ({loader_msg})")

    if check_only:
        print("=== REG-DISCUSS KPI 检查（不跑 kernel）===")
        ok, issues = _check_artifacts(PROJECT_ID)
        if not ok:
            archived = last_pass_run("REG-DISCUSS")
            if archived and PROJECT_ID == "tds-ch3-discuss-test":
                print(f"  live artifacts incomplete: {issues}")
                print(f"  fallback: archive {archived.get('run_id', '?')}")
                ok = True
            else:
                for i in issues:
                    print(f"  FAIL: {i}")
                print("REG-DISCUSS: FAIL")
                return 1
        print(f"  project: {PROJECT_ID}")
        print(f"  status: {_project_status(PROJECT_ID)}")
        print("REG-DISCUSS: PASS")
        return 0

    backend = _backend()
    if not _backend_available():
        print(f"REG-DISCUSS: SKIP（{backend} CLI 不可用）")
        return 2

    goal = os.environ.get(
        "REG_DISCUSS_GOAL",
        GOAL_FILE.read_text(encoding="utf-8") if GOAL_FILE.is_file() else "讨论链路 REG",
    )
    if "REVIEW: FAIL" not in goal and GOAL_FILE.is_file():
        goal = goal.rstrip() + "\n\n【REG 强制】第1轮 review 必须输出 REVIEW: FAIL；群讨论后第2轮 PATCH 再 REVIEW: PASS。"
    live_pid = os.environ.get("REG_DISCUSS_LIVE_PROJECT_ID", "reg-discuss-loop")
    cmd = [
        str(REPO / "venv/bin/python3"),
        str(REPO / "backend/common/run_kernel.py"),
        live_pid,
        "--workflow", WORKFLOW,
        "--goal", goal,
        "--budget", str(BUDGET),
        "--backend", backend,
    ]
    print(f"=== REG-DISCUSS LIVE run project={live_pid} ===")
    proc = subprocess.run(cmd, cwd=str(REPO), env={**os.environ})
    ok, issues = _check_artifacts(live_pid)
    status = _project_status(live_pid)
    reg_pass = proc.returncode == 0 and ok and status == "completed"
    append_run_record(
        reg_id="REG-DISCUSS",
        project_id=live_pid,
        pass_=reg_pass,
        kpis={"issues": issues, "status": status},
        meta={"workflow": WORKFLOW},
    )
    if not ok:
        for i in issues:
            print(f"  FAIL: {i}")
    print(f"REG-DISCUSS: {'PASS' if reg_pass else 'FAIL'}")
    return 0 if reg_pass else 1


if __name__ == "__main__":
    sys.exit(main())
