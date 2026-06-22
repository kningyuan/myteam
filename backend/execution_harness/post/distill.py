#!/usr/bin/env python3
"""POST — ledger 结构化蒸馏（无 LLM，YAML → 可读 fact 摘要）。"""
from __future__ import annotations

from execution_harness.post._yaml_util import (
    clip,
    parse_simple_yaml,
    strip_comments,
)


def distill_ledger_body(raw: str, *, task_type: str = "", task_id: str = "") -> str:
    """将 ledger YAML 压成 KB 友好摘要（保留 pitfalls/keywords）。"""
    body = strip_comments(raw or "")
    if not body:
        return ""
    parsed = parse_simple_yaml(body)
    lines: list[str] = []
    header = task_type or str(parsed.get("task_type") or "task")
    tid = task_id or str(parsed.get("task_id") or "")
    lines.append(f"# {header}:{tid} — distilled" if tid else f"# {header} — distilled")
    lines.append("")

    for key in ("intent", "goal", "summary", "outcome", "director_verdict", "director_score"):
        val = parsed.get(key)
        if val:
            lines.append(f"**{key}**: {clip(str(val), 400)}")

    lesson = parsed.get("lesson")
    if isinstance(lesson, dict):
        for lk, lv in lesson.items():
            if lv:
                lines.append(f"**lesson.{lk}**: {clip(str(lv), 400)}")
    elif lesson:
        lines.append(f"**lesson**: {clip(str(lesson), 400)}")

    for key in ("worked", "failed", "director_correction", "next_time"):
        val = parsed.get(key)
        if val:
            lines.append(f"**{key}**: {clip(str(val), 400)}")

    for key in ("pitfall", "pitfalls", "keywords", "tags", "sources"):
        val = parsed.get(key)
        if isinstance(val, list):
            lines.append(f"**{key}**:")
            for item in val[:8]:
                lines.append(f"- {clip(str(item), 200)}")
        elif val:
            lines.append(f"**{key}**: {clip(str(val), 400)}")

    if len(lines) <= 2:
        lines.append(clip(body, 600))
    lines.append("")
    lines.append("<!-- distilled_from: ledger.entry.yaml -->")
    return "\n".join(lines)