#!/usr/bin/env python3
"""Deliverable 元数据操作助手。

围绕 Store.deliverable 表的轻量封装：upsert / 列表 / 统计。
"""
from __future__ import annotations

from typing import Optional

from common.store import Store


def upsert_deliverable(
    store: Store,
    project_id: str,
    task_id: str,
    file_path: str,
    file_name: str,
    file_size: int = 0,
    file_kind: str = "file",
    task_type: str = "",
) -> int:
    """注册 / 更新一条 deliverable 元数据。

    返回 row id。
    """
    return store.upsert_deliverable(
        project_id, task_id, file_path, file_name,
        file_size, file_kind, task_type,
    )


def list_deliverables(
    store: Store,
    project_id: str,
    task_id: Optional[str] = None,
) -> list[dict]:
    """列出 deliverable 列表，可按 task_id 过滤。"""
    return store.list_deliverables(project_id, task_id=task_id)


def get_deliverable_stats(
    store: Store,
    project_id: str,
) -> dict:
    """返回 {file_kind: count} 统计。"""
    return store.get_deliverable_stats(project_id)
