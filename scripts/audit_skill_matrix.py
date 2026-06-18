#!/usr/bin/env python3
"""Skill 覆盖审计 — catalog × templates × SKILL.md 目录。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
os.environ.setdefault("MYTEAM_ROOT", str(REPO))

import yaml  # noqa: E402

from common.paths import MYTEAM_ROOT  # noqa: E402
from common.skill_catalog import audit_catalog_router_paths  # noqa: E402
from common.skill_extract import SKILLS_DIR, list_skill_drafts  # noqa: E402
from common.skill_link import iter_business_skill_dir_names  # noqa: E402
from common.task_type_store import list_task_types_for_api  # noqa: E402


def main() -> int:
    catalog_path = MYTEAM_ROOT / "business/skills/catalog.yaml"
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    catalog_types: set[str] = set()
    for item in data.get("skills") or []:
        for tt in item.get("task_types") or []:
            catalog_types.add(tt)

    registered = {t["task_type"] for t in list_task_types_for_api()}
    skill_dirs = set(iter_business_skill_dir_names(SKILLS_DIR))

    missing_router = sorted(registered - skill_dirs - catalog_types)
    missing_catalog = sorted(skill_dirs - catalog_types)
    drafts = list_skill_drafts()
    router_audit = audit_catalog_router_paths(catalog_path)

    print("=== Skill Matrix Audit ===")
    print(f"  registered task_types: {len(registered)}")
    print(f"  catalog task_types:    {len(catalog_types)}")
    print(f"  skill router dirs:     {len(skill_dirs)}")
    print(f"  auto-* drafts:         {len(drafts)}")
    print(f"  catalog routers:       {router_audit['router_ok']}/{router_audit['router_total']} ok")
    if router_audit["missing_routers"]:
        print(f"  missing catalog router ({len(router_audit['missing_routers'])}):")
        for row in router_audit["missing_routers"][:20]:
            print(f"    - {row.get('router')} (id={row.get('catalog_id')})")
    if missing_router:
        print(f"  missing router/catalog ({len(missing_router)}):")
        for tt in missing_router[:20]:
            print(f"    - {tt}")
        if len(missing_router) > 20:
            print(f"    … +{len(missing_router) - 20}")
    if missing_catalog:
        print(f"  skill dir not in catalog ({len(missing_catalog)}):")
        for d in missing_catalog[:10]:
            print(f"    - {d}")
    ok = not missing_router and not router_audit["missing_routers"]
    print(f"\n{'PASS' if ok else 'WARN'}: missing_router={len(missing_router)}, missing_catalog_router={len(router_audit['missing_routers'])}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
