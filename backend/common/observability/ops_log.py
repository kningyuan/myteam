#!/usr/bin/env python3
"""任务完成后写入 publish_log / audit_log。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def maybe_log_task_completion(
    project_id: str,
    task_id: str,
    task_type: str,
    *,
    status: str = "completed",
) -> None:
    """按 task_type 写入运营日志表（best-effort）。"""
    if status not in ("completed", "needs_review"):
        return
    try:
        from common.paths import deliverables_dir
        from common.store.store import Store

        store = Store()
        dv = deliverables_dir(project_id) / f"{task_id}_deliverable.md"
        deliverable = str(dv) if dv.is_file() else ""

        if task_type == "publish-post":
            platform = "zhihu" if "zhihu" in task_id.lower() else "generic"
            store.insert_publish_log(
                project_id, task_id=task_id, platform=platform,
                deliverable=deliverable, status=status,
            )
        elif task_type in ("geo-audit", "geo-verification"):
            store.insert_audit_log(
                project_id, task_id=task_id, audit_type="geo",
                deliverable=deliverable, status=status,
            )
    except Exception:
        pass
