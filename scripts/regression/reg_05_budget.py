#!/usr/bin/env python3
"""REG-05：budget 护栏 E2E（需真实 claude CLI）。

读 reg-05-budget.yaml → run_kernel → 查 K5 / status / tokens。

通过条件（见 docs/0608/03-QA度量与回归体系.md REG-05）：
  - K5 = 100%（done interaction 均有 tokens > 0）
  - project.status == paused
  - total_tokens ≤ budget×1.2，或规划后首次 budget 检查即停（accept paused）

退出码：0=PASS，1=FAIL，2=SKIP（无 CLI）
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from common.observability import cost  # noqa: E402
from common.store import Store  # noqa: E402

_PROJECT_ID = "reg-budget-guard-r3"
_YAML = _REPO_ROOT / "scripts/regression/projects/reg-05-budget.yaml"
_AGENTS_CONFIG = _REPO_ROOT / "business/config/agents_config.json"
_STATE_DB = _REPO_ROOT / "business/tasks/state.db"


def _load_cfg() -> dict:
    with open(_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _reg05_agent_id() -> str:
    """REG-05 临时改 backend 的目标 agent；优先 research，勿用 setdefault 复活已删 researcher。"""
    if not _AGENTS_CONFIG.is_file():
        return "research"
    data = json.loads(_AGENTS_CONFIG.read_text(encoding="utf-8"))
    for aid in ("research", "main", "developer"):
        if aid in data:
            return aid
    return next(iter(data), "research")


def _patch_agent_backend(agent_id: str, backend: str) -> str | None:
    """临时改 agent backend；返回原值（None=未改或 agent 不存在）。"""
    if not _AGENTS_CONFIG.is_file():
        return None
    data = json.loads(_AGENTS_CONFIG.read_text(encoding="utf-8"))
    entry = data.get(agent_id)
    if not isinstance(entry, dict):
        return None
    old = entry.get("backend")
    if old == backend:
        return None
    entry["backend"] = backend
    _AGENTS_CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return old


def _restore_agent_backend(agent_id: str, old: str | None) -> None:
    if old is None or not _AGENTS_CONFIG.is_file():
        return
    data = json.loads(_AGENTS_CONFIG.read_text(encoding="utf-8"))
    entry = data.get(agent_id)
    if not isinstance(entry, dict):
        return
    entry["backend"] = old
    _AGENTS_CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _reset_project(project_id: str) -> None:
    """清掉旧 run 数据，避免 stale in_progress 导致 REG-05 误判。"""
    if not _STATE_DB.is_file():
        return
    conn = sqlite3.connect(str(_STATE_DB))
    conn.execute("DELETE FROM interaction WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM task WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM project WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM run_event WHERE interaction_id LIKE ?", (f"{project_id}%",))
    conn.commit()
    conn.close()


def _k5(conn: sqlite3.Connection, project_id: str) -> float:
    rows = conn.execute("""
        SELECT tokens FROM interaction
        WHERE project_id = ? AND status IN ('done')
    """, (project_id,)).fetchall()
    if not rows:
        return 0.0
    ok = sum(1 for (t,) in rows if (t or 0) > 0)
    return ok / len(rows)


def run_kernel(cfg: dict) -> int:
    cmd = [
        str(_REPO_ROOT / "venv/bin/python3"),
        str(_REPO_ROOT / "backend/common/run_kernel.py"),
        _PROJECT_ID,
        "--goal", cfg["goal"],
        "--backend", cfg.get("backend", "claude"),
        "--budget", str(cfg["budget"]),
        "--mode", "one_shot",
    ]
    env = {
        **dict(__import__("os").environ),
        "MYTEAM_ROOT": str(_REPO_ROOT),
        "PYTHONPATH": str(_REPO_ROOT / "backend"),
        "NO_PROXY": "localhost,127.0.0.1,::1",
    }
    print(f"  命令: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(_REPO_ROOT), env=env)
    return proc.returncode


def main() -> int:
    cfg = _load_cfg()
    budget = int(cfg["budget"])
    thresholds = cfg.get("thresholds", {})
    k5_min = float(thresholds.get("k5_min", 1.0))
    expected_status = thresholds.get("expected_status", "paused")
    if expected_status == "budget_exceeded":
        expected_status = "paused"  # 验收等价态

    print("=== REG-05 budget 护栏 E2E ===")
    print(f"  project_id: {_PROJECT_ID}")
    print(f"  budget: {budget}")

    if not _claude_available():
        print("REG-05: SKIP（claude CLI 不可用）")
        sys.path.insert(0, str(_REPO_ROOT / "scripts" / "regression"))
        from regression_archive import append_run_record  # noqa: E402

        append_run_record(
            reg_id="REG-05",
            project_id=_PROJECT_ID,
            pass_=False,
            kpis={"K5": 0.0, "skip": True},
            meta={"mode": "skip", "reason": "claude CLI unavailable"},
        )
        return 2

    reg_agent = _reg05_agent_id()
    old_backend = _patch_agent_backend(reg_agent, cfg.get("backend", "claude"))
    if old_backend is not None:
        print(f"  临时将 {reg_agent} backend: {old_backend} → claude")

    _reset_project(_PROJECT_ID)

    try:
        rc = run_kernel(cfg)
        print(f"  run_kernel exit: {rc}")
    finally:
        _restore_agent_backend(reg_agent, old_backend)
        if old_backend is not None:
            print(f"  已恢复 {reg_agent} backend: {old_backend}")

    if not _STATE_DB.is_file():
        print(f"REG-05: FAIL（state.db 不存在: {_STATE_DB}）")
        return 1

    conn = sqlite3.connect(str(_STATE_DB))
    try:
        k5 = _k5(conn, _PROJECT_ID)
        proj = conn.execute(
            "SELECT status, meta FROM project WHERE project_id = ?", (_PROJECT_ID,)
        ).fetchone()
    finally:
        conn.close()

    store = Store(_STATE_DB)
    try:
        total_tokens = cost(store, _PROJECT_ID)["project"]
    finally:
        store.close()

    status = proj[0] if proj else "missing"
    token_cap = budget * 1.2
    k5_ok = k5 >= k5_min
    status_ok = status == expected_status
    # 规划后首次检查即停：paused 且未派发 execute 任务（accept 即使 total > cap）
    execute_count = 0
    if _STATE_DB.is_file():
        conn2 = sqlite3.connect(str(_STATE_DB))
        try:
            execute_count = conn2.execute("""
                SELECT COUNT(*) FROM interaction
                WHERE project_id = ? AND kind = 'execute' AND status = 'done'
            """, (_PROJECT_ID,)).fetchone()[0]
        finally:
            conn2.close()
    stopped_at_planning = status_ok and execute_count == 0
    tokens_ok = total_tokens <= token_cap or stopped_at_planning

    print("")
    print("=== REG-05 结果 ===")
    print(f"  K5:           {k5*100:.1f}% (阈值 ≥{k5_min*100:.0f}%)")
    print(f"  status:       {status} (期望 {expected_status})")
    print(f"  total_tokens: {total_tokens} / budget {budget} (cap×1.2={token_cap:.0f})")
    print(f"  execute done: {execute_count}")
    print(f"  K5 通过:      {'YES' if k5_ok else 'NO'}")
    print(f"  status 通过:  {'YES' if status_ok else 'NO'}")
    print(f"  tokens 通过:  {'YES' if tokens_ok else 'NO'} (规划期即停={stopped_at_planning})")

    overall = k5_ok and status_ok and tokens_ok
    verdict = "PASS" if overall else ("CONDITIONAL" if k5_ok and status_ok else "FAIL")
    print(f"REG-05: {verdict}")

    sys.path.insert(0, str(_REPO_ROOT / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-05",
        project_id=_PROJECT_ID,
        pass_=overall,
        kpis={
            "K5": k5,
            "status": status,
            "total_tokens": total_tokens,
            "budget": budget,
            "execute_done": execute_count,
        },
        meta={"mode": "e2e", "verdict": verdict},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
