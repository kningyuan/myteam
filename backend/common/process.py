#!/usr/bin/env python3
"""Process — 声明式「Step + Gate」单内核（D10 / D18）。

合并 task-executor 与 continuous-executor 为**单一内核 + 模式配置**（one_shot / recurring），
不再两套引擎。内核串行驱动 DAG（D12），每一步经 AgentPort 投递统一 Interaction（D11），
框架用确定性 Gate（D14）判格式/完整性，质量交 Agent（自评 + 评审）。

失败语义（D18）：
  - failed（客观失败，阻塞）：确定性门禁重试耗尽 / 端口看门狗终态 → 任务 failed，依赖者 blocked。
  - needs_review（质量未确认，默认不阻塞）：自评偏低 / known_gaps 非空（可配为阻塞）。
  - 升级阶梯：可重试失败 → 自动重试有限次 → 耗尽 failed → 委托 Main `kind=triage` 决策。
  - 项目级：全 completed 才 completed；有不可恢复 failed → partially_failed / failed 显式暴露。

本内核与 backend/skill 解耦：通过注入 AgentPort（其 Transport 可换 opencode/claude）驱动，
便于单测（fake transport）与 live 切换。
"""
from __future__ import annotations

import logging
from typing import Optional

from common.agent_port import AgentPort
from common.dag_dispatch import deps_block, derive_project_status
from common.decision_pipeline import DecisionPipeline
from common.plan_expansion import PlanExpander
from common.plan_gate import check_plan, prefix_cycle, topological_order
from common.process_types import (
    TERMINAL_BAD,
    TERMINAL_OK,
    ProcessConfig,
    ProjectOutcome,
    TaskOutcome,
)
from common.task_pipeline import TaskPipeline
from common.workspace_gc import gc_project_workspace, remove_interaction_files
from common.observability import BudgetConfig, check_budget
from common.store import Store

# 向后兼容 re-export
from common.agent_bootstrap import _auto_create_agent  # noqa: F401
from common.plan_gate import PlanCheckResult  # noqa: F401


