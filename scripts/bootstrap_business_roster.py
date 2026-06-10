#!/usr/bin/env python3
"""将 business/templates/business-roster.json 合并进 agents_registry，并创建缺失 workspace。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MYTEAM_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from common import paths  # noqa: E402
from common.agent_bootstrap import auto_create_agent  # noqa: E402
from common.agent_id_policy import invalidate_agent_id_policy_cache  # noqa: E402
from common.registry import invalidate_registry_cache  # noqa: E402


def _load_roster() -> dict:
    fp = paths.BUSINESS_DIR / "templates" / "business-roster.json"
    raw = json.loads(fp.read_text(encoding="utf-8"))
    return raw.get("agents") or {}


def _load_registry() -> dict:
    if paths.AGENTS_REGISTRY_FILE.is_file():
        try:
            return json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": "2.0", "agents": {}}


def _merge_agent_meta(existing: dict, incoming: dict) -> dict:
    return {
        "name": incoming.get("name") or existing.get("name", ""),
        "role": incoming.get("role") or existing.get("role", "worker"),
        "description": incoming.get("description") or existing.get("description", ""),
        "capabilities": incoming.get("capabilities") or existing.get("capabilities") or [],
        "task_types": sorted(
            set(existing.get("task_types") or []) | set(incoming.get("task_types") or [])
        ),
    }


def main() -> int:
    roster = _load_roster()
    reg = _load_registry()
    reg.setdefault("agents", {})

    created_ws: list[str] = []
    updated: list[str] = []

    for aid, meta in roster.items():
        ws = paths.workspace_dir(aid)
        if not ws.is_dir():
            auto_create_agent(
                aid,
                name=meta.get("name") or aid,
                role=meta.get("role") or "worker",
                description=meta.get("description") or "",
            )
            created_ws.append(aid)
        merged = _merge_agent_meta(reg["agents"].get(aid) or {}, meta)
        reg["agents"][aid] = merged
        updated.append(aid)

    paths.AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.AGENTS_REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    invalidate_registry_cache()
    invalidate_agent_id_policy_cache()

    print(f"✓ 已合并 {len(updated)} 个 Agent 到 {paths.AGENTS_REGISTRY_FILE}")
    if created_ws:
        print(f"✓ 新建 workspace: {', '.join(created_ws)}")
    else:
        print("  （workspace 均已存在，仅更新注册表）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
