#!/usr/bin/env python3
"""Prompt 矩阵 E2E：同一 task_type、不同 agent，description 仅变量。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ID = "prompt-matrix-3"


def main() -> int:
    env = os.environ.copy()
    env["MYTEAM_ROOT"] = str(ROOT)
    env["PYTHONPATH"] = str(ROOT / "backend")
    cmd = [
        str(ROOT / "venv/bin/python3"),
        str(ROOT / "backend/common/run_kernel.py"),
        PROJECT_ID,
        "--workflow", "prompt-matrix-smoke",
        "--goal", "Prompt 矩阵冒烟：三 agent × research + strategy 汇总",
        "--title", "Prompt 矩阵冒烟",
        "--budget", "600000",
        "--backend", "claude",
    ]
    print("运行:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    out = {
        "project_id": PROJECT_ID,
        "exit_code": proc.returncode,
        "workflow": "prompt-matrix-smoke",
    }
    reg_dir = ROOT / "business/regression"
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "prompt_matrix_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
