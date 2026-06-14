#!/usr/bin/env python3
"""REG-OUTCOME：三产出形态 catalog + 模板解析 CHECK_ONLY。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_outcome_forms.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "backend"))

from common.delivery_templates import list_delivery_template_ids  # noqa: E402
from common.registry import get_spec, invalidate_registry_cache, resolve_format_spec  # noqa: E402
from common.task_type_suggest import list_outcome_kind_catalog  # noqa: E402


def main() -> int:
    print("=== REG-OUTCOME 产出形态 CHECK_ONLY ===")
    invalidate_registry_cache()
    ok = True

    kinds = list_outcome_kind_catalog()
    if len(kinds) != 3:
        print(f"  FAIL: outcome_kinds 期望 3 个，实际 {len(kinds)}")
        ok = False
    else:
        print("  outcome_kinds: 3 形态 OK")

    for tt, kind in [("code-deployment", "artifact"), ("deploy-run", "action"), ("config-bundle", "code_project")]:
        spec = get_spec(tt)
        if spec is None:
            print(f"  FAIL: templates.yaml 缺少 {tt}")
            ok = False
        elif spec.outcome_kind != kind:
            print(f"  FAIL: {tt} outcome_kind={spec.outcome_kind} 期望 {kind}")
            ok = False
        else:
            print(f"  {tt}: {kind} OK")

    tpl_ids = list_delivery_template_ids()
    for tid in ("deploy-smoke", "config-bundle"):
        if tid not in tpl_ids:
            print(f"  FAIL: delivery_templates 缺少 {tid}")
            ok = False
        else:
            print(f"  template {tid}: OK")

    smoke = resolve_format_spec("deploy-run", "deploy-smoke")
    if smoke is None or "服务URL" not in smoke.required_sections:
        print("  FAIL: deploy-smoke 未正确实例化 deploy-run")
        ok = False
    else:
        print("  deploy-smoke → deploy-run: OK")

    bundle = resolve_format_spec("config-bundle", "config-bundle")
    if bundle is None or not bundle.required_extensions:
        print("  FAIL: config-bundle 模板未带 required_extensions")
        ok = False
    else:
        print("  config-bundle 模板: OK")

    print(f"REG-OUTCOME: {'PASS' if ok else 'FAIL'}")
    sys.path.insert(0, str(_REPO / "scripts" / "regression"))
    from regression_archive import append_run_record  # noqa: E402

    append_run_record(
        reg_id="REG-OUTCOME",
        project_id="reg-outcome-forms",
        pass_=ok,
        kpis={"forms": len(kinds)},
        meta={"mode": "check_only"},
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
