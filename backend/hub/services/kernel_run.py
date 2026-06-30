"""Hub kernel 运行态 — 仅存 Store project.meta.hub_kernel_run。"""

from __future__ import annotations

from typing import Optional


def _set_kernel_run(project_id: str, *, running: bool, error: Optional[str] = None) -> None:
    """写入 project.meta.hub_kernel_run，Hub 重启后可 reconcile。"""
    try:
        from common.store.store import Store

        store = Store()
        try:
            if store.get_project(project_id):
                store.update_project_meta(
                    project_id,
                    hub_kernel_run={"running": running, "error": error},
                )
        finally:
            store.close()
    except Exception:
        pass


def _get_kernel_run(project_id: str) -> dict:
    try:
        from common.store.store import Store

        store = Store()
        try:
            proj = store.get_project(project_id) or {}
            meta = proj.get("meta") or {}
            hub = meta.get("hub_kernel_run") or {}
            err = hub.get("error") or meta.get("launch_error")
            if hub.get("running") or err:
                return {"running": bool(hub.get("running")), "error": err}
        finally:
            store.close()
    except Exception:
        pass
    return {"running": False, "error": None}


def _is_kernel_running(project_id: str) -> bool:
    try:
        from common.project.project_runtime import get_project_runtime

        if get_project_runtime().is_running(project_id):
            return True
    except Exception:
        pass
    return bool(_get_kernel_run(project_id).get("running"))


def _clear_kernel_run(project_id: str) -> None:
    try:
        from common.store.store import Store

        store = Store()
        try:
            if store.get_project(project_id):
                store.update_project_meta(
                    project_id,
                    hub_kernel_run={"running": False, "error": None},
                )
        finally:
            store.close()
    except Exception:
        pass


def _reconcile_stale_kernel_runs() -> int:
    """Hub 重启：清除 meta 中残留的 running=true。"""
    cleared = 0
    try:
        from common.store.store import Store

        store = Store()
        try:
            for proj in store.list_projects():
                meta = proj.get("meta") or {}
                hub_run = meta.get("hub_kernel_run") or {}
                if hub_run.get("running"):
                    store.update_project_meta(
                        proj["project_id"],
                        hub_kernel_run={"running": False, "error": "hub_restarted"},
                    )
                    cleared += 1
        finally:
            store.close()
    except Exception:
        pass
    return cleared
