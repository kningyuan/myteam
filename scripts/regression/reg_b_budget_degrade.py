#!/usr/bin/env python3
"""REG-B：budget 自动降级（CHECK_ONLY）。

调用已有单测 `test_budget_degrade_fires_before_pause` 验证 Process 降级链路。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_b_budget_degrade.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    print("=== REG-B budget 自动降级（CHECK_ONLY via pytest）===")
    cmd = [
        str(_REPO / "venv/bin/python3"),
        "-m", "pytest",
        "backend/common/tests/test_observability.py::test_budget_degrade_fires_before_pause",
        "-q",
    ]
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env)
    ok = proc.returncode == 0
    print(f"REG-B: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-B",
        project_id="budget-degrade",
        pass_=ok,
        kpis={"pytest_exit": proc.returncode},
        meta={"mode": "check_only", "test": "test_budget_degrade_fires_before_pause"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
