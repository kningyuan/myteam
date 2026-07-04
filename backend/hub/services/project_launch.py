"""项目发起与后台内核调度（Hub API 与 lifespan 共享）。"""

from __future__ import annotations

import re
from typing import Callable, Optional

from hub.services.kernel_run import (
    _clear_kernel_run,
    _is_kernel_running,
    _set_kernel_run,
)
from config_store.skill_config import skill_config
from config_store.system_config import system_config


def slug(text: str, limit: int = 24) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]", "", (text or "").strip().replace(" ", "_"))
    return s[:limit] or "project"


def persist_project_launch(
    project_id: str,
    *,
    title: str,
    goal: str,
    mode: str,
    budget,
    workflow: Optional[str] = None,
    review: bool = False,
    split: bool = False,
    backend: Optional[str] = None,
    max_cycles: Optional[int] = None,
) -> None:
    """发起瞬间写入 SQLite，避免仅后台线程落库导致刷新后项目列表为空。"""
    from common.store.store import Store

    meta: dict = {
        "goal": goal,
        "token_budget": budget,
        "hub_kernel_run": {"running": True, "error": None},
    }
    if workflow:
        meta["workflow"] = workflow
    launch: dict = {}
    if review:
        launch["review"] = True
    if split:
        launch["split"] = True
    if max_cycles is not None and max_cycles >= 1:
        launch["max_cycles"] = max_cycles
    if backend:
        launch["backend"] = backend
    if launch:
        meta["launch"] = launch
    store = Store()
    try:
        store.upsert_project(
            project_id,
            title=title or project_id,
            mode=mode,
            status="in_progress",
            meta=meta,
        )
    finally:
        store.close()


def mark_project_kernel_failed(project_id: str, error: str) -> None:
    from common.store.store import Store

    store = Store()
    try:
        if store.get_project(project_id):
            store.set_project_status(project_id, "failed")
            store.update_project_meta(project_id, launch_error=error)
    finally:
        store.close()


def run_kernel_bg(
    project_id: str,
    goal: str,
    mode: str,
    budget,
    title: str,
    review: bool = False,
    workflow: Optional[str] = None,
    split: bool = False,
    process_defaults: Optional[dict] = None,
    max_cycles: Optional[int] = None,
) -> None:
    try:
        from common.runtime.kernel_config import kernel_configs_for_run
        from common.runtime.run_kernel import run_project
        from hub.services.project_hooks import hub_project_hooks

        defaults = process_defaults or {}
        backend = system_config.get("system", "default_backend", default="opencode")
        proc_cfg, wdog_cfg = kernel_configs_for_run(
            defaults if defaults else None,
            mode=mode,
            token_budget=budget,
            max_cycles=max_cycles,
            review=review,
            split=split,
            backend=backend,
        )
        run_project(
            project_id,
            goal=goal,
            title=title,
            mode=mode,
            token_budget=budget,
            review=review,
            workflow=workflow,
            split=split,
            config=proc_cfg,
            watchdog=wdog_cfg,
            backend=backend,
            hooks=hub_project_hooks(),
        )
    except Exception as e:  # noqa: BLE001 — 后台线程，错误回灌给状态查询
        _set_kernel_run(project_id, running=False, error=str(e))
        mark_project_kernel_failed(project_id, str(e))
    else:
        _set_kernel_run(project_id, running=False)


def resume_kernel_bg(project_id: str) -> None:
    try:
        from common.runtime.kernel_config import kernel_configs_for_run
        from common.runtime.run_kernel import resume_project
        from common.store.store import Store
        from hub.services.project_hooks import hub_project_hooks

        defaults = skill_config.get_all().get("process_defaults") or {}
        backend = system_config.get("system", "default_backend", default="opencode")
        store = Store()
        try:
            meta = (store.get_project(project_id) or {}).get("meta") or {}
            proc_cfg, wdog_cfg = kernel_configs_for_run(
                defaults if defaults else None,
                mode=meta.get("mode") or "one_shot",
                token_budget=meta.get("token_budget"),
                backend=backend,
            )
        finally:
            store.close()
        resume_project(
            project_id,
            config=proc_cfg,
            watchdog=wdog_cfg,
            backend=backend,
            hooks=hub_project_hooks(),
        )
    except Exception as e:  # noqa: BLE001
        _set_kernel_run(project_id, running=False, error=str(e))
    else:
        _set_kernel_run(project_id, running=False)


def start_kernel_job(project_id: str, runner: Callable, *args, **kwargs) -> None:
    """经 ProjectRuntime 调度后台内核（JobSupervisor + 并发槽 + 取消注册）。"""
    from common.project.project_runtime import get_project_runtime

    def _on_end(pid: str, _err: Optional[BaseException]) -> None:
        _clear_kernel_run(pid)

    get_project_runtime().start(project_id, runner, *args, on_end=_on_end, **kwargs)


__all__ = [
    "_is_kernel_running",
    "persist_project_launch",
    "resume_kernel_bg",
    "run_kernel_bg",
    "slug",
    "start_kernel_job",
]
