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


def project_overview(store: Store, project_id: str) -> dict:
    """项目总览：状态 / DAG / 进度。"""
    proj = store.get_project(project_id) or {"project_id": project_id}
    tasks = store.list_tasks(project_id)
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    done = counts.get("completed", 0) + counts.get("needs_review", 0)
    total = len(tasks) or 1
    return {
        "project_id": project_id,
        "status": proj.get("status"),
        "mode": proj.get("mode"),
        "task_counts": counts,
        "progress": round(done / total, 3),
        "tasks": [{"id": t["task_id"], "status": t["status"], "agent": t["agent"],
                   "dependencies": t["dependencies"]} for t in tasks],
    }


def task_detail(store: Store, project_id: str, task_id: str) -> dict:
    """任务详情：当前 interaction / 重试 / outcome / 自评 / 存活态。"""
    task = store.get_task(project_id, task_id) or {}
    inters = [i for i in store.list_interactions(project_id) if i.get("task_id") == task_id]
    return {
        "task": {"id": task_id, "status": task.get("status"), "agent": task.get("agent"),
                 "meta": task.get("meta")},
        "interactions": [{
            "interaction_id": i["interaction_id"], "attempt": i["attempt"],
            "status": i["status"], "liveness": liveness(i),
            "tokens": i["tokens"], "response_ref": i["response_ref"],
        } for i in inters],
    }


def timeline(store: Store, interaction_id: str) -> list[dict]:
    """实时时间线（run_event 流）。"""
    return [{"seq": e["seq"], "kind": e["kind"], "payload": e["payload"], "ts": e["ts"]}
            for e in store.list_run_events(interaction_id)]


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
