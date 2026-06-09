#!/usr/bin/env python3
"""REG-K14：任务级 per-agent backend 路由（CHECK_ONLY）。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_k14_per_agent_backend.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

TESTS = [
    "backend/common/tests/test_agent_transport.py::test_transport_uses_per_agent_backend",
    "backend/common/tests/test_agent_transport.py::test_transport_two_agents_different_backends",
]


def main() -> int:
    print("=== REG-K14 per-agent backend 路由（CHECK_ONLY）===")
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
    print(f"REG-K14: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-K14",
        project_id="reg-k14-backend",
        pass_=ok,
        kpis={"tests": len(TESTS), "exit_code": proc.returncode},
        meta={"mode": "check_only", "tests": TESTS},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
