#!/usr/bin/env python3
"""Resume Engine — 项目简历恢复数据操作。

处理 task_data.json 中因进程崩溃导致的残留状态：
- 清理过期 journal
- 子任务去重
- 重置卡住的任务状态（in_progress/failed/needs_review → pending）

用法:
    from common.resume_engine import resume_task_data
    modified = resume_task_data("pro_xxx")
    if modified:
        write_task_data("pro_xxx", modified)
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from common.task_data_store import (
    is_pid_alive,
    read_task_data,
)


def resume_task_data(project_id: str) -> Optional[dict]:
    """读取项目数据并执行恢复操作。

    检查 executor_pid 是否存活，清理陈旧 journal，去重子任务，
    重置卡住的 in_progress / failed / needs_review 状态。

    Args:
        project_id: 项目 ID

    Returns:
        修改后的完整 task_data dict，无修改时返回 None
    """
    data = read_task_data(project_id)
    modified = False

    # 清理陈旧 journal
    journal = data.get("journal", [])
    executor_pid = data.get("executor_pid")
    if journal and executor_pid is not None and not is_pid_alive(executor_pid):
        data["journal"] = []
        modified = True

    # 清理重复子任务
    for task in data.get("tasks", []):
        subtasks = task.get("subtasks", [])
        seen_ids = set()
        unique_subtasks = []
        for st in subtasks:
            st_id = st.get("id")
            if st_id and st_id in seen_ids:
                modified = True
                continue
            if st_id:
                seen_ids.add(st_id)
            unique_subtasks.append(st)
        if len(unique_subtasks) != len(subtasks):
            task["subtasks"] = unique_subtasks

    # 重置卡住的任务状态
    for task in data.get("tasks", []):
        # 有已完成子任务的父任务保持 in_progress
        if task["status"] == "in_progress":
            subtasks = task.get("subtasks", [])
            has_completed = any(s.get("status") == "completed" for s in subtasks)
            if not has_completed:
                task["status"] = "pending"
                modified = True

        # failed → pending（仅当 executor 已死：崩溃恢复，非手动标记）
        if task["status"] == "failed" and executor_pid is not None and not is_pid_alive(executor_pid):
            task["status"] = "pending"
            modified = True

        # needs_review → 仅当无已完成子任务时才重置
        if task["status"] == "needs_review":
            subtasks = task.get("subtasks", [])
            has_completed = any(s.get("status") == "completed" for s in subtasks)
            if not has_completed:
                task["status"] = "pending"
                modified = True

        # 重置卡住的子任务
        for sub in task.get("subtasks", []):
            if sub["status"] == "in_progress":
                sub["status"] = "pending"
                modified = True

    return data if modified else None