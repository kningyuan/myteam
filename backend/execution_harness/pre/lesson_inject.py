"""PRE — 同类任务教训注入（Path B：Failure → Lesson → Behavior Change）。

从 KB 检索 ``["lesson", task_type, agent_id]`` 标签的教训条目，
以「【同类任务教训】」块注入 execute prompt。"""

from __future__ import annotations

import logging
from typing import Optional

from common.store import Store

logger = logging.getLogger("execution_harness.pre.lesson_inject")

_LESSON_TAG = "lesson"

# lesson 注入 prompt 模板
_LESSON_BLOCK_HEADER = "【同类任务教训（避免再犯）】"


def fetch_lesson_entries(
    project_id: str,
    task_type: str,
    agent_id: str,
    *,
    limit: int = 2,
    store: Optional[Store] = None,
) -> list[dict]:
    """从 memory 检索 lesson 标签条目。

    优先级：当前项目 lesson → 全局同类 lesson。
    """
    if not store:
        return []
    entries: list[dict] = []

    # 1. 当前项目 + 当前 agent + 当前 task_type
    entries = store.memory_search(
        tags=[_LESSON_TAG, agent_id, task_type],
        project_id=project_id,
        limit=limit,
    )
    if len(entries) >= limit:
        return entries[:limit]

    # 2. 全局 + 当前 agent + 当前 task_type
    global_entries = store.memory_search(
        tags=[_LESSON_TAG, agent_id, task_type],
        limit=limit,
    )
    seen = {e.get("id") for e in entries}
    for e in global_entries:
        if e.get("id") in seen:
            continue
        entries.append(e)
        if len(entries) >= limit:
            break

    # 3. 任 agent + 当前 task_type（跨 agent 可复用经验）
    if len(entries) < limit:
        cross_entries = store.memory_search(
            tags=[_LESSON_TAG, task_type],
            limit=limit * 2,
        )
        cross_seen = {e.get("id") for e in entries}
        for e in cross_entries:
            if e.get("id") in cross_seen:
                continue
            entries.append(e)
            if len(entries) >= limit:
                break

    return entries[:limit]


def _clip_lesson(text: str, n: int = 300) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def append_lesson_hints(
    lines: list[str],
    project_id: str,
    task_type: str,
    agent_id: str,
    *,
    limit: int = 2,
    store: Optional[Store] = None,
) -> None:
    """向 execute prompt 追加同类任务教训块。"""
    entries = fetch_lesson_entries(
        project_id, task_type, agent_id, limit=limit, store=store,
    )
    if not entries:
        return

    lines.append("")
    lines.append(_LESSON_BLOCK_HEADER)
    for e in entries:
        title = e.get("title") or "lesson"
        content = _clip_lesson(e.get("content") or "")
        # 从 title 提取 agent 来源
        agent_hint = ""
        parts = title.split(":")
        if len(parts) >= 2 and parts[0] == "lesson":
            agent_hint = f"（来自 {parts[1]}）" if len(parts) >= 2 else ""
        lines.append(f"- {agent_hint} {content}" if agent_hint else f"- {content}")
    lines.append("")