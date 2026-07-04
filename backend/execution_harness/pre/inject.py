#!/usr/bin/env python3
"""PRE — execute 前注入 prompt 块。"""
from __future__ import annotations

import logging

from execution_harness.backends.context_provider import (
    fetch_experience_entries,
    fetch_kb_entries,
    fetch_l1_hint,
    fetch_preferences,
)
from execution_harness.config import experience_clip_chars, execute_harness_enabled, kb_inject_allowed, lesson_inject_enabled
from execution_harness.context import ExecuteHarnessContext
from execution_harness.injection.blocks import (
    append_kb_top_k,
    append_l1_block,
    append_preference_block,
    append_reference_pointers,
    append_rubric_block,
    append_umbrella_skill_block,
)
from execution_harness.pre.lesson_inject import append_lesson_hints
from execution_harness.skill.references import list_reference_pointers
from execution_harness.skill.umbrella import (
    resolve_umbrella_skill,
    resolve_umbrella_skill_sections,
    umbrella_skill_path,
)

logger = logging.getLogger("execution_harness.pre.inject")


def _clip(text: str, n: int) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def _experience_snippet(content: str, n: int) -> str:
    """优先提取 pitfalls/keywords/summary 行，便于 inject 命中。"""
    text = content or ""
    hits: list[str] = []
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in ("pitfall", "keyword", "lesson", "summary", "director", "worked", "failed")):
            s = line.strip().lstrip("-").strip()
            if s:
                hits.append(s)
    if hits:
        return _clip(" | ".join(hits[:5]), n)
    return _clip(text, n)


def append_experience_hints(ctx: ExecuteHarnessContext) -> None:
    entries = fetch_experience_entries(
        ctx.project_id, ctx.task_type, limit=ctx.limit, store=ctx.store
    )
    if not entries:
        return
    n = experience_clip_chars()
    ctx.lines.append("【同类任务经验（KB ledger，参考勿照抄）】")
    for e in entries:
        title = e.get("title") or "ledger"
        ctx.lines.append(f"- {title}: {_experience_snippet(e.get('content') or '', n)}")
    ctx.lines.append("")


def inject_execute_prompt(ctx: ExecuteHarnessContext) -> None:
    """向 execute worker prompt 追加 harness 块。"""
    if not execute_harness_enabled():
        return
    try:
        append_experience_hints(ctx)

        if lesson_inject_enabled():
            append_lesson_hints(
                ctx.lines,
                ctx.project_id,
                ctx.task_type,
                ctx.agent_id,
                limit=min(ctx.limit, 2),
                store=ctx.store,
            )

        umbrella = resolve_umbrella_skill(ctx.task_type)
        if umbrella:
            sp = umbrella_skill_path(umbrella)
            if sp is not None:
                skill_secs = resolve_umbrella_skill_sections(ctx.task_type)
                append_umbrella_skill_block(
                    ctx.lines,
                    umbrella,
                    str(sp),
                    skill_sections=skill_secs,
                    store=ctx.store,
                    project_id=ctx.project_id,
                )
            pointers = list_reference_pointers(
                umbrella, ctx.project_id, ctx.task_type, limit=ctx.limit
            )
            append_reference_pointers(ctx.lines, pointers)

        hint = fetch_l1_hint(
            ctx.agent_id, ctx.intent, project_id=ctx.project_id, store=ctx.store
        )
        append_l1_block(ctx.lines, hint)

        pref = fetch_preferences(agent_id=ctx.agent_id)
        append_preference_block(ctx.lines, pref)

        if kb_inject_allowed():
            entries = fetch_kb_entries(
                ctx.project_id, ctx.task_type, store=ctx.store, limit=ctx.limit
            )
            append_kb_top_k(ctx.lines, entries)

        # 路径 D：Rubric 质量评分标准注入（让 Agent 知晓将被如何评估）
        append_rubric_block(ctx.lines, task_type=ctx.task_type)
    except Exception as e:
        logger.warning("inject_execute_prompt failed: %s", e)
