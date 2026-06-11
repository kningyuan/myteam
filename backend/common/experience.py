#!/usr/bin/env python3
"""B 层经验复用 — 检索注入 execute prompt；任务成功后沉淀 ledger。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from common.memory import get_backend
from common.registry import is_stub
from common.store import Store

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clip(text: str, n: int = 240) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def fetch_experience_entries(
    project_id: str,
    task_type: str,
    *,
    limit: int = 3,
    store: Optional[Store] = None,
) -> list[dict]:
    """按 task_type 检索历史 ledger 经验（先本项目，再跨项目）。"""
    if not task_type:
        return []
    kb = get_backend(store)
    entries = kb.search(tags=[task_type, "ledger"], project_id=project_id)[:limit]
    if len(entries) < limit:
        seen = {e.get("id") for e in entries}
        for e in kb.search(tags=[task_type, "ledger"])[: limit * 2]:
            if e.get("id") in seen:
                continue
            entries.append(e)
            if len(entries) >= limit:
                break
    return entries[:limit]


def append_experience_hints(
    lines: list[str],
    project_id: str,
    task_type: str,
    *,
    limit: int = 3,
    store: Optional[Store] = None,
) -> None:
    """将同类任务历史经验块追加到 execute prompt。"""
    entries = fetch_experience_entries(project_id, task_type, limit=limit, store=store)
    if not entries:
        return
    lines.append("【同类任务经验（参考，勿照抄）】")
    for e in entries:
        title = e.get("title") or "ledger"
        lines.append(f"- {title}: {_clip(e.get('content') or '')}")
    lines.append("")


def promote_ledger_to_memory(
    base_dir: Path,
    project_id: str,
    task_id: str,
    task_type: str,
    store: Store,
) -> Optional[str]:
    """任务成功后，将 ledger.entry.yaml 写入 KB（若已实质填写）。"""
    ledger = base_dir / "ledger.entry.yaml"
    if not ledger.is_file():
        return None
    raw = ledger.read_text(encoding="utf-8", errors="replace")
    body = _COMMENT_RE.sub("", raw).strip()
    if is_stub(body, 30):
        return None
    kb = get_backend(store)
    title = f"{task_type}:{task_id}"
    return kb.write(
        project_id,
        title,
        raw,
        task_id=task_id,
        tags=[task_type, "ledger"],
    )
