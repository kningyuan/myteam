#!/usr/bin/env python3
"""Context 后端聚合 — KB / L1 / 偏好（复用 memstack adapter，不重复实现）。"""
from __future__ import annotations

from typing import Optional

from common.store import Store
from execution_harness.config import inject_top_k, kb_enabled, l1_on_execute


def fetch_l1_hint(
    agent_id: str,
    intent: str,
    *,
    project_id: str = "",
    store: Optional[Store] = None,
) -> str:
    if not l1_on_execute():
        return ""
    try:
        from memstack.l1.protocol import memory_scope_execute
        from memstack.l1.registry import get_agent_memory_provider

        scope = memory_scope_execute(agent_id, project_id=project_id)
        prov = get_agent_memory_provider()
        query = (intent or "execute task context").strip()[:500]
        return (prov.before_turn(scope, query) or "").strip()
    except Exception:
        return ""


def fetch_preferences(_owner_id: str = "", *, agent_id: str = "") -> str:
    try:
        from execution_harness.config import preferences_on_execute

        if not preferences_on_execute():
            return ""
        from memstack.preferences.registry import get_preference_backend

        return (
            get_preference_backend().format_block("default", agent_id=agent_id) or ""
        ).strip()
    except Exception:
        return ""


def fetch_kb_entries(
    project_id: str,
    task_type: str,
    *,
    store: Optional[Store] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    from execution_harness.config import kb_inject_allowed

    if not kb_inject_allowed():
        return []
    try:
        from memstack.kb import get_kb_backend

        kb = get_kb_backend(store)
        top_k = limit if limit is not None else inject_top_k()
        tags = [task_type] if task_type else None
        seen: set[int] = set()
        merged: list[dict] = []
        for pid in ("__global__", project_id):
            if not pid:
                continue
            for entry in kb.search(tags=tags, project_id=pid):
                eid = entry.get("id")
                if eid in seen:
                    continue
                seen.add(eid)
                merged.append(entry)
        return merged[:top_k]
    except Exception:
        return []


def fetch_experience_entries(
    project_id: str,
    task_type: str,
    *,
    limit: int = 3,
    store: Optional[Store] = None,
) -> list[dict]:
    try:
        from memstack.orchestration.experience import fetch_experience_entries as _fetch

        return _fetch(project_id, task_type, limit=limit, store=store)
    except Exception:
        return []
