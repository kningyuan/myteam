#!/usr/bin/env python3
"""项目级管理操作（删除）—— 跨 DB 真相库 + 文件系统临时件的一处出口。

删除一个项目 = 删 state.db 的 5 表行（store.delete_project）+ 清 agent 工作目录里该项目
留下的 .trigger/.response 临时件 + 删项目交付物目录。Store 只管 DB，文件清理放这里。
"""
from __future__ import annotations

import shutil
from typing import Optional

from common.paths import project_dir
from common.store.store import Store
from common.runtime.workspace_gc import remove_interaction_files, remove_legacy_task_files


def delete_project(project_id: str, store: Optional[Store] = None) -> dict:
    """彻底删除一个项目，返回清理摘要（删了多少交互/文件、项目目录是否存在）。"""
    own = store is None
    store = store or Store()
    try:
        interactions = store.delete_project(project_id)
    finally:
        if own:
            store.close()

    files_removed = 0
    for it in interactions:
        agent = it.get("agent_id") or ""
        iid = it["interaction_id"]
        if not agent:
            continue
        files_removed += remove_interaction_files(agent, iid)

    agents = {it.get("agent_id") for it in interactions if it.get("agent_id")}
    for agent in agents:
        files_removed += remove_legacy_task_files(agent, project_id)

    pdir = project_dir(project_id)
    pdir_removed = pdir.exists()
    if pdir_removed:
        shutil.rmtree(pdir, ignore_errors=True)

    return {"interactions": len(interactions), "files_removed": files_removed,
            "project_dir_removed": pdir_removed}
