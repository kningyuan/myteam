#!/usr/bin/env python3
"""memstack facade — Layer A 唯一入口（Framework）。"""
from __future__ import annotations

import logging
from typing import Optional

from memstack.config import inject_top_k, memstack_enabled  # noqa: F401  — inject_top_k 供测试 monkeypatch
from memstack.kb import get_kb_backend
from memstack.l1.protocol import AgentMemoryProvider, MemoryScope, inject_memory_hints
from memstack.l1.registry import get_agent_memory_provider
from memstack.orchestration.context import (
    ChatTurnContext,
    ConsensusContext,
    ExecuteInjectContext,
    ProjectCompleteContext,
    TaskSuccessContext,
)
from memstack.preferences.registry import get_preference_backend

logger = logging.getLogger("memstack.facade")


def enabled() -> bool:
    return memstack_enabled()


def on_chat_turn(
    ctx: ChatTurnContext,
    provider: Optional[AgentMemoryProvider] = None,
) -> str:
    """H1 — 私聊/群聊回合：L1 retrieve + 偏好 inject。"""
    try:
        if not enabled():
            return ctx.message
        prov = provider or get_agent_memory_provider()
        hint = prov.before_turn(ctx.scope, ctx.message)
        effective = inject_memory_hints(ctx.message, hint)
        owner = (ctx.owner_id or ctx.scope.agent_id or "").strip()
        if owner:
            pref = get_preference_backend().format_block(owner, agent_id=ctx.scope.agent_id)
            if pref and pref not in effective:
                effective = f"{effective}\n\n---\n{pref}" if effective else pref
        return effective
    except Exception as e:
        logger.warning("on_chat_turn failed: %s", e)
        return ctx.message


def after_chat_turn(
    scope: MemoryScope,
    user_text: str,
    assistant_text: str,
    provider: Optional[AgentMemoryProvider] = None,
) -> None:
    try:
        prov = provider or get_agent_memory_provider()
        prov.after_turn(scope, user_text, assistant_text)
    except Exception as e:
        logger.warning("after_chat_turn failed: %s", e)


def inject_for_execute(ctx: ExecuteInjectContext) -> None:
    """H3 — 委托 execution_harness（执行质量层）。"""
    try:
        from execution_harness.context import ExecuteHarnessContext
        from execution_harness.facade import inject_for_execute as _harness_inject

        _harness_inject(
            ExecuteHarnessContext(
                lines=ctx.lines,
                project_id=ctx.project_id,
                task_type=ctx.task_type,
                agent_id=ctx.agent_id,
                owner_id=ctx.owner_id or "",
                limit=ctx.limit,
                store=ctx.store,
            )
        )
    except Exception as e:
        logger.warning("inject_for_execute failed: %s", e)


def on_task_success(ctx: TaskSuccessContext) -> Optional[str]:
    """H2 — 委托 execution_harness POST promote。"""
    try:
        from execution_harness.context import TaskCompleteContext
        from execution_harness.facade import on_task_complete

        return on_task_complete(
            TaskCompleteContext(
                base_dir=ctx.base_dir,
                project_id=ctx.project_id,
                task_id=ctx.task_id,
                task_type=ctx.task_type,
                store=ctx.store,
                agent_id=ctx.agent_id or "",
                gate_passed=ctx.gate_passed,
            ),
            port_run=None,
        )
    except Exception as e:
        logger.warning("on_task_success failed: %s", e)
        return None


def on_project_complete(ctx: ProjectCompleteContext) -> Optional[str]:
    """H4 — 项目完成复盘页写入 KB。"""
    try:
        if ctx.status != "completed":
            return None
        if not enabled():
            return None
        tasks = ctx.store.list_tasks(ctx.project_id)
        lines = [f"# 项目 {ctx.project_id} 复盘", ""]
        for t in tasks:
            tid = t.get("task_id") or t.get("id") or "?"
            tt = t.get("task_type") or "?"
            st = t.get("status") or "?"
            lines.append(f"- {tid} ({tt}): {st}")
        body = "\n".join(lines)
        kb = get_kb_backend(ctx.store)
        return kb.write(
            ctx.project_id,
            f"project_review:{ctx.project_id}",
            body,
            tags=["project_review"],
        )
    except Exception as e:
        logger.warning("on_project_complete failed: %s", e)
        return None


def on_consensus(ctx: ConsensusContext) -> Optional[str]:
    """H5 — 圆桌共识 best_practice → KB。"""
    try:
        if not enabled():
            return None
        text = (ctx.draft_text or "").strip()
        if not text:
            return None
        kb = get_kb_backend()
        project_id = ctx.project_id or f"group:{ctx.group_id}"
        title = f"consensus:{ctx.group_id}"
        return kb.write(
            project_id,
            title,
            text,
            tags=list(ctx.tags),
        )
    except Exception as e:
        logger.warning("on_consensus failed: %s", e)
        return None
