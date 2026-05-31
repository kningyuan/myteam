#!/usr/bin/env python3
"""Deliverable Merger — 子任务交付物合并模块。

父任务被拆分为多个子任务后，按依赖拓扑序合并所有子任务的交付物，
生成父任务的完整交付物文件。合并后的文件用于质量门禁检查。

用法:
    path = merge_subtask_deliverables("pro_xxx", "task_003")
    if path:
        # 对 path 执行质量门禁
"""

import json
from pathlib import Path
from typing import Optional

HOME = Path.home()
BASE = HOME / ".openclaw"


def _project_dir(project_id: str) -> Path:
    return BASE / "tasks" / "projects" / project_id


def _task_data_path(project_id: str) -> Path:
    return _project_dir(project_id) / "task_data.json"


def _deliverables_dir(project_id: str) -> Path:
    d = _project_dir(project_id) / "deliverables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _topological_sort(sub_tasks: list[dict]) -> list[dict]:
    """按依赖关系对子任务拓扑排序。

    无依赖或依赖已完成的排在前面，被依赖的排在后面。
    同层保持原始顺序。
    """
    ordered = []
    remaining = list(sub_tasks)
    placed_ids = set()

    while remaining:
        # 找所有依赖都已放置（或无依赖）的子任务
        ready = []
        for st in remaining:
            deps = set(st.get("dependencies", []))
            # 过滤掉自身依赖和非子任务依赖（如 parent_task）
            local_deps = deps & {s["id"] for s in sub_tasks}
            if local_deps.issubset(placed_ids):
                ready.append(st)

        if not ready:
            # 有环或无法解析 — 按原顺序追加剩余项
            ordered.extend(remaining)
            break

        # 同层保持原始顺序
        ready.sort(key=lambda s: sub_tasks.index(s))
        for st in ready:
            ordered.append(st)
            placed_ids.add(st["id"])
        remaining = [s for s in remaining if s not in ready]

    return ordered


def merge_subtask_deliverables(project_id: str, task_id: str) -> Optional[str]:
    """合并父任务的所有已完成子任务交付物。

    读取 task_data.json 中指定父任务的 subtasks，按依赖拓扑序
    排列，读取每个子任务的 deliverable 文件，拼接写入父任务的
    交付物文件。

    Args:
        project_id: 项目 ID
        task_id: 父任务 ID

    Returns:
        合并后的交付物文件路径，没有子任务或无已完成子任务时返回 None
    """
    data_path = _task_data_path(project_id)
    if not data_path.exists():
        return None

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 查找父任务
    parent_task = None
    for t in data.get("tasks", []):
        if t["id"] == task_id:
            parent_task = t
            break

    if not parent_task:
        return None

    subtasks = parent_task.get("subtasks", [])
    if not subtasks:
        return None

    # 只取已完成子任务
    completed = [s for s in subtasks if s.get("status") == "completed"]
    if not completed:
        return None

    # 拓扑排序（保留已完成子任务间的依赖关系）
    sorted_subtasks = _topological_sort(completed)

    # 读取各子任务交付物
    dv_dir = _deliverables_dir(project_id)
    merged_parts = []

    for st in sorted_subtasks:
        st_id = st["id"]
        st_name = st.get("name", st_id)
        st_file = dv_dir / f"{st_id}_deliverable.md"
        if not st_file.exists():
            continue

        content = st_file.read_text(encoding="utf-8")
        merged_parts.append(f"\n## {st_name}\n\n{content.strip()}")

    if not merged_parts:
        return None

    # 写入父任务交付物文件
    parent_dv = dv_dir / f"{task_id}_deliverable.md"
    merged_content = "\n---\n".join(merged_parts)
    parent_dv.write_text(merged_content, encoding="utf-8")

    return str(parent_dv)