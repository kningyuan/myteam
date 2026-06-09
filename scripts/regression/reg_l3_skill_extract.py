#!/usr/bin/env python3
"""REG-L3-SKILL：Skill 自动抽提（CHECK_ONLY）。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

TESTS = [
    "backend/common/tests/test_skill_extract.py",
    "backend/common/tests/test_process.py::test_recurring_completed_extracts_skill_draft",
    "backend/common/tests/test_recovery.py::test_maybe_extract_skills_writes_draft",
]


def main() -> int:
    print("=== REG-L3-SKILL Skill 自动抽提（CHECK_ONLY）===")
    cmd = [str(_REPO / "venv" / "bin" / "python3"), "-m", "pytest", *TESTS, "-q"]
    env = {**os.environ, "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    ok = proc.returncode == 0
    print(f"REG-L3-SKILL: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-L3-SKILL",
        project_id="reg-l3-skill-extract",
        pass_=ok,
        kpis={"tests": len(TESTS), "exit_code": proc.returncode},
        meta={"mode": "check_only", "tests": TESTS},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