class Process:
    def __init__(self, store: Store, port: AgentPort, config: Optional[ProcessConfig] = None):
        self.store = store
        self.port = port
        self.config = config or ProcessConfig()
        release = self._release_interaction_files
        self._pipeline = TaskPipeline(
            store=self.store, port=self.port, config=self.config, release_files=release,
        )
        self._decisions = DecisionPipeline(
            store=self.store, port=self.port, config=self.config, release_files=release,
        )
        self._expander = PlanExpander(
            decision=self._decisions, store=self.store, config=self.config,
        )

    def _release_interaction_files(self, agent_id: str, interaction_id: str) -> None:
        remove_interaction_files(agent_id, interaction_id)

    # ── 入口 ─────────────────────────────────────────────────

    def run(self, project_id: str, *, title: str = "", goal: str = "",
            agents: Optional[list[str]] = None,
            tasks: Optional[list[dict]] = None,
            workflow: Optional[str] = None) -> ProjectOutcome:
        """跑一个项目。

        若给定 agents/tasks 则直接用（便于测试与已规划场景）；否则走 team_config / task_plan
        两个 Interaction 由 Main 决策（live 路径）。
        """
        proj_meta: dict = {"token_budget": self.config.token_budget, "goal": goal}
        if workflow:
            proj_meta["workflow"] = workflow
        self.store.upsert_project(project_id, title=title, mode=self.config.mode,
                                  status="in_progress", meta=proj_meta)
        logging.info("▶ 启动项目：%s", project_id)
        if agents is None:
            agents = self._decisions.team_config(project_id, goal)
            logging.info("  agent 名册：%s", ", ".join(agents))
        if self.config.mode == "recurring" and tasks is None:
            return self._run_recurring(project_id, goal, agents)
        if tasks is None:
            tasks = self._decisions.task_plan(project_id, goal, agents)
            if self.config.split_enabled:
                tasks = self._expander.expand(project_id, tasks, agents)
        check = check_plan(tasks, set(agents))
        if not check.passed:
            raise RuntimeError(f"plan gate 校验失败（{project_id}）：{check.feedback}")
        self._persist_tasks(project_id, tasks)
        logging.info("  任务数：%s", len(tasks))
        return self._dispatch(project_id, tasks)

    def resume(self, project_id: str) -> ProjectOutcome:
        """断点续跑（D8）：回收孤儿响应、结算卡住任务、继续 DAG。不重跑 team_config/task_plan。"""
        proj = self.store.get_project(project_id)
        if not proj:
            raise RuntimeError(f"项目不存在：{project_id}")
        if proj.get("status") not in ("in_progress", "paused"):
            return ProjectOutcome(project_id, proj["status"], {})

        tasks = self._tasks_from_store(project_id)
        if not tasks:
            raise RuntimeError(f"项目无任务：{project_id}")

        outcomes: dict[str, TaskOutcome] = {}
        for task in tasks:
            tid = task["id"]
            row = self.store.get_task(project_id, tid) or {}
            st = row.get("status", "pending")
            if st in TERMINAL_OK | TERMINAL_BAD | {"blocked"}:
                outcomes[tid] = TaskOutcome(tid, st)
                continue
            if st == "in_progress":
                settled = self._pipeline.settle_in_progress_task(project_id, task)
                if settled:
                    outcomes[tid] = settled

        return self._dispatch(project_id, tasks, initial_outcomes=outcomes)

    def _tasks_from_store(self, project_id: str) -> list[dict]:
        return [{
            "id": r["task_id"],
            "name": r.get("name", ""),
            "agent": r.get("agent", ""),
            "reviewer": r.get("reviewer", ""),
            "task_type": r.get("task_type", ""),
            "dependencies": r.get("dependencies") or [],
            "description": (r.get("meta") or {}).get("description", ""),
        } for r in self.store.list_tasks(project_id)]

    def _persist_tasks(self, project_id: str, tasks: list[dict]) -> None:
        for t in tasks:
            self.store.upsert_task(
                project_id, t["id"], name=t.get("name", ""), agent=t.get("agent", ""),
                reviewer=t.get("reviewer", ""), task_type=t.get("task_type", ""),
                dependencies=t.get("dependencies", []), status="pending",
            )

    # ── recurring：周期循环 + 轮次继承（D10）────────────────────

    def _run_recurring(self, project_id: str, goal: str, agents: list[str]) -> ProjectOutcome:
        overall: dict[str, TaskOutcome] = {}
        prior_summary = ""
        stop_status: Optional[str] = None
        for cycle in range(1, max(1, self.config.max_cycles) + 1):
            if self._is_cancelled(project_id):
                stop_status = "cancelled"
                break
            planned = self._decisions.task_plan(project_id, goal, agents,
                                                cycle=cycle, prior_summary=prior_summary)
            if self.config.split_enabled:
                planned = self._expander.expand(project_id, planned, agents, cycle=cycle)
            tasks = prefix_cycle(planned, cycle)
            self._persist_tasks(project_id, tasks)
            outcome = self._dispatch(project_id, tasks, persist=False)
            overall.update(outcome.tasks)
            prior_summary = self._cycle_summary(project_id, tasks)
            self.store.memory_write(project_id, f"周期 {cycle} 滚动摘要", prior_summary,
                                    tags=["cycle_summary"])
            self.store.append_run_event(f"{project_id}:cycle:{cycle}", "cycle_done",
                                        {"status": outcome.status})
            if outcome.status in ("cancelled", "aborted", "paused"):
                stop_status = outcome.status
                break
            if not any(o.status in TERMINAL_OK for o in outcome.tasks.values()):
                stop_status = "failed"
                break
        final = stop_status or "completed"
        self.store.set_project_status(project_id, final)
        return ProjectOutcome(project_id, final, overall)

    def _cycle_summary(self, project_id: str, tasks: list[dict]) -> str:
        parts: list[str] = []
        for t in tasks:
            row = self.store.get_task(project_id, t["id"]) or {}
            summary = (row.get("meta") or {}).get("summary")
            if summary:
                parts.append(f"- {row.get('name') or t['id']}: {summary}")
        return "\n".join(parts) or "（本周期无可用摘要）"

    # ── 进度输出 ──────────────────────────────────────────

    def _print_progress(self, project_id: str, outcomes: dict[str, TaskOutcome],
                        total: int) -> None:
        done = sum(1 for o in outcomes.values() if o.status in TERMINAL_OK | TERMINAL_BAD | {"blocked"})
        pct = int(done / total * 100) if total else 0
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\n  ╔══ 项目进度  {bar}  {done}/{total} ══╗")
        last = list(outcomes.items())[-1:] if outcomes else []
        for tid, o in last:
            name = self.store.get_task(project_id, tid) or {}
            label = name.get("name", "") or tid
            icon = "✔" if o.status == "completed" else "✖" if o.status in ("failed", "blocked") else "○"
            extra = f" — {o.reason}" if o.reason else ""
            print(f"  {icon} {label} → {o.status}{extra}")

    # ── DAG 调度（串行，D12）──────────────────────────────────

    def _dispatch(self, project_id: str, tasks: list[dict],
                  *, persist: bool = True,
                  initial_outcomes: Optional[dict[str, TaskOutcome]] = None) -> ProjectOutcome:
        by_id = {t["id"]: t for t in tasks}
        order = topological_order(tasks)
        outcomes: dict[str, TaskOutcome] = dict(initial_outcomes or {})
        aborted = False
        paused = False
        cancelled = False

        for tid in order:
            if tid in outcomes:
                continue
            if not (cancelled or aborted or paused) and self._is_cancelled(project_id):
                cancelled = True
            if cancelled or aborted or paused:
                reason = ("项目已取消" if cancelled else
                          "项目已中止" if aborted else "项目已暂停（token 超预算）")
                outcomes[tid] = self._block(project_id, tid, reason)
                continue
            if self._over_budget(project_id):
                paused = True
                outcomes[tid] = self._block(project_id, tid, "项目已暂停（token 超预算）")
                continue
            task = by_id[tid]
            dep_block = deps_block(task, outcomes,
                                   needs_review_blocks=self.config.needs_review_blocks)
            if dep_block:
                outcomes[tid] = self._block(project_id, tid, dep_block)
                continue

            outcome = self._pipeline.run_task(project_id, task)
            if outcome.status == "failed":
                decision = self._decisions.triage(project_id, task, outcome.reason)
                if decision == "retry":
                    outcome = self._pipeline.run_task(project_id, task)
                elif decision == "reassign":
                    outcome = self._pipeline.run_task(project_id, task)
                elif decision == "abort":
                    aborted = True
            outcomes[tid] = outcome
            self._print_progress(project_id, outcomes, len(order))

        proj_status = self._finalize(project_id, outcomes, aborted, paused, cancelled,
                                     persist=persist)
        return ProjectOutcome(project_id, proj_status, outcomes)

    def _is_cancelled(self, project_id: str) -> bool:
        p = self.store.get_project(project_id)
        return bool(p and p.get("status") == "cancelled")

    def _over_budget(self, project_id: str) -> bool:
        if not self.config.token_budget:
            return False
        bs = check_budget(self.store, project_id,
                          BudgetConfig(self.config.token_budget, self.config.budget_alert_ratio))
        if bs.state == "over":
            self.store.append_run_event(f"{project_id}:budget", "budget_over",
                                        {"used": bs.used, "limit": bs.limit})
            return True
        if bs.state == "alert":
            self.store.append_run_event(f"{project_id}:budget", "budget_alert",
                                        {"used": bs.used, "limit": bs.limit, "ratio": bs.ratio})
        return False

    # ── 收尾 ─────────────────────────────────────────────────

    def _block(self, project_id: str, tid: str, reason: str) -> TaskOutcome:
        self.store.set_task_status(project_id, tid, "blocked")
        self.store.append_run_event(f"{project_id}:{tid}:blocked", "blocked", {"reason": reason})
        return TaskOutcome(tid, "blocked", reason)

    def _finalize(self, project_id: str, outcomes: dict[str, TaskOutcome],
                  aborted: bool, paused: bool = False, cancelled: bool = False,
                  persist: bool = True) -> str:
        status = derive_project_status(outcomes, aborted=aborted, paused=paused,
                                       cancelled=cancelled)
        if persist:
            self.store.set_project_status(project_id, status)
            gc_project_workspace(self.store, project_id)
        return status
