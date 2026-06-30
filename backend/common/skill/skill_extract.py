#!/usr/bin/env python3
"""L3 skill 抽提 scaffold — 从完成任务交付物生成 SKILL.md 草案。"""
from __future__ import annotations

from pathlib import Path

from common.paths import BUSINESS_DIR, MYTEAM_ROOT, to_relative_path
from common.store.store import Store

SKILLS_DIR = BUSINESS_DIR / "skills"


def draft_dir(project_id: str, task_id: str) -> Path:
    return SKILLS_DIR / f"auto-{project_id}-{task_id}"


def skill_draft_path(project_id: str, task_id: str) -> Path:
    return draft_dir(project_id, task_id) / "SKILL.md"


def _read_pattern_summary(deliverable: Path) -> str:
    if deliverable.is_file():
        return deliverable.read_text(encoding="utf-8", errors="replace")[:500]
    if deliverable.is_dir():
        for pattern in ("*.md", "**/*.md"):
            for candidate in sorted(deliverable.glob(pattern)):
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8", errors="replace")[:500]
    return ""


def extract_skill_draft(
    store: Store,
    project_id: str,
    task_id: str,
    deliverable_path: str | Path,
) -> Path:
    """从交付物生成最小 SKILL.md 草案，写入 business/skills/auto-<project>-<task>/。"""
    deliverable = Path(deliverable_path)
    if not deliverable.is_absolute():
        deliverable = (MYTEAM_ROOT / deliverable).resolve()

    task = store.get_task(project_id, task_id) or {}
    project = store.get_project(project_id) or {}
    project_meta = project.get("meta") or {}
    project_goal = project_meta.get("goal") or ""
    task_type = task.get("task_type", "")
    agent = task.get("agent", "")
    pattern_summary = _read_pattern_summary(deliverable)
    deliverable_rel = to_relative_path(deliverable)

    out_dir = draft_dir(project_id, task_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    skill_path = out_dir / "SKILL.md"
    skill_path.write_text(
        f"""---
name: auto-{project_id}-{task_id}
task_type: {task_type}
project_id: {project_id}
task_id: {task_id}
agent: {agent}
source_deliverable: {deliverable_rel}
description: L3 自动抽提 skill 草案（scaffold）
---

# auto-{project_id}-{task_id}

> L3 skill 抽提 scaffold — 摘自交付物前 500 字 + 元数据，非最终 Skill Pack。

## 元数据

| 字段 | 值 |
|------|-----|
| project_id | {project_id} |
| task_id | {task_id} |
| task_type | {task_type} |
| agent | {agent} |
| project_goal | {project_goal} |
| deliverable | `{deliverable_rel}` |

## Pattern 摘要（交付物前 500 字）

```
{pattern_summary}
```
""",
        encoding="utf-8",
    )
    return skill_path


def list_skill_drafts() -> list[Path]:
    """列出 business/skills/auto-*/SKILL.md 草案路径。"""
    if not SKILLS_DIR.is_dir():
        return []
    drafts: list[Path] = []
    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir() and entry.name.startswith("auto-"):
            skill = entry / "SKILL.md"
            if skill.is_file():
                drafts.append(skill)
    return sorted(drafts)
