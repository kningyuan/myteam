"""Job Supervisor — 持久化 job 生命周期管理，替代 _KERNEL_RUNS 内存 dict。

设计规格：docs/myteam-upgrade-design-spec.md §4.3 R2-3

功能：
- 创建 job 记录到 Store
- 取消 job（设置标志位）
- Hub 重启后检测 orphan job
"""

import logging
import os
import signal
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("job_supervisor")


class JobSupervisor:
    """Job 生命周期管理。"""

    def __init__(self, store):
        self.store = store
        self._running_jobs: dict[str, threading.Thread] = {}

    def start_job(self, project_id: str, runner: Callable, *args, **kwargs) -> str:
        """创建 job 记录、启动后台线程、返回 job_id。"""
        job_id = self.store.create_job(project_id, pid=os.getpid())
        t = threading.Thread(
            target=self._run_wrapper,
            args=(project_id, job_id, runner, args, kwargs),
            daemon=True,
        )
        self._running_jobs[project_id] = t
        t.start()
        logger.info("job %s started for project %s", job_id, project_id)
        return job_id

    def _run_wrapper(self, project_id: str, job_id: str,
                     runner: Callable, args: tuple, kwargs: dict):
        """包装 runner，结束后更新 job 状态。"""
        try:
            runner(*args, **kwargs)
            self.store.update_job_status(job_id, "completed")
        except Exception as e:
            logger.error("job %s failed: %s", job_id, e)
            self.store.update_job_status(job_id, "failed", error=str(e))
        finally:
            self._running_jobs.pop(project_id, None)

    def cancel_job(self, project_id: str) -> bool:
        """取消 job：设置 Store 标志位，发送 SIGTERM。返回 True 表示已取消。"""
        job = self.store.get_latest_job(project_id)
        if not job:
            return False
        self.store.cancel_job_request(project_id)
        # 用 SIGTERM 终止进程
        pid = job.get("pid")
        if pid and pid != os.getpid():
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, PermissionError):
                pass
        # 标记取消
        self.store.update_job_status(job["job_id"], "cancelled")
        self._running_jobs.pop(project_id, None)
        logger.info("job %s cancelled for project %s", job["job_id"], project_id)
        return True

    def get_job(self, project_id: str) -> Optional[dict]:
        """查询 project 最新的 job 记录。"""
        return self.store.get_latest_job(project_id)

    def list_jobs(self, status: str = "") -> list[dict]:
        return self.store.list_jobs(status=status)

    def resume_orphans(self) -> list[dict]:
        """扫描 status=running → 标记 orphan → 返回列表。"""
        orphans = []
        for job in self.store.list_jobs(status="running"):
            pid = job.get("pid")
            if pid and self._pid_exists(pid):
                continue
            self.store.update_job_status(job["job_id"], "orphan",
                                         error="Hub 重启后被标记为 orphan")
            orphans.append(job)
        if orphans:
            logger.warning("marked %d jobs as orphan", len(orphans))
        return orphans

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        """检查 pid 是否存活。"""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False