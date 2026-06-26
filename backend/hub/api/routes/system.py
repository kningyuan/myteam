"""System 域路由。"""

from __future__ import annotations

from fastapi import APIRouter

from hub.api.deps import we_store as _we_store

router = APIRouter(tags=["system"])


@router.get("/api/status")
async def api_status():
    from common.paths import WORKSPACES_DIR

    initialized = WORKSPACES_DIR.is_dir() and any(WORKSPACES_DIR.iterdir())
    store = _we_store()
    projects = store.list_projects()
    total = len(projects)
    running = sum(1 for p in projects if p.get("status") == "in_progress")
    monthly_tokens = sum(
        p.get("meta", {}).get("tokens", 0) if isinstance(p.get("meta"), dict) else 0
        for p in projects
    )
    return {
        "status": "ok",
        "initialized": initialized,
        "project_count": total,
        "running_count": running,
        "version": "1.0.0",
        "trends": {
            "project_count": {"direction": "up" if total > 0 else "flat", "value": total},
            "running_count": {"direction": "flat", "value": running},
            "monthly_tokens": {"direction": "up" if monthly_tokens > 0 else "flat", "value": 0},
            "cumulative_cost": {"direction": "flat", "value": 0},
        },
    }