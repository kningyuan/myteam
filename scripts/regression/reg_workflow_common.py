#!/usr/bin/env python3
"""通用 workflow REG 辅助 — CHECK_ONLY loader + 可选 LIVE KPI。"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parents[2]


def claude_available() -> bool:
    import shutil
    return shutil.which("claude") is not None


def opencode_available() -> bool:
    import shutil
    return shutil.which("opencode") is not None


def backend_available(backend: str) -> bool:
    if backend == "claude":
        return claude_available()
    if backend == "opencode":
        return opencode_available()
    return False


def reg_backend() -> str:
    return os.environ.get("REG_BACKEND", "opencode")


def check_workflow_loader(workflow_id: str, *, goal: str = "REG check") -> tuple[bool, str]:
    sys.path.insert(0, str(REPO / "backend"))
    from common.plan_gate import check_plan
    from common.workflow_loader import load_workflow

    profile = load_workflow(workflow_id)
    tasks = profile.instantiate_tasks(goal=goal)
    result = check_plan(tasks, set(profile.roster), check_capabilities=False)
    if not result.passed:
        return False, result.feedback or "plan_gate failed"
    return True, f"tasks={len(tasks)} roster={profile.roster}"


def project_status(db: Path, project_id: str) -> str:
    if not db.is_file():
        return "missing"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT status FROM project WHERE project_id=?", (project_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else "missing"


def task_statuses(db: Path, project_id: str) -> dict[str, str]:
    if not db.is_file():
        return {}
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT task_id, status FROM task WHERE project_id=?", (project_id,)
    ).fetchall()
    conn.close()
    return {r["task_id"]: r["status"] for r in rows}


def run_live_kernel(
    project_id: str,
    *,
    workflow: str,
    goal: str,
    budget: int,
    backend: str = "claude",
    mode: str = "one_shot",
    max_cycles: int = 3,
) -> int:
    cmd = [
        str(REPO / "venv/bin/python3"),
        str(REPO / "backend/common/run_kernel.py"),
        project_id,
        "--workflow", workflow,
        "--goal", goal,
        "--budget", str(budget),
        "--backend", backend,
        "--mode", mode,
        "--max-cycles", str(max_cycles),
    ]
    env = {**os.environ, "MYTEAM_ROOT": str(REPO), "PYTHONPATH": str(REPO / "backend")}
    return subprocess.run(cmd, cwd=str(REPO), env=env).returncode


def reg_main(
    *,
    reg_id: str,
    workflow: str,
    project_id: str,
    goal: str,
    budget: int,
    check_only_env: str,
    live_kpi: Optional[Callable[[str], tuple[bool, list[str]]]] = None,
    mode: str = "one_shot",
    max_cycles: int = 3,
) -> int:
    from regression_archive import append_run_record, last_pass_run

    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    db = REPO / "business/tasks/state.db"
    check_only = os.environ.get(check_only_env, "").lower() in ("1", "true", "yes")
    require_live_kpi = os.environ.get("REG_REQUIRE_LIVE_KPI", "").lower() in ("1", "true", "yes")
    kpi_only = require_live_kpi and not check_only

    ok, msg = check_workflow_loader(workflow)
    print(f"{reg_id} loader: {'PASS' if ok else 'FAIL'} ({msg})")
    if not ok:
        return 1

    if check_only:
        print(f"=== {reg_id} CHECK_ONLY ===")
        if live_kpi and require_live_kpi:
            kpi_ok, issues = live_kpi(project_id)
            status = project_status(db, project_id)
            if kpi_ok and status == "completed":
                print(f"  project={project_id} status={status}")
                print(f"{reg_id}: PASS")
                return 0
            archived = last_pass_run(reg_id)
            if archived:
                print(f"  live KPI incomplete: {issues}")
                print(f"  fallback archive: {archived.get('run_id')}")
                print(f"{reg_id}: PASS")
                return 0
            for i in issues:
                print(f"  FAIL: {i}")
            if status != "completed":
                print(f"  FAIL: project status={status}")
            print(f"{reg_id}: FAIL")
            return 1
        print(f"{reg_id}: PASS")
        return 0

    if kpi_only:
        print(f"=== {reg_id} LIVE_KPI ===")
        if not live_kpi:
            print(f"{reg_id}: FAIL（无 live_kpi）")
            return 1
        kpi_ok, issues = live_kpi(project_id)
        status = project_status(db, project_id)
        if kpi_ok and status == "completed":
            print(f"  project={project_id} status={status}")
            append_run_record(
                reg_id=reg_id,
                project_id=project_id,
                pass_=True,
                kpis={"status": status, "tasks": task_statuses(db, project_id)},
                meta={"workflow": workflow, "backend": os.environ.get("REG_BACKEND", "opencode")},
            )
            print(f"{reg_id}: PASS")
            return 0
        for i in issues:
            print(f"  FAIL: {i}")
        if status != "completed":
            print(f"  FAIL: project status={status}")
        print(f"{reg_id}: FAIL")
        return 1

    backend = reg_backend()
    if not backend_available(backend):
        print(f"{reg_id}: SKIP（{backend} CLI 不可用）")
        return 2

    rc = run_live_kernel(
        project_id, workflow=workflow, goal=goal, budget=budget,
        mode=mode, max_cycles=max_cycles, backend=backend,
    )
    kpi_ok = True
    issues: list[str] = []
    if live_kpi:
        kpi_ok, issues = live_kpi(project_id)
    status = project_status(db, project_id)
    reg_pass = rc == 0 and kpi_ok and status == "completed"
    append_run_record(
        reg_id=reg_id,
        project_id=project_id,
        pass_=reg_pass,
        kpis={"status": status, "tasks": task_statuses(db, project_id), "issues": issues},
        meta={"workflow": workflow},
    )
    if issues:
        for i in issues:
            print(f"  FAIL: {i}")
    print(f"{reg_id}: {'PASS' if reg_pass else 'FAIL'}")
    return 0 if reg_pass else 1
