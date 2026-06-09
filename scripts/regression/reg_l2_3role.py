#!/usr/bin/env python3
"""REG-L2：三角色并行评审（L2 发版门禁）。

固定 workflow `reg-l2-3role`：3 个无依赖 research 叶子 + 1 个 strategy 汇总。
CHECK_ONLY 读 state.db 验 K1（三评审叶子完成率 ≥80%）与 K8（并行度 ≥0.8）；
全量模式调用 run_kernel（与 reg_02_parallel.py 同模式）。

用法:
    # 仅 KPI 检查（不跑 kernel）
    REG_L2_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l2_3role.py

    # 全量 E2E（需 claude CLI）
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l2_3role.py

    # resume 失败叶子
    REG_L2_RESUME=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_l2_3role.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT_ID = os.environ.get("REG_L2_PROJECT_ID", "reg-l2-3role")
WORKFLOW = "reg-l2-3role"
LEAVES = ("t1", "t2", "t3")
GOAL = (
    "对 myteam L2 协作机制做三角色并行评审："
    "A）产品视角 B）架构视角 C）测试视角，每视角约200字，最后汇总"
)
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402

BUDGET = int(os.environ.get("REG_L2_BUDGET", str(REG_DEFAULT_BUDGET)))
K1_THRESHOLD = 0.80
K8_THRESHOLD = 0.80
AGENTS = ("research", "main")

sys.path.insert(0, str(REPO / "scripts" / "regression"))
from check_kpis import check_k8  # noqa: E402
from regression_archive import append_run_record, last_pass_run  # noqa: E402


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _task_statuses(db: Path, project_id: str) -> dict[str, str]:
    import sqlite3

    if not db.is_file():
        return {}
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT task_id, status FROM task WHERE project_id=?", (project_id,)
    ).fetchall()
    conn.close()
    return {r["task_id"]: r["status"] for r in rows}


def _patch_agent_claude(agent_id: str) -> dict | None:
    cfg_path = REPO / "business/config/agents_config.json"
    if not cfg_path.is_file():
        return None
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    old = data.get(agent_id)
    entry = dict(data.get(agent_id) or {})
    entry["backend"] = "claude"
    entry["model"] = entry.get("model") or "claude-sonnet-4-6"
    entry.setdefault("workspace", f"business/workspaces/workspace-{agent_id}")
    data[agent_id] = entry
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return old


def _restore_agent(agent_id: str, old: dict | None) -> None:
    if old is None:
        return
    cfg_path = REPO / "business/config/agents_config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data[agent_id] = old
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _reset_reg_project(db: Path, project_id: str, budget: int) -> None:
    import json
    import sqlite3

    conn = sqlite3.connect(str(db))
    for tid in (*LEAVES, "t4"):
        conn.execute(
            "UPDATE task SET status='pending' WHERE project_id=? AND task_id=? "
            "AND status IN ('failed','blocked')",
            (project_id, tid),
        )
    row = conn.execute(
        "SELECT meta FROM project WHERE project_id=?", (project_id,)
    ).fetchone()
    meta = {}
    if row and row[0]:
        try:
            meta = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            meta = {}
    meta["token_budget"] = max(int(meta.get("token_budget") or 0), budget)
    conn.execute(
        "UPDATE project SET status='in_progress', meta=? WHERE project_id=? "
        "AND status IN ('partially_failed','failed','paused','in_progress')",
        (json.dumps(meta, ensure_ascii=False), project_id),
    )
    conn.commit()
    conn.close()


def _k1_leaves(conn, project_id: str) -> float:
    """三评审叶子（t1–t3）完成率。"""
    placeholders = ",".join("?" * len(LEAVES))
    rows = conn.execute(
        f"SELECT status FROM task WHERE project_id=? AND task_id IN ({placeholders})",
        (project_id, *LEAVES),
    ).fetchall()
    if not rows:
        return 0.0
    done = sum(1 for (status,) in rows if status in ("completed", "needs_review"))
    return done / len(rows)


def _k1_k8(db: Path, project_id: str) -> tuple[float, float, dict[str, str]]:
    if not db.is_file():
        return 0.0, 0.0, {}
    import sqlite3

    conn = sqlite3.connect(str(db))
    try:
        k1 = _k1_leaves(conn, project_id)
        k8 = check_k8(conn, project_id)
    finally:
        conn.close()
    return k1, k8, _task_statuses(db, project_id)


def _print_kpi_report(k1: float, k8: float, tasks: dict[str, str], *, prefix: str = "") -> bool:
    k1_pass = k1 >= K1_THRESHOLD
    k8_pass = k8 >= K8_THRESHOLD
    print(f"{prefix}project: {PROJECT_ID}")
    print(f"{prefix}workflow: {WORKFLOW}")
    print(f"{prefix}review_leaves: {LEAVES}")
    print(f"{prefix}tasks: {tasks}")
    print(f"{prefix}K1: {k1:.1%} (阈值 ≥{K1_THRESHOLD:.0%}) → {'PASS' if k1_pass else 'FAIL'}")
    print(f"{prefix}K8: {k8:.1%} (阈值 ≥{K8_THRESHOLD:.0%}) → {'PASS' if k8_pass else 'FAIL'}")
    t4_st = tasks.get("t4", "missing")
    t4_ok = t4_st in ("completed", "needs_review")
    print(f"{prefix}t4(strategy): {t4_st} → {'OK' if t4_ok else 'PENDING'}")
    reg_pass = k1_pass and k8_pass
    print(f"REG-L2: {'PASS' if reg_pass else 'FAIL'}")
    return reg_pass


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    db = REPO / "business/tasks/state.db"
    check_only = os.environ.get("REG_L2_CHECK_ONLY", "").lower() in ("1", "true", "yes")
    resume = os.environ.get("REG_L2_RESUME", "").lower() in ("1", "true", "yes")

    if check_only:
        print("=== REG-L2 KPI 检查（不跑 kernel）===")
        k1, k8, tasks = _k1_k8(db, PROJECT_ID)
        if not tasks:
            archived = last_pass_run("REG-L2")
            if archived:
                kpis = archived.get("kpis") or {}
                k1 = float(kpis.get("K1", 0))
                k8 = float(kpis.get("K8", 0))
                tasks = kpis.get("tasks") or {}
                print(f"  source: archive:{archived.get('run_id', '?')}")
            else:
                print(f"  project: {PROJECT_ID}")
                print("REG-L2: SKIP（无 live 数据且无 PASS 归档）")
                return 2
        else:
            print("  source: live")
        reg_pass = _print_kpi_report(k1, k8, tasks, prefix="  ")
        return 0 if reg_pass else 1

    if not _claude_available():
        print("REG-L2: SKIP（claude CLI 不可用）")
        return 2

    patched: dict[str, dict | None] = {}
    for agent_id in AGENTS:
        patched[agent_id] = _patch_agent_claude(agent_id)

    if resume and db.is_file():
        k1_pre, k8_pre, tasks_pre = _k1_k8(db, PROJECT_ID)
        append_run_record(
            reg_id="REG-L2",
            project_id=PROJECT_ID,
            pass_=False,
            kpis={"K1": k1_pre, "K8": k8_pre, "tasks": tasks_pre},
            meta={"phase": "pre_reset_resume"},
        )
        _reset_reg_project(db, PROJECT_ID, BUDGET)
        cmd = [
            str(REPO / "venv/bin/python3"),
            "-c",
            (
                "from common.run_kernel import resume_project; "
                f"out = resume_project({PROJECT_ID!r}, backend='claude'); "
                "import json; print(json.dumps({'status': out.status, 'tasks': "
                "{k: v.status for k, v in out.tasks.items()}}, ensure_ascii=False))"
            ),
        ]
        mode = "resume"
    else:
        cmd = [
            str(REPO / "venv/bin/python3"),
            str(REPO / "backend/common/run_kernel.py"),
            PROJECT_ID,
            "--goal", GOAL,
            "--workflow", WORKFLOW,
            "--backend", "claude",
            "--budget", str(BUDGET),
            "--mode", "one_shot",
        ]
        mode = "fresh"
    print("=== REG-L2 三角色并行评审（L2 发版门禁）===")
    print("  mode:", mode)
    print("  project:", PROJECT_ID)
    print("  budget:", BUDGET)
    print("  命令:", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=str(REPO), timeout=int(os.environ.get("REG_L2_TIMEOUT", "2400")))
    finally:
        for agent_id, old in patched.items():
            _restore_agent(agent_id, old)

    proj_status = "N/A"
    if db.is_file():
        import sqlite3

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM project WHERE project_id=?", (PROJECT_ID,)
        ).fetchone()
        if row:
            proj_status = row["status"]
        conn.close()

    k1, k8, tasks = _k1_k8(db, PROJECT_ID)

    print("\n=== REG-L2 结果 ===")
    print(f"  run_kernel exit: {proc.returncode}")
    print(f"  project.status: {proj_status}")
    kpi_pass = _print_kpi_report(k1, k8, tasks, prefix="  ")
    if proc.returncode != 0:
        print("  注: run_kernel 非零退出；L2 门禁以三评审叶子 K1+K8 为准")
    reg_pass = kpi_pass
    rec = append_run_record(
        reg_id="REG-L2",
        project_id=PROJECT_ID,
        pass_=reg_pass,
        kpis={"K1": k1, "K8": k8, "tasks": tasks},
        meta={"mode": mode, "run_kernel_exit": proc.returncode, "budget": BUDGET},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if reg_pass else 1


if __name__ == "__main__":
    sys.exit(main())
