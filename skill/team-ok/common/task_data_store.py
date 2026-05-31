#!/usr/bin/env python3
"""Task Data Store — task_data.json CRUD 操作模块。

集中管理 `~/.openclaw/tasks/projects/{project_id}/task_data.json` 的读写、
状态更新、子任务操作、journal 日志等。

用法:
    data = read_task_data("pro_xxx")
    update_task_status("pro_xxx", "task_001", "completed")
"""
import fcntl
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

HOME = Path.home()
BASE = HOME / ".openclaw"


def project_dir(project_id: str) -> Path:
    return BASE / "tasks" / "projects" / project_id


def task_data_path(project_id: str) -> Path:
    return project_dir(project_id) / "task_data.json"


def _task_data_lock_path(project_id: str) -> Path:
    return project_dir(project_id) / ".task_data.lock"


def deliverables_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "deliverables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def trigger_dir(agent_id: str) -> Path:
    return BASE / f"workspace-{agent_id}" / ".trigger"


def response_dir(agent_id: str) -> Path:
    return BASE / f"workspace-{agent_id}" / ".response"


def _cleanup_stale_tmp_files(path: Path):
    """清理此路径的残留临时文件（进程崩溃留下的 .json.*.tmp）。"""
    pattern = path.with_suffix(f".json.*.tmp")
    for tmp in Path(path.parent).glob(f"{path.stem}*.tmp"):
        try:
            tmp.unlink()
        except OSError:
            pass


def atomic_write_json(path: Path, data: dict):
    """原子写入 JSON 文件：先写临时文件，再 os.rename（POSIX 原子操作）。"""
    _cleanup_stale_tmp_files(path)
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.rename(str(tmp), str(path))


def is_pid_alive(pid: int) -> bool:
    """检查 PID 是否存活（信号 0 — 不发送实际信号）。"""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def read_task_data(project_id: str) -> dict:
    path = task_data_path(project_id)
    if not path.exists():
        return {"project": {}, "tasks": [], "executor_pid": None, "journal": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_task_data(project_id: str, data: dict):
    """写 task_data.json（通过 fcntl.flock 保护并发写入）。"""
    data["executor_pid"] = os.getpid()
    if "journal" not in data:
        data["journal"] = []
    lock_path = _task_data_lock_path(project_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            atomic_write_json(task_data_path(project_id), data)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def journal_append(project_id: str, op: str, task_id: str, subtask_id: str = None):
    data = read_task_data(project_id)
    data.setdefault("journal", [])
    data["journal"].append({
        "op": op,
        "task_id": task_id,
        "subtask_id": subtask_id,
        "started_at": datetime.now().isoformat(),
    })
    write_task_data(project_id, data)


def journal_clear(project_id: str):
    data = read_task_data(project_id)
    data["journal"] = []
    write_task_data(project_id, data)


def get_task_info(project_id: str, task_id: str) -> Optional[dict]:
    """搜索顶层任务和子任务。"""
    data = read_task_data(project_id)
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            return t
        for st in t.get("subtasks", []):
            if st.get("id") == task_id:
                return st
    return None


def get_task_name(project_id: str, task_id: str) -> str:
    info = get_task_info(project_id, task_id)
    return info.get("name", task_id) if info else task_id


def get_task_description(project_id: str, task_id: str) -> str:
    info = get_task_info(project_id, task_id)
    return info.get("description", "") if info else ""


def get_task_status(project_id: str, task_id: str) -> str:
    info = get_task_info(project_id, task_id)
    return info.get("status", "unknown") if info else "unknown"


def update_task_status(project_id: str, task_id: str, status: str):
    """更新任务状态（支持顶层任务和子任务）。"""
    data = read_task_data(project_id)
    now = datetime.now().isoformat()
    found = False

    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            t["status"] = status
            t["updated_at"] = now
            if status == "in_progress" and not t.get("started_at"):
                t["started_at"] = now
            if status in ("completed", "failed") and not t.get("completed_at"):
                t["completed_at"] = now
            found = True
            break
        for st in t.get("subtasks", []):
            if st.get("id") == task_id:
                st["status"] = status
                st["updated_at"] = now
                if status == "in_progress" and not st.get("started_at"):
                    st["started_at"] = now
                if status in ("completed", "failed") and not st.get("completed_at"):
                    st["completed_at"] = now
                found = True
                break
        if found:
            break

    if not found:
        raise ValueError(f"任务 {task_id} 不存在")

    write_task_data(project_id, data)


def reset_task(project_id: str, task_id: str):
    """将任务重置为 pending 状态（支持顶层任务和子任务）。"""
    data = read_task_data(project_id)
    now = datetime.now().isoformat()
    found = False

    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            t["status"] = "pending"
            t["updated_at"] = now
            if t.get("started_at"):
                t["started_at"] = None
            if t.get("completed_at"):
                t["completed_at"] = None
            found = True
            break
        for st in t.get("subtasks", []):
            if st.get("id") == task_id:
                st["status"] = "pending"
                st["updated_at"] = now
                if st.get("started_at"):
                    st["started_at"] = None
                if st.get("completed_at"):
                    st["completed_at"] = None
                found = True
                break
        if found:
            break

    if found:
        write_task_data(project_id, data)


def mark_task_failed(project_id: str, task_id: str, reason: str = ""):
    update_task_status(project_id, task_id, "failed")