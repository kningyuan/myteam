"""项目服务 — 读取 tasks/ 下各项目目录。"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Optional

from hub.paths import PROJECTS_DIR, to_relative_path
from common.store import Store


# P0 边界澄清：是否使用 SQLite 替代 task_data.json（0.6）
# 模块级 bool，单测可直接覆盖
_use_sqlite_store: bool = True
_USE_SQLITE_FLAG_INITED: bool = False


def _init_sqlite_flag() -> None:
    """初始化 USE_SQLITE_STORE 标志。"""
    global _use_sqlite_store
    global _USE_SQLITE_FLAG_INITED
    if _USE_SQLITE_FLAG_INITED:
        return
    try:
        from store.system_config import system_config
        _use_sqlite_store = bool(system_config.get("system", "use_sqlite_project_store", default=False))
    except Exception:
        _use_sqlite_store = False
    _USE_SQLITE_FLAG_INITED = True


_init_sqlite_flag()


def _sqlite_list_projects() -> list[dict]:
    """从 SQLite 真相库读取项目列表。"""
    try:
        store = Store()
        try:
            projects = store.list_projects()
            out = []
            for p in projects:
                pid = p["project_id"]
                tasks = store.list_tasks(pid) if hasattr(store, "list_tasks") else []
                stats = _task_stats(tasks)
                out.append({
                    "id": pid,
                    "name": p.get("title") or pid,
                    "status": p.get("status", "unknown"),
                    "path": to_relative_path(_project_dir(pid)),
                    "task_count": stats.get("total", 0),
                    "progress": stats.get("progress", 0),
                    "current_task_id": stats.get("current_task_id"),
                    "executor_pid": None,
                })
            return sorted(out, key=lambda x: x["id"], reverse=True)
        finally:
            store.close()
    except Exception:
        return []


def _sqlite_get_project(project_id: str) -> Optional[dict]:
    """从 SQLite 真相库读取单个项目。"""
    try:
        store = Store()
        try:
            p = store.get_project(project_id)
            if not p:
                return None
            tasks = store.list_tasks(project_id) if hasattr(store, "list_tasks") else []
            stats = _task_stats(tasks)
            return {
                "id": project_id,
                "name": p.get("title") or project_id,
                "description": p.get("description", ""),
                "status": p.get("status", "unknown"),
                "path": to_relative_path(_project_dir(project_id)),
                "task_count": stats.get("total", 0),
                "progress": stats.get("progress", 0),
                "current_task_id": stats.get("current_task_id"),
                "executor_pid": None,
                "task_data": {},
                "stats": stats,
                "journal": [],
            }
        finally:
            store.close()
    except Exception:
        return None


def _project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _task_stats(tasks: list) -> dict:
    total = len(tasks)
    by_status: dict[str, int] = {}
    current = None
    for t in tasks:
        st = t.get("status", "pending")
        by_status[st] = by_status.get(st, 0) + 1
        if st == "in_progress" and current is None:
            current = t.get("id")
    completed = by_status.get("completed", 0)
    progress = round(completed / total * 100) if total else 0
    return {
        "total": total,
        "completed": completed,
        "progress": progress,
        "by_status": by_status,
        "current_task_id": current,
    }


def _summarize(project_id: str, data: dict) -> dict:
    project = data.get("project") or {}
    tasks = data.get("tasks") or []
    stats = _task_stats(tasks)
    return {
        "id": project_id,
        "name": project.get("name") or project_id,
        "description": project.get("description", ""),
        "status": project.get("status", "unknown"),
        "path": to_relative_path(_project_dir(project_id)),
        "task_count": stats["total"],
        "progress": stats["progress"],
        "current_task_id": stats["current_task_id"],
        "executor_pid": data.get("executor_pid"),
    }


def list_projects() -> list[dict]:
    if _use_sqlite_store:
        result = _sqlite_list_projects()
        if result:
            return result
        # Fallback: SQLite 无数据时读 task_data.json
    if not PROJECTS_DIR.is_dir():
        return []
    warnings.warn("Reading from task_data.json is deprecated, use SQLite store instead", DeprecationWarning, stacklevel=2)
    result = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        td = d / "task_data.json"
        if not td.is_file():
            continue
        data = _read_json(td)
        result.append(_summarize(d.name, data))
    return sorted(result, key=lambda x: x["id"], reverse=True)


def get_project(project_id: str) -> Optional[dict]:
    if _use_sqlite_store:
        return _sqlite_get_project(project_id)
    warnings.warn("Reading from task_data.json is deprecated, use SQLite store instead", DeprecationWarning, stacklevel=2)
    td = _project_dir(project_id) / "task_data.json"
    if not td.is_file():
        return None
    data = _read_json(td)
    summary = _summarize(project_id, data)
    stats = _task_stats(data.get("tasks") or [])
    return {
        **summary,
        "task_data": data,
        "stats": stats,
        "journal": data.get("journal") or [],
    }


def get_project_log(project_id: str, tail: int = 500) -> str:
    log_path = _project_dir(project_id) / "skill-logs" / "skills.log"
    if not log_path.is_file():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-tail:])
    except OSError:
        return ""
