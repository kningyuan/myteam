#!/usr/bin/env python3
"""REG-K17：Gate retry session 可观测（CHECK_ONLY）。

跑 R-K17 相关单测，验证 gate_retry_session run_event 与 gate_failed.session_id。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_k17_gate_retry.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

TESTS = [
    "backend/common/tests/test_agent_transport.py::test_gate_retry_emits_gate_retry_session_event",
    "backend/common/tests/test_process.py::test_gate_retry_reuses_session",
]


def main() -> int:
    print("=== REG-K17 Gate retry session 可观测（CHECK_ONLY）===")
    cmd = [
        str(_REPO / "venv" / "bin" / "python3"),
        "-m",
        "pytest",
        *TESTS,
        "-q",
    ]
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    ok = proc.returncode == 0
    print(f"REG-K17: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-K17",
        project_id="reg-k17-gate-retry",
        pass_=ok,
        kpis={"tests": len(TESTS), "exit_code": proc.returncode},
        meta={"mode": "check_only", "tests": TESTS},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
