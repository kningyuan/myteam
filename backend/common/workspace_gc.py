#!/usr/bin/env python3
"""Agent workspace 临时文件 GC — 自动清理 .trigger/.response 中的历史 interaction 件。

store 是真相；磁盘上的 .request/.response 只是传输缓存。interaction 进入终态且
框架已采纳响应后，这些文件应删除，避免 agent 工作目录堆积旧项目信息。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from common import paths
from common.agent_port import read_adoptable_response
from common.paths import response_dir, trigger_dir
from common.store import Store

_TERMINAL = frozenset({"done", "timed_out", "failed"})
_ORPHAN_GRACE_SEC = 3600  # 无 DB 记录的残留件：超过 1h 才删（防竞态）


def interaction_paths(agent_id: str, interaction_id: str) -> tuple[Path, Path]:
    return (
        trigger_dir(agent_id) / f"{interaction_id}.request",
        response_dir(agent_id) / f"{interaction_id}.response",
    )


def remove_interaction_files(agent_id: str, interaction_id: str) -> int:
    """删除一次 interaction 的 request/response 临时件。返回删除的文件数。"""
    if not agent_id or not interaction_id:
        return 0
    removed = 0
    for p in interaction_paths(agent_id, interaction_id):
        if p.is_file():
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def remove_legacy_task_files(agent_id: str, project_id: str) -> int:
    """清理旧版 ``{project_id}_{task_id}.trigger/.response/.ack`` 命名残留。"""
    if not agent_id or not project_id:
        return 0
    removed = 0
    prefix = f"{project_id}_"
    for d in (trigger_dir(agent_id), response_dir(agent_id)):
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            if not p.name.startswith(prefix):
                continue
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def gc_project_workspace(store: Store, project_id: str) -> dict:
    """清理某项目在所有 agent workspace 里留下的 interaction 临时件。"""
    files_removed = 0
    for it in store.list_interactions(project_id):
        agent = it.get("agent_id") or ""
        iid = it.get("interaction_id") or ""
        if agent and iid:
            files_removed += remove_interaction_files(agent, iid)
    agents = {it.get("agent_id") for it in store.list_interactions(project_id) if it.get("agent_id")}
    for agent in agents:
        files_removed += remove_legacy_task_files(agent, project_id)
    return {"project_id": project_id, "files_removed": files_removed}


def gc_terminal_interactions(store: Store) -> dict:
    """按 DB 终态 interaction 清理磁盘临时件（启动对账 / Hub 启动时可调用）。

    timed_out/failed 且磁盘仍有可采纳 .response 时跳过删除，留给 reconcile /
    settle 回收，避免启动 gc 与对账竞态。
    """
    rows = store.list_interactions_by_statuses(("done", "timed_out", "failed"))
    files_removed = 0
    seen: set[tuple[str, str]] = set()
    for r in rows:
        agent = r["agent_id"] or ""
        iid = r["interaction_id"] or ""
        key = (agent, iid)
        if not agent or not iid or key in seen:
            continue
        seen.add(key)
        if r["status"] in ("timed_out", "failed"):
            resp, _ = read_adoptable_response(agent, iid)
            if resp is not None:
                continue
        files_removed += remove_interaction_files(agent, iid)
    return {"interactions": len(seen), "files_removed": files_removed}


def gc_orphan_workspace_files(store: Store, *, grace_sec: int = _ORPHAN_GRACE_SEC) -> dict:
    """扫描各 agent 的 .trigger/.response：无 pending/running 记录且超 grace 的残留件删除。"""
    if not paths.WORKSPACES_DIR.is_dir():
        return {"files_removed": 0}
    now = time.time()
    files_removed = 0
    for ws in paths.WORKSPACES_DIR.iterdir():
        if not ws.is_dir() or not ws.name.startswith("workspace-"):
            continue
        agent_id = ws.name.removeprefix("workspace-")
        for d, suffix in ((trigger_dir(agent_id), ".request"), (response_dir(agent_id), ".response")):
            if not d.is_dir():
                continue
            for p in d.iterdir():
                if not p.is_file() or not p.name.endswith(suffix):
                    continue
                iid = p.name[: -len(suffix)]
                row = store.get_interaction(iid)
                if row is not None:
                    st = row.get("status")
                    if st in _TERMINAL:
                        if st in ("timed_out", "failed"):
                            resp, _ = read_adoptable_response(agent_id, iid)
                            if resp is not None:
                                continue
                        try:
                            p.unlink()
                            files_removed += 1
                        except OSError:
                            pass
                    continue
                if now - p.stat().st_mtime >= grace_sec:
                    try:
                        p.unlink()
                        files_removed += 1
                    except OSError:
                        pass
    return {"files_removed": files_removed}


def gc_workspace(store: Optional[Store] = None) -> dict:
    """一次完整 sweep：终态 interaction 件 + 孤儿残留。"""
    own = store is None
    store = store or Store()
    try:
        terminal = gc_terminal_interactions(store)
        orphan = gc_orphan_workspace_files(store)
    finally:
        if own:
            store.close()
    return {
        "files_removed": terminal["files_removed"] + orphan["files_removed"],
        "terminal_interactions": terminal["interactions"],
    }
