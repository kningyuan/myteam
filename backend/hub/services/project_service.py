"""项目服务 — 读取 tasks/ 下各项目目录。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from hub.paths import PROJECTS_DIR, to_relative_path


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
    if not PROJECTS_DIR.is_dir():
        return []
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
