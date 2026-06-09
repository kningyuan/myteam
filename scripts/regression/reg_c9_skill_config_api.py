#!/usr/bin/env python3
"""REG-C9：Skill Config API（CHECK_ONLY）。

验证 `/api/skill-config` 与 `/api/skill_config` 均可读写，PUT 后触发热重载。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    print("=== REG-C9 Skill Config API（CHECK_ONLY）===")
    cmd = [
        str(_REPO / "venv" / "bin" / "python3"),
        "-m",
        "pytest",
        "backend/common/tests/test_skill_config_api.py",
        "-q",
    ]
    env = {**os.environ, "PYTHONPATH": str(_REPO / "backend")}
    proc = subprocess.run(cmd, cwd=str(_REPO), env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    ok = proc.returncode == 0
    print(f"REG-C9: {'PASS' if ok else 'FAIL'}")

    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-C9",
        project_id="reg-c9-skill-config-api",
        pass_=ok,
        kpis={"exit_code": proc.returncode},
        meta={"mode": "check_only", "test": "backend/common/tests/test_skill_config_api.py"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
