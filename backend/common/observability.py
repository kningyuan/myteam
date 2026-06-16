#!/usr/bin/env python3
"""可观测 + Token 治理（D17）。

数据全来自 SQLite 真相库（D13）。本模块定义**只读 API 形状**（纯查询函数），
供 Hub 暴露为只读 HTTP + 复用现有 SSE 推 run_event（UI 视觉设计按 D9 推迟）。

- 项目总览 / 任务详情 / 实时时间线 / Agent 舰队状态 / 成本（token 累计）。
- 存活判定（D7）：按 last_event_at 推「执行中 / 空闲 / 卡死」。
- Token 治理：计量 → 预算（per-project 必备）→ 告警（默认 80%）→ 超限方案丙（暂停 + 上报）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from common.store import Store

# 存活判定阈值（与 AgentPort 看门狗对齐，D7）
SOFT_IDLE_SEC = 120.0
HARD_IDLE_SEC = 300.0


def _age_sec(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        t = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return None
    return max(0.0, time.time() - t)


def liveness(interaction: dict) -> str:
    """由 status + last_event_at 推存活态：running/idle/stuck/done/...（D7）。"""
    status = interaction.get("status")
    if status != "running":
        return status or "unknown"
    age = _age_sec(interaction.get("last_event_at"))
    if age is None:
        return "running"
    if age >= HARD_IDLE_SEC:
        return "stuck"
    if age >= SOFT_IDLE_SEC:
        return "idle"
    return "running"


def _budget_state(used: int, budget: Optional[int], alert_ratio: float = 0.8) -> tuple[Optional[float], str]:
    """(ratio, state)：ok / alert / over。budget 为空时 ratio=None、state=ok。"""
    if not budget:
        return None, "ok"
    ratio = round(used / budget, 3)
    if used >= budget:
        return ratio, "over"
    if ratio >= alert_ratio:
        return ratio, "alert"
    return ratio, "ok"


def _launch_config(proj: dict, meta: dict) -> dict:
    """从 project 行与 meta 组装发起时的配置快照（供概览展示）。"""
    from common.goal_template import parse_goal_template_id

    launch_meta = meta.get("launch") or {}
    goal = (meta.get("goal") or "").strip()
    workflow = (meta.get("workflow") or "").strip() or None
    mode = proj.get("mode") or "one_shot"
    mode_labels = {
        "one_shot": "one_shot（跑一次）",
        "recurring": "recurring（持续）",
    }
    if workflow:
        from common.workflow_loader import resolve_workflow_display_name

        workflow_label = resolve_workflow_display_name(workflow)
    else:
        workflow_label = "自由规划（main 即兴 task_plan）"
    return {
        "goal": goal or None,
        "workflow": workflow,
        "workflow_label": workflow_label,
        "mode": mode,
        "mode_label": mode_labels.get(mode, mode),
        "token_budget": meta.get("token_budget"),
        "template_id": parse_goal_template_id(goal),
        "review": bool(launch_meta.get("review")),
        "split": bool(launch_meta.get("split")),
        "max_cycles": launch_meta.get("max_cycles"),
        "backend": launch_meta.get("backend"),
    }


def project_overview(store: Store, project_id: str) -> dict:
    """项目总览：状态 / DAG / 进度 / 成本预算 / 发起配置。"""
    proj = store.get_project(project_id) or {"project_id": project_id}
    tasks = store.list_tasks(project_id)
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    done = counts.get("completed", 0) + counts.get("needs_review", 0)
    total = len(tasks) or 1
    used = store.tokens_total(project_id)
    meta = proj.get("meta") or {}
    budget = meta.get("token_budget")
    ratio, bstate = _budget_state(used, budget)
    return {
        "project_id": project_id,
        "title": proj.get("title") or project_id,  # 与 api-reference.md §11.1 + 前端 project.js 对齐；proj 兜底时退化为 pid
        "status": proj.get("status"),
        "mode": proj.get("mode"),
        "workflow": meta.get("workflow"),
        "launch_error": meta.get("launch_error"),
        "created_at": proj.get("created_at"),
        "updated_at": proj.get("updated_at"),
        "launch": _launch_config(proj, meta),
        "task_counts": counts,
        "progress": round(done / total, 3),
        "tokens": used,
        "budget": budget,
        "budget_ratio": ratio,
        "budget_state": bstate,
        "tasks": [{"id": t["task_id"], "name": t.get("name", ""), "status": t["status"],
                   "agent": t["agent"], "dependencies": t["dependencies"],
                   "summary": (t.get("meta") or {}).get("summary", "")} for t in tasks],
        "iterations": _build_iterations(store, project_id),
    }


def projects_summary(store: Store) -> dict:
    """全局总览（Dashboard 用）：每个项目的状态/进度/成本/预算 + 全局总计。"""
    running = {"in_progress", "running", "pending"}
    items = []
    total_tokens = 0
    n_running = 0
    for p in store.list_projects():
        pid = p["project_id"]
        tasks = store.list_tasks(pid)
        done = sum(1 for t in tasks if t["status"] in ("completed", "needs_review"))
        progress = round(done / (len(tasks) or 1), 3)
        used = store.tokens_total(pid)
        total_tokens += used
        status = p.get("status") or "unknown"
        if status in running:
            n_running += 1
        budget = (p.get("meta") or {}).get("token_budget")
        ratio, bstate = _budget_state(used, budget)
        items.append({
            "id": pid, "title": p.get("title") or pid, "status": status,
            "mode": p.get("mode"), "progress": progress, "task_count": len(tasks),
            "tokens": used, "budget": budget, "budget_ratio": ratio,
            "budget_state": bstate, "updated_at": p.get("updated_at"),
        })
    return {
        "projects": items,
        "totals": {"projects": len(items), "running": n_running,
                   "tokens": total_tokens},
    }


def _summarize_interaction_events(store: Store, interaction_id: str, *, kind: str) -> dict:
    """从 run_event 提取门禁失败、评审结论、自评（execute response_snapshot）。"""
    gate_failures: list = []
    review = None
    quality = None
    for e in store.list_run_events(interaction_id):
        payload = e.get("payload") or {}
        if e["kind"] == "gate_failed":
            gate_failures = payload.get("failures") or []
        elif e["kind"] == "review_done":
            review = payload
        elif e["kind"] == "response_snapshot" and kind == "execute":
            resp = payload.get("response") or {}
            if isinstance(resp, dict):
                q = resp.get("quality")
                if isinstance(q, dict):
                    quality = q
    out: dict = {"gate_failures": gate_failures}
    if review is not None:
        out["review"] = review
    if quality is not None:
        out["quality"] = quality
    return out


def task_detail(store: Store, project_id: str, task_id: str) -> dict:
    """任务详情：当前 interaction / 重试 / outcome / 自评 / 存活态。"""
    task = store.get_task(project_id, task_id) or {}
    inters = [i for i in store.list_interactions(project_id) if i.get("task_id") == task_id]
    interactions = []
    latest_quality = None
    for i in inters:
        kind = i.get("kind") or ""
        summary = _summarize_interaction_events(store, i["interaction_id"], kind=kind)
        if kind == "execute" and summary.get("quality"):
            latest_quality = summary["quality"]
        interactions.append({
            "interaction_id": i["interaction_id"],
            "kind": kind,
            "attempt": i["attempt"],
            "status": i["status"],
            "liveness": liveness(i),
            "tokens": i["tokens"],
            "response_ref": i["response_ref"],
            **summary,
        })
    meta = task.get("meta") or {}
    return {
        "task": {
            "id": task_id,
            "name": task.get("name"),
            "status": task.get("status"),
            "agent": task.get("agent"),
            "reviewer": task.get("reviewer"),
            "task_type": task.get("task_type"),
            "meta": meta,
            "fail_reason": meta.get("fail_reason"),
            "fail_detail": meta.get("fail_detail"),
            "summary": meta.get("summary"),
            "ref": meta.get("ref"),
        },
        "latest_quality": latest_quality,
        "interactions": interactions,
    }


def timeline(store: Store, interaction_id: str) -> list[dict]:
    """实时时间线（run_event 流）。"""
    return [{"seq": e["seq"], "kind": e["kind"], "payload": e["payload"], "ts": e["ts"]}
            for e in store.list_run_events(interaction_id)]


# 项目事件流里要呈现的「里程碑」事件（过滤掉 text/step_start 等低层噪声）
_FEED_KINDS = {
    "plan_rejected", "gate_passed", "gate_failed",
    "review_done", "review_unreachable",
    "blocked", "budget_alert", "budget_over", "budget_degrade", "budget_exceeded",
    "budget_exceeded_pause", "cycle_done",
    "loop_round_done", "loop_finished", "loop_round_assess", "loop_transition", "branch_selected",
    "watchdog_soft_idle", "watchdog_hard_kill", "transport_error",
    "reconcile_timed_out", "reconcile_adopted",
    "tool_use", "tool_result", "prompt_sent", "request_snapshot", "response_snapshot",
    "message", "parallel_wave",
}


def _build_iterations(store: Store, project_id: str) -> list[dict]:
    """从 loop 占位 task meta 与 run_event 聚合 iterations[]。"""
    iterations: list[dict] = []
    for t in store.list_tasks(project_id):
        meta = t.get("meta") or {}
        loop_id = str(meta.get("loop") or "").strip()
        if not loop_id:
            continue
        placeholder_id = t["task_id"]
        iid = f"{project_id}:loop:{loop_id}"
        rounds_done: list[dict] = []
        finished: Optional[dict] = None
        last_assess: Optional[dict] = None
        for e in store.list_run_events(iid):
            kind = e.get("kind")
            payload = e.get("payload") or {}
            if kind == "loop_round_done":
                rounds_done.append(payload)
            elif kind == "loop_finished":
                finished = payload
            elif kind == "loop_round_assess":
                last_assess = payload
        current_round = 0
        body_key = "default"
        if rounds_done:
            last = rounds_done[-1]
            current_round = int(last.get("round") or 0)
            body_key = str(last.get("body_key") or "default")
        elif last_assess:
            current_round = int(last_assess.get("round") or 0)
            body_key = str(last_assess.get("body_key") or "default")
        rounds_used = int((finished or {}).get("rounds_used") or current_round or 0)
        state = "running"
        if finished:
            fs = str(finished.get("state") or "")
            if fs == "passed":
                state = "passed"
            elif fs == "exhausted":
                state = "exhausted"
            else:
                state = fs or "finished"
        elif t.get("status") in ("completed", "needs_review"):
            state = "passed" if t.get("status") == "completed" else "needs_review"
        last_assess_marker = meta.get("last_assess_marker")
        if last_assess:
            last_assess_marker = (
                last_assess.get("marker")
                or meta.get("last_assess_marker")
            )
        iterations.append({
            "loop_id": loop_id,
            "placeholder_task_id": placeholder_id,
            "state": state,
            "current_round": current_round,
            "max_rounds": meta.get("loop_max_rounds"),
            "body_key": body_key,
            "last_assess_marker": last_assess_marker,
            "last_assess_action": (last_assess or {}).get("action"),
            "last_assess_matched_rule": (last_assess or {}).get("matched_rule"),
            "rounds_used": rounds_used,
            "placeholder_status": t.get("status"),
        })
    return iterations


def project_events(store: Store, project_id: str) -> list[dict]:
    """项目执行过程事件流（一条时间线）。

    = 交互生命周期骨架（每个 interaction 一条：谁/什么任务/什么交互 → 状态）
    + 里程碑事件（门禁 / 评审 / skill 调用 / 阻塞 / 预算 / 看门狗 / 消息）。
    低层 cli 噪声（text/step_*/session）不进项目级流，留给单交互钻取。
    """
    feed: list[dict] = []
    for i in store.list_interactions(project_id):
        feed.append({
            "ts": i.get("started_at") or "",
            "category": "interaction",
            "kind": i.get("kind") or "",
            "agent_id": i.get("agent_id") or "",
            "task_id": i.get("task_id") or "",
            "interaction_id": i.get("interaction_id"),
            "status": i.get("status"),
            "attempt": i.get("attempt"),
            "tokens": i.get("tokens"),
        })
    for e in store.list_project_events(project_id):
        if e["kind"] not in _FEED_KINDS:
            continue
        feed.append({
            "ts": e["ts"], "category": "event", "kind": e["kind"],
            "agent_id": e["agent_id"], "task_id": e["task_id"],
            "interaction_id": e["interaction_id"], "payload": e["payload"],
        })
    feed.sort(key=lambda x: (x.get("ts") or "", x.get("category") == "event"))
    return feed


def fleet_status(store: Store, project_id: str) -> dict[str, str]:
    """Agent 舰队状态（派生）：每个 agent 取其最新 interaction 的存活态。"""
    latest: dict[str, dict] = {}
    for i in store.list_interactions(project_id):
        aid = i.get("agent_id") or ""
        if not aid:
            continue
        if aid not in latest or (i.get("started_at") or "") >= (latest[aid].get("started_at") or ""):
            latest[aid] = i
    return {aid: liveness(i) for aid, i in latest.items()}


def cost(store: Store, project_id: str) -> dict:
    """成本：token 累计 per project / agent / task（D17 计量）。"""
    return {
        "project": store.tokens_total(project_id),
        "by_agent": store.tokens_grouped(project_id, "agent_id"),
        "by_task": store.tokens_grouped(project_id, "task_id"),
    }


# ── Token 预算治理（方案丙）─────────────────────────────────


@dataclass
class BudgetConfig:
    project_limit: Optional[int] = None   # per-project token 硬上限（必备粒度，D17）
    alert_ratio: float = 0.8              # 过阈值告警（默认 80%）


@dataclass
class BudgetState:
    used: int
    limit: Optional[int]
    ratio: Optional[float]
    state: str                            # ok | alert | over


def check_budget(store: Store, project_id: str, config: BudgetConfig) -> BudgetState:
    """检查项目 token 预算。over = 到硬上限（方案丙：调用方暂停项目 + 上报）。"""
    used = store.tokens_total(project_id)
    if not config.project_limit:
        return BudgetState(used, None, None, "ok")
    ratio = used / config.project_limit
    if used >= config.project_limit:
        state = "over"
    elif ratio >= config.alert_ratio:
        state = "alert"
    else:
        state = "ok"
    return BudgetState(used, config.project_limit, round(ratio, 3), state)
