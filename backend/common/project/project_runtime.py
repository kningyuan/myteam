#!/usr/bin/env python3
"""Hub 项目运行调度 — JobSupervisor + 并发槽 + 取消注册。"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Optional

from common.project.job_supervisor import JobSupervisor
from common.project.project_cancel import cancel_registry
import common.store.store as store_module

logger = logging.getLogger("project_runtime")

_PROJECT_TERMINAL = {"completed", "failed", "partially_failed", "aborted", "cancelled", "paused", "timed_out"}


def _max_concurrent() -> int:
    try:
        from common.skill.skill_settings import process_defaults

        d = process_defaults()
        n = int(d.get("max_concurrent_projects") or 0)
        if n > 0:
            return n
    except Exception:
        pass
    try:
        return max(1, int(os.environ.get("MYTEAM_MAX_PROJECT_RUNS", "2")))
    except ValueError:
        return 2


class ProjectRuntime:
    """单 Hub 进程内的项目运行管理器。"""

    def __init__(self) -> None:
        self._supervisor = JobSupervisor(store_module.Store())
        self._slot = threading.Semaphore(_max_concurrent())
        self._lock = threading.Lock()

    def is_running(self, project_id: str) -> bool:
        return self._supervisor.is_running(project_id)

    def start(
        self,
        project_id: str,
        runner: Callable,
        *args,
        on_start: Optional[Callable[[str], None]] = None,
        on_end: Optional[Callable[[str, Optional[BaseException]], None]] = None,
        **kwargs,
    ) -> str:
        if self.is_running(project_id):
            raise RuntimeError(f"project {project_id} already running")

        def wrapped() -> None:
            cancel_registry.register(project_id)
            if on_start:
                on_start(project_id)
            self._slot.acquire()
            err: Optional[BaseException] = None
            try:
                runner(*args, **kwargs)
            except BaseException as e:
                err = e
                raise
            finally:
                self._slot.release()
                cancel_registry.clear(project_id)
                # 兜底：无论 runner 成功/失败/异常，都清除 hub_kernel_run.running 标记
                try:
                    import common.store.store as _store_mod
                    _s = _store_mod.Store()
                    try:
                        _p = _s.get_project(project_id)
                        if _p:
                            _s.update_project_meta(
                                project_id,
                                hub_kernel_run={"running": False, "error": None},
                            )
                    finally:
                        _s.close()
                except Exception:
                    pass
                if on_end:
                    on_end(project_id, err)

        return self._supervisor.start_job(project_id, wrapped)

    def cancel(self, project_id: str) -> tuple[bool, str]:
        store = store_module.Store()
        try:
            proj = store.get_project(project_id)
            if not proj:
                return False, "项目不存在"
            if proj.get("status") in _PROJECT_TERMINAL:
                return False, f"项目已终态：{proj.get('status')}"
            store.set_project_status(project_id, "cancelled")
        finally:
            store.close()
        cancel_registry.cancel(project_id)
        self._supervisor.cancel_job(project_id)
        logger.info("cancel requested for project %s", project_id)
        return True, "cancelled"

    def pause(self, project_id: str) -> tuple[bool, str]:
        """暂停项目：与 cancel 同样停 CLI 子进程 + 调度，但置 paused（可 resume 恢复）。

        当前 in_progress 的 task 置回 pending，让 resume 时重新派发（不续跑被中断的半截执行）。
        """
        store = store_module.Store()
        try:
            proj = store.get_project(project_id)
            if not proj:
                return False, "项目不存在"
            st = proj.get("status") or ""
            # paused 属终态但可 resume；cancelled/failed 等不可 pause
            if st in (_PROJECT_TERMINAL - {"paused"}):
                return False, f"项目已终态：{st}"
            store.set_project_status(project_id, "paused")
            # 把 in_progress 的 task 置回 pending，resume 时重新派发
            for t in store.list_tasks(project_id):
                if t.get("status") == "in_progress":
                    tid = t.get("task_id") or t.get("id")
                    if tid:
                        store.set_task_status(project_id, tid, "pending")
        finally:
            store.close()
        cancel_registry.cancel(project_id)  # 停当前 CLI 子进程
        self._supervisor.cancel_job(project_id)  # 停后续派发
        logger.info("pause requested for project %s", project_id)
        return True, "paused"


_runtime: Optional[ProjectRuntime] = None
_runtime_lock = threading.Lock()


def get_project_runtime() -> ProjectRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = ProjectRuntime()
        return _runtime


def reset_project_runtime() -> None:
    """测试或 Hub 热重载时重置单例（生产路径勿调用）。"""
    global _runtime
    with _runtime_lock:
        _runtime = None
