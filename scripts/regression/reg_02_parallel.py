#!/usr/bin/env python3
"""REG-02：四叶子并行 dogfooding（固定 workflow，跳过规划期 token 爆表）。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend python3 scripts/regression/reg_02_parallel.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT_ID = os.environ.get("REG02_PROJECT_ID", "reg-parallel-4leaf")
GOAL = (
    "对 myteam 的架构做4维度评估：A）依赖关系 B）接口抽象 "
    "C）测试覆盖 D）错误处理，每维度200字"
)
from reg_budget_defaults import REG_DEFAULT_BUDGET  # noqa: E402

BUDGET = int(os.environ.get("REG02_BUDGET", str(REG_DEFAULT_BUDGET)))
K8_THRESHOLD = 0.80

sys.path.insert(0, str(REPO / "scripts" / "regression"))
from agents_config_guard import AgentsConfigSession  # noqa: E402
from check_kpis import check_k8  # noqa: E402
from regression_archive import append_run_record, last_pass_run  # noqa: E402


def _k1_k3_k8(store_path: Path, project_id: str) -> tuple[float, float, float, dict]:
    import sqlite3

    if not store_path.is_file():
        return 0.0, 0.0, 0.0, {}
    conn = sqlite3.connect(str(store_path))
    conn.row_factory = sqlite3.Row
    try:
        tasks = conn.execute(
            "SELECT task_id, status FROM task WHERE project_id=?", (project_id,)
        ).fetchall()
        leaves = [r for r in tasks if r["task_id"] in ("t1", "t2", "t3", "t4")]
        if not leaves:
            return 0.0, 0.0, 0.0, {}
        done = sum(1 for r in leaves if r["status"] in ("completed", "needs_review"))
        k1 = done / len(leaves)
        timed = sum(
            1 for r in conn.execute(
                "SELECT status FROM interaction WHERE project_id=? AND task_id IN ('t1','t2','t3','t4')",
                (project_id,),
            )
            if r[0] == "timed_out"
        )
        total_i = conn.execute(
            "SELECT COUNT(*) FROM interaction WHERE project_id=? AND task_id IN ('t1','t2','t3','t4')",
            (project_id,),
        ).fetchone()[0]
        k3 = (timed / total_i) if total_i else 0.0
        k8 = check_k8(conn, project_id)
        statuses = {r["task_id"]: r["status"] for r in tasks}
    finally:
        conn.close()
    return k1, k3, k8, statuses


def _reset_reg_project(db: Path, project_id: str, leaves: tuple[str, ...], budget: int) -> None:
    """将 failed/blocked 叶子重置为 pending，恢复项目并抬高 token_budget（REG resume 用）。"""
    import json
    import sqlite3

    conn = sqlite3.connect(str(db))
    for tid in leaves:
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


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    db = REPO / "business/tasks/state.db"
    check_only = os.environ.get("REG02_CHECK_ONLY", "").lower() in ("1", "true", "yes")
    resume = os.environ.get("REG02_RESUME", "").lower() in ("1", "true", "yes")

    if check_only:
        k1, k3, k8, tasks = _k1_k3_k8(db, PROJECT_ID)
        source = "live"
        if not tasks:
            archived = last_pass_run("REG-02")
            if archived:
                kpis = archived.get("kpis") or {}
                k1 = float(kpis.get("K1", 0))
                k3 = float(kpis.get("K3", 0))
                k8 = float(kpis.get("K8", 0))
                tasks = kpis.get("tasks") or {}
                source = f"archive:{archived.get('run_id', '?')}"
            else:
                print("=== REG-02 KPI 检查（不跑 kernel）===")
                print(f"  project: {PROJECT_ID}")
                print("  tasks: {}")
                print("REG-02: SKIP（无 live 数据且无 PASS 归档）")
                return 2
        k1_pass = k1 >= 0.80
        k3_pass = k3 < 0.10
        k8_pass = k8 >= K8_THRESHOLD
        print("=== REG-02 KPI 检查（不跑 kernel）===")
        print(f"  project: {PROJECT_ID}")
        print(f"  source: {source}")
        print(f"  tasks: {tasks}")
        print(f"  K1: {k1:.1%} (阈值 ≥80%) → {'PASS' if k1_pass else 'FAIL'}")
        print(f"  K3: {k3:.1%} (阈值 <10%) → {'PASS' if k3_pass else 'FAIL'}")
        print(f"  K8: {k8:.1%} (阈值 ≥{K8_THRESHOLD:.0%}) → {'PASS' if k8_pass else 'FAIL'}")
        reg_pass = k1_pass and k3_pass and k8_pass
        print(f"REG-02: {'PASS' if reg_pass else 'FAIL'}")
        return 0 if reg_pass else 1

    if resume and db.is_file():
        # I-06：reset 前归档当前状态
        k1_pre, k3_pre, k8_pre, tasks_pre = _k1_k3_k8(db, PROJECT_ID)
        append_run_record(
            reg_id="REG-02",
            project_id=PROJECT_ID,
            pass_=False,
            kpis={"K1": k1_pre, "K3": k3_pre, "K8": k8_pre, "tasks": tasks_pre},
            meta={"phase": "pre_reset_resume"},
        )
        _reset_reg_project(db, PROJECT_ID, ("t1", "t2", "t3", "t4"), BUDGET)
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
            "--workflow", "reg-parallel-4leaf",
            "--backend", "claude",
            "--budget", str(BUDGET),
            "--mode", "one_shot",
        ]
        mode = "fresh"
    print("=== REG-02 并行 dogfooding ===")
    print("  mode:", mode)
    print("  project:", PROJECT_ID)
    print("  budget:", BUDGET)
    print("  命令:", " ".join(cmd))
    with AgentsConfigSession() as guard:
        guard.patch_claude("research", model="claude-haiku-4-5")
        proc = subprocess.run(cmd, cwd=str(REPO), timeout=int(os.environ.get("REG02_TIMEOUT", "2400")))

    proj = {}
    if db.is_file():
        import sqlite3
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, meta FROM project WHERE project_id=?", (PROJECT_ID,)
        ).fetchone()
        if row:
            proj = dict(row)
        conn.close()

    k1, k3, k8, tasks = _k1_k3_k8(db, PROJECT_ID)
    k1_pass = k1 >= 0.80
    k3_pass = k3 < 0.10
    k8_pass = k8 >= K8_THRESHOLD
    # 门禁以四叶子 K1+K3+K8 为准；t5 汇总可能因预算暂停 blocked，不要求 run_kernel exit 0
    reg_pass = k1_pass and k3_pass and k8_pass

    print("\n=== REG-02 结果 ===")
    print(f"  run_kernel exit: {proc.returncode}")
    print(f"  project.status: {proj.get('status', 'N/A')}")
    print(f"  tasks: {tasks}")
    print(f"  K1: {k1:.1%} (阈值 ≥80%) → {'PASS' if k1_pass else 'FAIL'}")
    print(f"  K3: {k3:.1%} (阈值 <10%) → {'PASS' if k3_pass else 'FAIL'}")
    print(f"  K8: {k8:.1%} (阈值 ≥{K8_THRESHOLD:.0%}) → {'PASS' if k8_pass else 'FAIL'}")
    if proc.returncode != 0 and reg_pass:
        print("  注: run_kernel 非零退出；REG-02 门禁以四叶子 K1+K3+K8 为准")
    rec = append_run_record(
        reg_id="REG-02",
        project_id=PROJECT_ID,
        pass_=reg_pass,
        kpis={"K1": k1, "K3": k3, "K8": k8, "tasks": tasks},
        meta={"mode": mode, "run_kernel_exit": proc.returncode, "budget": BUDGET},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    print(f"REG-02: {'PASS' if reg_pass else 'FAIL'}")
    return 0 if reg_pass else 1


if __name__ == "__main__":
    sys.exit(main())
