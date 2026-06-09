#!/usr/bin/env python3
"""REG-RULES：rules 注入可观测（CHECK_ONLY）。

验证内核 execute 路径将 universal-rules + AGENTS.md 合并注入 RunRequest.rules_file。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_rules_injection.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

TEST = "backend/common/tests/test_agent_transport.py::test_transport_injects_rules_file"


def main() -> int:
    print("=== REG-RULES rules 注入可观测（CHECK_ONLY）===")
    cmd = [
        str(_REPO / "venv" / "bin" / "python3"),
        "-m",
        "pytest",
        TEST,
        "-q",
    ]
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    ok = proc.returncode == 0
    print(f"REG-RULES: {'PASS' if ok else 'FAIL'}")
    if ok:
        sys.path.insert(0, str(_REPO / "scripts" / "regression"))
        from regression_archive import append_run_record  # noqa: E402

        rec = append_run_record(
            reg_id="REG-RULES",
            project_id="rules-injection-check",
            pass_=True,
            kpis={"rules_file_injected": True},
            meta={"test": TEST},
        )
        print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
