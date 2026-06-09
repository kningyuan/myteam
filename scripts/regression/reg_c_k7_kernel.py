#!/usr/bin/env python3
"""REG-C：K7 triage 有效决策率 — 真实 Process 路径（pytest 驱动）。

验证失败任务经内核 triage 后 K7 可度量，非仅种子 SQL。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_c_k7_kernel.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    print("=== REG-C K7 triage 内核路径（pytest）===")
    cmd = [
        str(_REPO / "venv/bin/python3"),
        "-m", "pytest",
        "backend/common/tests/test_process.py::test_kernel_triage_k7_measurable",
        "-q",
    ]
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env)
    ok = proc.returncode == 0
    print(f"REG-C: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-C-K7",
        project_id="k7-kernel",
        pass_=ok,
        kpis={"pytest_exit": proc.returncode},
        meta={"mode": "kernel_path", "test": "test_kernel_triage_k7_measurable"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
