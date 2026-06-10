#!/usr/bin/env python3
"""分层 E2E：L2 workflow + L3 自由规划，输出 KPI 表。"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "business/tasks/state.db"
GOAL_FILE = REPO / "business/workflows/tier-l3-free-goal.txt"


def _run(project_id: str, extra: list[str]) -> int:
    env = {
        **os.environ,
        "MYTEAM_ROOT": str(REPO),
        "PYTHONPATH": str(REPO / "backend"),
        "NO_PROXY": "localhost,127.0.0.1,::1",
    }
    cmd = [
        str(REPO / "venv/bin/python3"),
        str(REPO / "backend/common/run_kernel.py"),
        project_id,
        "--backend", "claude",
        "--budget", os.environ.get("TIER_BUDGET", "1000000"),
        *extra,
    ]
    print(f"\n{'='*60}\n▶ {' '.join(cmd[-6:])}\n{'='*60}")
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(REPO), env=env)
    print(f"  exit={p.returncode} elapsed={time.time()-t0:.0f}s")
    return p.returncode


def _kpi(project_id: str) -> dict:
    if not DB.is_file():
        return {"error": "no db"}
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    proj = conn.execute(
        "SELECT status FROM project WHERE project_id=?", (project_id,)
    ).fetchone()
    tasks = conn.execute(
        "SELECT task_id, status, agent, task_type FROM task WHERE project_id=?",
        (project_id,),
    ).fetchall()
    interactions = conn.execute(
        "SELECT interaction_id, kind, status FROM interaction WHERE project_id=?",
        (project_id,),
    ).fetchall()
    events = conn.execute(
        """SELECT kind, COUNT(*) c FROM run_event
           WHERE interaction_id LIKE ? GROUP BY kind""",
        (f"{project_id}:%",),
    ).fetchall()
    conn.close()
    ev = {r["kind"]: r["c"] for r in events}
    completed = sum(1 for t in tasks if t["status"] == "completed")
    return {
        "project_status": proj["status"] if proj else "missing",
        "tasks": [dict(t) for t in tasks],
        "task_completed_ratio": completed / len(tasks) if tasks else 0,
        "interaction_done": sum(1 for i in interactions if i["status"] == "done"),
        "gate_failed": ev.get("gate_failed", 0),
        "gate_passed": ev.get("gate_passed", 0),
        "deliverable_adopted": ev.get("deliverable_adopted", 0),
        "timed_out": sum(1 for i in interactions if i["status"] == "timed_out"),
    }


def main() -> int:
    os.chdir(REPO)
    results = {}

    l2_pid = os.environ.get("TIER_L2_PROJECT", "tier-l2-upg")
    l2_wf = os.environ.get("TIER_L2_WORKFLOW", "GitHub项目调研")
    rc = _run(l2_pid, [
        "--goal", "Tier L2：GitHub 开源项目三视角并行调研（产品/架构/工程化）",
        "--title", "Tier L2 并行调研",
        "--workflow", l2_wf,
    ])
    results["tier-l2"] = {"exit": rc, "kpi": _kpi(l2_pid), "workflow": l2_wf}

    l3_pid = os.environ.get("TIER_L3_PROJECT", "tier-l3-upg")
    goal = GOAL_FILE.read_text(encoding="utf-8").strip()
    rc = _run(l3_pid, [
        "--goal", goal,
        "--title", "Tier L3 自由规划 5 步",
    ])
    results["tier-l3-free"] = {"exit": rc, "kpi": _kpi(l3_pid)}

    out = REPO / "business/regression/tier_e2e_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 KPI 已写入 {out}")
    for name, r in results.items():
        k = r["kpi"]
        print(f"  {name}: exit={r['exit']} project={k.get('project_status')} "
              f"tasks_ok={k.get('task_completed_ratio',0):.0%} "
              f"gate_fail={k.get('gate_failed')} timeout={k.get('timed_out')}")
    return 0 if all(r["exit"] == 0 for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
