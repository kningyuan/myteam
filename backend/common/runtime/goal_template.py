#!/usr/bin/env python3
"""从 Goal 文本解析 template_id 等项目级默认值。"""
from __future__ import annotations

import re
from typing import Optional

_GOAL_TEMPLATE_RE = re.compile(
    r"^\s*[-*]?\s*template_id\s*:\s*(\S+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_goal_template_id(goal: str) -> Optional[str]:
    m = _GOAL_TEMPLATE_RE.search(goal or "")
    return m.group(1).strip() if m else None


def apply_goal_template_defaults(tasks: list[dict], goal: str) -> list[dict]:
    """Goal 中的 template_id 填充尚未显式指定的任务。"""
    goal_tpl = parse_goal_template_id(goal)
    if not goal_tpl:
        return tasks
    out: list[dict] = []
    for t in tasks:
        item = dict(t)
        if not str(item.get("template_id") or "").strip():
            item["template_id"] = goal_tpl
        out.append(item)
    return out
