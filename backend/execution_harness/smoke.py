#!/usr/bin/env python3
"""execution_harness 本地 smoke。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from execution_harness.context import ExecuteHarnessContext
from execution_harness.facade import enabled, inject_for_execute, prepare_execute_harness
from execution_harness.skill.umbrella import resolve_umbrella_skill


def main() -> int:
    assert enabled(), "execution_harness should be enabled"
    assert resolve_umbrella_skill("research") == "product-methodology"
    lines: list[str] = []
    ctx = ExecuteHarnessContext(
        lines=lines,
        project_id="smoke-proj",
        task_type="research",
        agent_id="product",
        intent="smoke test",
    )
    prepare_execute_harness(ctx)
    inject_for_execute(ctx)
    assert any("推荐方法论" in ln or "同类任务" in ln for ln in lines), lines
    print("execution_harness smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
