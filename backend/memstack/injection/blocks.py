#!/usr/bin/env python3
"""prompt 注入块 — Framework 统一格式。"""
from __future__ import annotations

from typing import Optional


def append_block(lines: list[str], title: str, body: str) -> None:
    text = (body or "").strip()
    if not text:
        return
    lines.append(title)
    lines.append(text)
    lines.append("")


def append_preference_block(lines: list[str], body: str) -> None:
    append_block(lines, "【用户偏好】", body)


def append_kb_top_k(
    lines: list[str],
    entries: list[dict],
    *,
    title: str = "【相关知识】",
    task_type: Optional[str] = None,
) -> None:
    """将 KB 条目注入 prompt。

    支持结构化条目（含 ``structured_content`` 字段）：按模板字段展示。
    支持传统条目：截断到 200 字符展示（向后兼容）。
    """
    if not entries:
        return
    lines.append(title)
    for e in entries:
        t = e.get("title") or "entry"
        struct = e.get("structured_content")
        if struct:
            content_preview = _format_structured_entry(struct, task_type)
        else:
            content = (e.get("content") or "").strip().replace("\n", " ")
            if len(content) > 200:
                content = content[:199] + "…"
            content_preview = content
        lines.append(f"- {t}: {content_preview}")
    lines.append("")


def _format_structured_entry(struct: dict[str, str], task_type: Optional[str] = None) -> str:
    """格式化结构化 KB 条目为单行预览。

    优先展示关键字段：objective/problem/decision。
    """
    priority_keys = ["objective", "problem", "decision", "conclusion", "key_findings"]
    for key in priority_keys:
        val = struct.get(key, "").strip()
        if val:
            if len(val) > 150:
                val = val[:149] + "…"
            return val
    # fallback: 展示第一个非空字段
    for key, val in struct.items():
        if val.strip():
            if len(val) > 150:
                val = val[:149] + "…"
            return val
    return "(结构化条目)"


def append_block_if(lines: list[str], title: str, body: str | None) -> None:
    """有条件地追加块（body 为空或 None 时不追加）。"""
    if body:
        append_block(lines, title, body)
