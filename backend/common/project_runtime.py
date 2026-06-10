#!/usr/bin/env python3
"""Hub 项目运行调度 — JobSupervisor + 并发槽 + 取消注册。"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Optional

from common.job_supervisor import JobSupervisor
from common.project_cancel import cancel_registry
import common.store as store_module

logger = logging.getLogger("project_runtime")

_PROJECT_TERMINAL = {"completed", "failed", "partially_failed", "aborted", "cancelled", "paused", "timed_out"}


def _max_concurrent() -> int:
    try:
        from common.skill_settings import process_defaults

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
