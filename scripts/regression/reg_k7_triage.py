#!/usr/bin/env python3
"""REG-K7：triage 有效决策率 CHECK_ONLY。

构造 5 个已完成 triage interaction（4 有效 + 1 盲目 retry）→ K7 = 80% → PASS。
不跑 kernel，不依赖真实 CLI。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_k7_triage.py

退出码：0=PASS，1=FAIL
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "regression"))
sys.path.insert(0, str(_REPO / "backend"))

from check_kpis import check_k7  # noqa: E402

PROJECT_ID = "reg-k7-triage"
K7_THRESHOLD = 0.8


def _seed_case(tmp: Path) -> Path:
    import sqlite3

    from common.store import Store

    db_path = tmp / "state.db"
    store = Store(db_path)
    store.upsert_project(PROJECT_ID, status="failed", meta={"goal": "reg-k7"})

    cases = [
        ("drop", "", "", True),
        ("reassign", "seo", "", True),
        ("retry", "", "因 gate_exhausted 中止重试", True),
        ("retry", "researcher", "", True),
        ("retry", "", "", False),
    ]
    resp_root = tmp / "responses"
    resp_root.mkdir(parents=True, exist_ok=True)

    for i, (decision, target, notes, _) in enumerate(cases, start=1):
        iid = f"{PROJECT_ID}:t{i}:triage"
        store.create_interaction(iid, "triage", PROJECT_ID, task_id=f"t{i}", agent_id="main")
        resp = {
            "interaction_id": iid,
            "kind": "triage",
            "status": "ok",
            "result": {"decision": decision, "target_agent": target, "notes": notes},
        }
        resp_path = resp_root / f"{iid}.response"
        resp_path.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
        store.update_interaction(iid, status="done", response_ref=str(resp_path))

    store.close()
    return db_path


def main() -> int:
    print("=== REG-K7 triage 有效决策率（CHECK_ONLY）===")
    with tempfile.TemporaryDirectory(prefix="reg_k7_") as tmp_str:
        tmp = Path(tmp_str)
        db = _seed_case(tmp)
        import sqlite3

        conn = sqlite3.connect(str(db))
        try:
            k7 = check_k7(conn, PROJECT_ID)
        finally:
            conn.close()

    k7_pass = k7 >= K7_THRESHOLD
    print(f"  project: {PROJECT_ID}")
    print(f"  triage 样本: 5（4 有效 + 1 盲目 retry）")
    print(f"  K7: {k7:.1%} (阈值 ≥{K7_THRESHOLD:.0%}) → {'PASS' if k7_pass else 'FAIL'}")
    print(f"REG-K7: {'PASS' if k7_pass else 'FAIL'}")

    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-K7",
        project_id=PROJECT_ID,
        pass_=k7_pass,
        kpis={"K7": k7},
        meta={"mode": "check_only", "samples": 5},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if k7_pass else 1


if __name__ == "__main__":
    sys.exit(main())
