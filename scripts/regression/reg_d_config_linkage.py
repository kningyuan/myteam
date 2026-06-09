#!/usr/bin/env python3
"""REG-D：设置 Tab process_defaults ↔ 内核贯通（CHECK_ONLY）。

验证 kernel_configs_for_run 与 skill_settings 读取链路，不跑 CLI。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_d_config_linkage.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "regression"))
sys.path.insert(0, str(_REPO / "backend"))

from common.kernel_config import kernel_configs_for_run  # noqa: E402


def main() -> int:
    print("=== REG-D 设置↔内核贯通（CHECK_ONLY）===")
    defaults = {
        "max_gate_retries": 4,
        "soft_idle_sec": 88,
        "hard_idle_sec": 222,
        "parallel_enabled": True,
        "max_parallel": 2,
    }
    proc, wdog = kernel_configs_for_run(defaults, mode="one_shot", backend="claude")
    ok = (
        proc.max_gate_retries == 4
        and proc.parallel_enabled is True
        and proc.max_parallel == 2
        and wdog.soft_idle_sec == 88.0
        and wdog.hard_idle_sec == 222.0
    )
    print(f"  max_gate_retries: {proc.max_gate_retries} (期望 4)")
    print(f"  hard_idle_sec:    {wdog.hard_idle_sec} (期望 222)")
    print(f"REG-D: {'PASS' if ok else 'FAIL'}")

    from regression_archive import append_run_record  # noqa: E402

    rec = append_run_record(
        reg_id="REG-D",
        project_id="config-linkage",
        pass_=ok,
        kpis={"max_gate_retries": proc.max_gate_retries, "hard_idle_sec": wdog.hard_idle_sec},
        meta={"mode": "check_only"},
    )
    print(f"  I-06 archived: run_id={rec['run_id']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
