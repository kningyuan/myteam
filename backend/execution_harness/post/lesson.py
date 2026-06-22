"""POST — 任务经验教训写入（Path B：Failure → Lesson → Behavior Change）。

在 task 有 retry 成功的场景下，从 ledger.entry.yaml 提取教训，
写入 KB 带 ``["lesson", task_type]`` tag，供下次同类任务 PRE 注入。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from common.store import Store
from execution_harness.post._yaml_util import parse_simple_yaml

logger = logging.getLogger("execution_harness.post.lesson")

_LESSON_TAG = "lesson"


def extract_lesson_from_ledger(base_dir: Path) -> Optional[str]:
    """从 ledger.entry.yaml 提取教训摘要。

    优先取 ``pitfalls`` + ``lesson`` 内容；若缺失则从 ``failed`` / ``director_correction`` 合成。
    返回纯文本教训块（约 200 字内）。
    """
    ledger = base_dir / "ledger.entry.yaml"
    if not ledger.is_file():
        return None

    raw = ledger.read_text(encoding="utf-8", errors="replace")
    parsed = parse_simple_yaml(raw)
    if not _has_lesson_content(parsed):
        return None

    lesson_lines: list[str] = []
    pitfalls = parsed.get("pitfalls") or parsed.get("pitfall") or []
    if isinstance(pitfalls, str):
        pitfalls = [pitfalls]
    lesson = parsed.get("lesson")
    failed = parsed.get("failed", "")
    correction = parsed.get("director_correction", parsed.get("next_time", ""))

    if pitfalls:
        lesson_lines.append("【已知陷阱】")
        for p in list(pitfalls)[:3]:
            lesson_lines.append(f"  - {p}")
    if lesson:
        if isinstance(lesson, dict):
            lesson_text = "；".join(
                f"{k}: {v}" for k, v in lesson.items() if v
            )
            lesson_lines.append(f"【经验教训】{lesson_text}")
        else:
            lesson_lines.append(f"【经验教训】{lesson}")
    if failed and not lesson:
        lesson_lines.append(f"【上一轮失败原因】{failed}")
    if correction and not failed:
        lesson_lines.append(f"【修正方向】{correction}")

    if not lesson_lines:
        return None
    return "\n".join(lesson_lines)


def _has_lesson_content(parsed: dict) -> bool:
    """检测 parsed YAML 是否含教训相关内容。"""
    if parsed.get("lesson"):
        return True
    if parsed.get("pitfalls") or parsed.get("pitfall"):
        return True
    if parsed.get("failed"):
        return True
    if parsed.get("director_correction"):
        return True
    return False


def write_lesson_entry(
    store: Store,
    project_id: str,
    task_id: str,
    task_type: str,
    agent_id: str,
    base_dir: Path,
    attempt: int,
) -> Optional[int]:
    """从 ledger 提取教训，写入 KB（``["lesson", task_type, agent_id]`` tag）。

    Returns:
        memory id, or None if no lesson found.
    """
    lesson_text = extract_lesson_from_ledger(base_dir)
    if not lesson_text:
        return None

    title = f"lesson:{agent_id}/{task_type}:{task_id}"
    tags = [_LESSON_TAG, task_type, agent_id, "ledger"]
    return store.memory_write(
        project_id,
        title,
        lesson_text,
        tags=tags,
    )