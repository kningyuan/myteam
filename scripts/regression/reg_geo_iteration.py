#!/usr/bin/env python3
"""REG-GEO-ITERATION：GEO 持续优化-迭代 v2 loop 回归。

用法:
    REG_GEO_ITER_CHECK_ONLY=1 MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_geo_iteration.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = os.environ.get("REG_GEO_ITER_WORKFLOW", "GEO持续优化-迭代")
LOOP_ID = os.environ.get("REG_GEO_ITER_LOOP_ID", "geo_wave")
FIXTURE_PATH = REPO / "business/workflows/GEO持续优化-迭代.yaml"

sys.path.insert(0, str(REPO / "scripts" / "regression"))
from regression_archive import last_pass_run  # noqa: E402


def _check_loader() -> tuple[bool, str]:
    sys.path.insert(0, str(REPO / "backend"))
    from common.plan_gate import check_plan
    from common.workflow_loader import load_workflow

    if not FIXTURE_PATH.is_file():
        return False, f"missing {FIXTURE_PATH}"

    profile = load_workflow(WORKFLOW, path=FIXTURE_PATH)
    spec = next((lp for lp in profile.loops if lp.id == LOOP_ID), None)
    if spec is None:
        return False, f"loop「{LOOP_ID}」not found"
    if not spec.bodies or "audit" not in spec.bodies or "patch" not in spec.bodies:
        return False, "bodies audit/patch missing"
    if not spec.assess:
        return False, "assess missing"
    if not spec.transition:
        return False, "transition missing"

    tasks = profile.instantiate_tasks(goal="REG geo iteration")
    ok = check_plan(tasks, set(profile.roster), check_capabilities=False).passed
    return ok, "loader ok" if ok else "plan_gate failed"


def main() -> int:
    os.environ.setdefault("MYTEAM_ROOT", str(REPO))
    os.environ.setdefault("PYTHONPATH", str(REPO / "backend"))
    check_only = os.environ.get("REG_GEO_ITER_CHECK_ONLY", "").lower() in ("1", "true", "yes")

    loader_ok, loader_msg = _check_loader()
    if not loader_ok:
        print(f"REG-GEO-ITERATION loader: FAIL ({loader_msg})")
        return 1
    print(f"REG-GEO-ITERATION loader: PASS ({loader_msg})")

    if check_only:
        archived = last_pass_run("REG-GEO-ITERATION")
        if archived:
            print(f"  fallback archive: {archived.get('run_id', '?')}")
        print("REG-GEO-ITERATION: PASS (CHECK_ONLY)")
        return 0

    print("REG-GEO-ITERATION LIVE: SKIP（P2 — 需 claude CLI + 完整 GEO 项目）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
