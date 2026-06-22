#!/usr/bin/env python3
"""umbrella skill references/ 目录 — 同类任务沉淀。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from common.paths import MYTEAM_ROOT
from common.registry import is_stub
from common.skill_catalog import SKILLS_DIR

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def references_dir(umbrella_skill_id: str) -> Path:
    return SKILLS_DIR / umbrella_skill_id / "references"


def reference_file(umbrella_skill_id: str, task_type: str, task_id: str) -> Path:
    safe_tid = re.sub(r"[^\w\-]+", "_", task_id or "task")
    safe_tt = re.sub(r"[^\w\-]+", "_", task_type or "type")
    return references_dir(umbrella_skill_id) / f"{safe_tt}-{safe_tid}.md"


def write_reference_from_ledger(
    umbrella_skill_id: str,
    base_dir: Path,
    task_type: str,
    task_id: str,
) -> Optional[Path]:
    ledger = base_dir / "ledger.entry.yaml"
    if not ledger.is_file():
        return None
    raw = ledger.read_text(encoding="utf-8", errors="replace")
    body = _COMMENT_RE.sub("", raw).strip()
    if is_stub(body, 30):
        return None
    out = reference_file(umbrella_skill_id, task_type, task_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = f"# {task_type}:{task_id}\n\n> 自动沉淀自 ledger；供同类 execute 按需 Read。\n\n"
    out.write_text(header + raw.strip() + "\n", encoding="utf-8")
    return out


def list_reference_pointers(
    umbrella_skill_id: str,
    project_id: str,
    task_type: str,
    *,
    limit: int = 3,
) -> list[str]:
    """返回 prompt 用的相对路径指针（不含全文）。"""
    d = references_dir(umbrella_skill_id)
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[str] = []
    prefix = f"{task_type}-"
    for f in files:
        if task_type and not f.name.startswith(prefix):
            continue
        try:
            rel = f.relative_to(MYTEAM_ROOT)
            out.append(str(rel))
        except ValueError:
            out.append(str(f))
        if len(out) >= limit:
            break
    return out
