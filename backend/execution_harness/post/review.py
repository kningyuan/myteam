#!/usr/bin/env python3
"""POST — Background skill review（Hermes 语义 · CLI 适配）。"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Optional

from common.store import Store
from execution_harness.config import skill_review_enabled, skill_review_min_attempts
from execution_harness.context import SkillReviewContext, TaskCompleteContext
from execution_harness.post.pending import create_pending_bundle
from execution_harness.skill.umbrella import resolve_umbrella_skill

logger = logging.getLogger("execution_harness.post.review")

_SKILL_REVIEW_PROMPT_HEAD = """你正在执行一次「skill_review」后台复盘（不是用户任务，不影响交卷）。

请根据下方会话摘要，决定是否要把本次 execute 的教训写入 Skill 库：
1. 优先 patch 已有 umbrella skill（见 constraints.umbrella_skill）
2. 否则在 umbrella 下写 references/ 补充细节
3. 仅当完全无覆盖时才建议 create 新 class-level skill

输出要求：运行 submit_result，result 填写 action（patch|reference|create|noop）、skill_id、notes。
若 action 非 noop，在 notes 中给出可写入 SKILL.patch.md 的 Markdown 片段（Procedure/Pitfalls/Verification）。
"""


def should_trigger_review(ctx: TaskCompleteContext) -> bool:
    if not skill_review_enabled():
        return False
    if not ctx.gate_passed:
        return False
    if ctx.attempt >= skill_review_min_attempts():
        return True
    return ctx.status in ("completed", "needs_review")


def summarize_interaction(store: Store, interaction_id: str, *, max_events: int = 40) -> str:
    lines: list[str] = []
    try:
        events = store.list_run_events(interaction_id)
    except Exception:
        return "(无 run_events)"
    for ev in events[-max_events:]:
        kind = ev.get("kind") or "?"
        payload = ev.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"raw": payload[:200]}
        if not isinstance(payload, dict):
            payload = {}
        snippet = json.dumps(payload, ensure_ascii=False)[:300]
        lines.append(f"- [{kind}] {snippet}")
    return "\n".join(lines) if lines else "(无 run_events)"


def build_skill_review_request(ctx: TaskCompleteContext, store: Store) -> dict:
    iid = f"{ctx.project_id}:{ctx.task_id}:skill_review"
    umbrella = resolve_umbrella_skill(ctx.task_type) or ""
    summary = summarize_interaction(store, ctx.interaction_id or f"{ctx.project_id}:{ctx.task_id}:execute:{ctx.attempt}")
    intent = f"复盘任务 {ctx.task_id}（{ctx.task_type}）execute 过程，提取可复用 Skill 教训"
    return {
        "interaction_id": iid,
        "kind": "skill_review",
        "project_id": ctx.project_id,
        "task_id": ctx.task_id,
        "agent_id": ctx.agent_id,
        "intent": intent,
        "input": {
            "session_summary": summary,
            "execute_interaction_id": ctx.interaction_id,
            "attempt": ctx.attempt,
        },
        "context": {},
        "response_schema": "skill_review.result@1.0",
        "constraints": {
            "task_type": ctx.task_type,
            "umbrella_skill": umbrella,
        },
    }


def build_skill_review_prompt(req: dict) -> str:
    inp = req.get("input") or {}
    cons = req.get("constraints") or {}
    lines = [
        _SKILL_REVIEW_PROMPT_HEAD,
        f"interaction_id={req.get('interaction_id')}",
        f"umbrella_skill={cons.get('umbrella_skill') or '(无)'}",
        "",
        "【会话摘要】",
        inp.get("session_summary") or "",
        "",
        "【submit_result 结果 JSON 示例】",
        "{",
        f'  "interaction_id": "{req.get("interaction_id")}",',
        '  "kind": "skill_review", "status": "ok",',
        '  "result": {"action": "noop|patch|reference|create", "skill_id": "", "notes": "", "pending_content": ""},',
        '  "notes": "复盘摘要"',
        "}",
    ]
    return "\n".join(lines)


def record_review_from_response(ctx: TaskCompleteContext, resp: dict) -> Optional[str]:
    """解析 skill_review 响应并写 pending。"""
    result = resp.get("result") or {}
    action = (result.get("action") or "noop").strip().lower()
    if action in ("noop", "", "none"):
        return None
    skill_id = (result.get("skill_id") or resolve_umbrella_skill(ctx.task_type) or "").strip()
    notes = (result.get("notes") or resp.get("notes") or "").strip()
    content = (result.get("pending_content") or notes).strip()
    return create_pending_bundle(
        project_id=ctx.project_id,
        task_id=ctx.task_id,
        task_type=ctx.task_type,
        agent_id=ctx.agent_id,
        action=action,
        skill_id=skill_id,
        notes=notes,
        content=content,
    )


def schedule_skill_review(
    ctx: TaskCompleteContext,
    store: Store,
    port_run: Optional[Callable[[dict], Any]] = None,
    *,
    daemon: bool = True,
) -> bool:
    """异步或同步触发 skill_review。port_run 为 AgentPort.run 的可调用（接收 dict）。"""
    if not should_trigger_review(ctx):
        return False
    if port_run is None:
        return False

    def _worker() -> None:
        try:
            req = build_skill_review_request(ctx, store)
            res = port_run(req)
            resp = getattr(res, "response", None)
            if resp and isinstance(resp, dict):
                pid = record_review_from_response(ctx, resp)
                if pid:
                    store.append_run_event(
                        req["interaction_id"],
                        "skill_review_pending",
                        {"pending_id": pid},
                    )
        except Exception as e:
            logger.warning("skill_review failed: %s", e)

    if daemon:
        threading.Thread(target=_worker, daemon=True).start()
        return True
    _worker()
    return True
