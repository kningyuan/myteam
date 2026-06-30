"""project_lib — 统一 facade 封装，汇集 project 层面管理操作。

包级 re-export:
    from common.project_lib import (
        project_artifacts, project_admin, project_cancel,
        project_hooks, project_runtime,
    )

ProjectLib 类（静态方法 facade）:
    ProjectLib.get_deliverable_bundle(store, project_id, task_id) — 交付物捆绑
    ProjectLib.scan_project_dir(proj_dir)                       — 扫描工程目录
    ProjectLib.cancel_project(store, project_id)                — 取消运行中项目
    ProjectLib.list_project_hooks()                             — 可用 hook 列表
    ProjectLib.delete_project(project_id, store=None)           — 彻底删除项目
    ProjectLib.read_artifact_file(store, project_id, task_id, relpath) — 读取产物文件
    ProjectLib.get_project_runtime()                            — 运行时单例
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# ── 包级 re-export ──────────────────────────────────────────────
from common.project import project_admin
from common.project import project_artifacts
from common.project import project_cancel
from common.project import project_hooks
from common.project import project_runtime

__all__ = [
    "project_admin",
    "project_artifacts",
    "project_cancel",
    "project_hooks",
    "project_runtime",
    "ProjectLib",
]

# ── Re-export 模块内精选子符号 ──────────────────────────────────
# project_artifacts
get_task_deliverable_bundle = project_artifacts.get_task_deliverable_bundle
scan_project_dir = project_artifacts.scan_project_dir
read_task_artifact_file = project_artifacts.read_task_artifact_file
is_code_project_task = project_artifacts.is_code_project_task
task_project_dir = project_artifacts.task_project_dir
task_deliverable_base = project_artifacts.task_deliverable_base
artifact_rel_path = project_artifacts.artifact_rel_path

# project_cancel
ProjectCancelRegistry = project_cancel.ProjectCancelRegistry
cancel_registry = project_cancel.cancel_registry

# project_hooks
ProjectHooks = project_hooks.ProjectHooks

# project_admin
delete_project = project_admin.delete_project

# project_runtime
ProjectRuntime = project_runtime.ProjectRuntime
get_project_runtime = project_runtime.get_project_runtime
reset_project_runtime = project_runtime.reset_project_runtime


# ── Facade ───────────────────────────────────────────────────────
class ProjectLib:
    """统一操作入口，每个静态方法封装一个跨模块流程。"""

    @staticmethod
    def get_deliverable_bundle(store, project_id: str, task_id: str) -> dict:
        """返回 task 交付物捆绑包。"""
        return project_artifacts.get_task_deliverable_bundle(store, project_id, task_id)

    @staticmethod
    def scan_project_dir(proj_dir: Path) -> list[dict]:
        """扫描代码工程目录内所有产出文件。"""
        return project_artifacts.scan_project_dir(proj_dir)

    @staticmethod
    def cancel_project(store, project_id: str) -> tuple[bool, str]:
        """取消一个运行中的项目。

        使用已打开的 store 判断当前项目状态，写入 cancelled 后通过
        cancel_registry 通知活跃 DeliveryContext。
        返回 (ok, message)。
        """
        from common.project.project_runtime import _PROJECT_TERMINAL as terminal_states

        proj = store.get_project(project_id)
        if not proj:
            return False, "项目不存在"
        if proj.get("status") in terminal_states:
            return False, f"项目已终态：{proj.get('status')}"

        store.set_project_status(project_id, "cancelled")
        cancel_registry.cancel(project_id)

        # 如运行时存在并正在管理该项目，一并取消 supervisor 任务
        try:
            runtime = project_runtime.get_project_runtime()
            if runtime.is_running(project_id):
                runtime._supervisor.cancel_job(project_id)
        except Exception:
            pass

        return True, "cancelled"

    @staticmethod
    def list_project_hooks() -> list[str]:
        """返回 ProjectHooks 定义的所有回调名称。"""
        return list(project_hooks.ProjectHooks.__dataclass_fields__.keys())

    @staticmethod
    def delete_project(project_id: str, store: Optional[object] = None) -> dict:
        """彻底删除项目（DB + 文件）。"""
        return project_admin.delete_project(project_id, store)

    @staticmethod
    def read_artifact_file(store, project_id: str, task_id: str,
                           relpath: str) -> dict:
        """从交付物目录读取单个文件。"""
        return project_artifacts.read_task_artifact_file(
            store, project_id, task_id, relpath,
        )

    @staticmethod
    def get_project_runtime() -> project_runtime.ProjectRuntime:
        """返回 Hub 进程内 ProjectRuntime 单例。"""
        return project_runtime.get_project_runtime()
