#!/usr/bin/env python3
"""prompt 注入块 — 统一标题格式。"""
from __future__ import annotations


def append_block(lines: list[str], title: str, body: str) -> None:
    text = (body or "").strip()
    if not text:
        return
    lines.append(title)
    lines.append(text)
    lines.append("")


def append_preference_block(lines: list[str], body: str) -> None:
    append_block(lines, "【用户偏好】", body)


def append_kb_top_k(lines: list[str], entries: list[dict], *, title: str = "【相关知识】") -> None:
    if not entries:
        return
    lines.append(title)
    for e in entries:
        t = e.get("title") or "entry"
        content = (e.get("content") or "").strip().replace("\n", " ")
        if len(content) > 200:
            content = content[:199] + "…"
        lines.append(f"- {t}: {content}")
    lines.append("")


def append_l1_block(lines: list[str], hint: str) -> None:
    append_block(lines, "【工作记忆（本 Agent）】", hint)


def append_umbrella_skill_block(lines: list[str], skill_id: str, skill_path: str) -> None:
    if not skill_id:
        return
    lines.append("【本任务推荐方法论 Skill — 必读】")
    lines.append(f"- umbrella skill：`{skill_id}`")
    lines.append(f"- 路径：`{skill_path}`")
    lines.append("- 执行前须 Read 上述 SKILL.md 全文，按 Procedure / Pitfalls / Verification 操作。")
    lines.append("- 同类历史细节见该 skill 下 `references/`（按需 Read，勿一次全读）。")
    lines.append("")


def append_reference_pointers(lines: list[str], pointers: list[str]) -> None:
    if not pointers:
        return
    lines.append("【同类任务参考（references，按需 Read）】")
    for p in pointers:
        lines.append(f"- {p}")
    lines.append("")
