#!/usr/bin/env python3
"""REG-K2：Gate 首次通过率 CHECK_ONLY。

构造 5 个带 gate 事件的任务（3 首次通过、1 二次通过、1 仅失败）→ K2 = 3/5 = 60%。
不跑 kernel，验证 check_k2 可从 run_event 采集。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_k2_gate.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "regression"))
sys.path.insert(0, str(_REPO / "backend"))

from check_kpis import check_k2  # noqa: E402

PROJECT_ID = "reg-k2-gate"
EXPECTED_K2 = 0.6


def _seed_case(tmp: Path) -> Path:
    import sqlite3

    from common.store import Store

    db_path = tmp / "state.db"
    store = Store(db_path)
    store.upsert_project(PROJECT_ID, status="completed", meta={"goal": "reg-k2"})

    cases = [
        ("t1", [("gate_passed", 1)]),
        ("t2", [("gate_passed", 1)]),
        ("t3", [("gate_passed", 1)]),
        ("t4", [("gate_failed", 1), ("gate_passed", 2)]),
        ("t5", [("gate_failed", 1)]),
    ]
    for tid, events in cases:
        store.upsert_task(PROJECT_ID, tid, agent="research")
        for kind, attempt in events:
            iid = f"{PROJECT_ID}:{tid}:execute:{attempt}"
            store.create_interaction(iid, "execute", PROJECT_ID, task_id=tid, agent_id="research")
            store.append_run_event(iid, kind, {})

    store.close()
    return db_path


def main() -> int:
    print("=== REG-K2 Gate 首次通过率（CHECK_ONLY）===")
    with tempfile.TemporaryDirectory(prefix="reg_k2_") as tmp_str:
        tmp = Path(tmp_str)
        db = _seed_case(tmp)
        import sqlite3

        conn = sqlite3.connect(str(db))
        try:
            k2 = check_k2(conn, PROJECT_ID)
        finally:
            conn.close()

    ok = abs(k2 - EXPECTED_K2) < 0.01
    print(f"  project: {PROJECT_ID}")
    print(f"  K2:      {k2:.2%} (期望 {EXPECTED_K2:.0%})")
    print(f"REG-K2: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-K2",
        project_id=PROJECT_ID,
        pass_=ok,
        kpis={"K2": round(k2, 4), "expected": EXPECTED_K2},
        meta={"mode": "check_only"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
