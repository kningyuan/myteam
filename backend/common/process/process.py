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

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import common.paths as paths

from common.agent.agent_port import AgentPort
from common.process.dag_dispatch import deps_block, derive_project_status, ready_tasks
from common.process.decision_pipeline import DecisionPipeline
from common.loop.loop_runtime import (
    LoopSpec,
    RunLoopDeps,
    run_loop,
)
from common.process.plan_expansion import PlanExpander
from common.process.plan_gate import check_plan, prefix_cycle, topological_order
from common.process.process_types import (
    TERMINAL_BAD,
    TERMINAL_OK,
    BudgetExceededError,
    ProcessConfig,
    ProjectOutcome,
    TaskExecuteResult,
    TaskOutcome,
)
from common.process.task_pipeline import TaskPipeline
from common.runtime.workspace_gc import gc_project_workspace, remove_interaction_files
from common.observability.observability import BudgetConfig, check_budget
from common.project.project_artifacts import artifact_rel_path, task_deliverable_base
from common.project.project_hooks import ProjectHooks
from common.store.store import Store

# 向后兼容 re-export
from common.agent.agent_bootstrap import _auto_create_agent  # noqa: F401
from common.process.plan_gate import PlanCheckResult  # noqa: F401


class Process:
    def __init__(self, store: Store, port: AgentPort, config: Optional[ProcessConfig] = None,
                 hooks: Optional[ProjectHooks] = None):
        self.store = store
        self.port = port
        self.config = config or ProcessConfig()
        self._hooks = hooks
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
        self._loops_by_id: dict[str, LoopSpec] = {}

    def _release_interaction_files(self, agent_id: str, interaction_id: str) -> None:
        remove_interaction_files(agent_id, interaction_id)

    # ── 入口 ─────────────────────────────────────────────────

    def run(self, project_id: str, *, title: str = "", goal: str = "",
            agents: Optional[list[str]] = None,
            tasks: Optional[list[dict]] = None,
            workflow: Optional[str] = None,
            loops: Optional[list[LoopSpec]] = None) -> ProjectOutcome:
        """跑一个项目。

        若给定 agents/tasks 则直接用（便于测试与已规划场景）；否则走 team_config / task_plan
        两个 Interaction 由 Main 决策（live 路径）。
        """
        self._loops_by_id = {spec.id: spec for spec in (loops or [])}
        try:
            return self._run_impl(
                project_id, title=title, goal=goal, agents=agents, tasks=tasks, workflow=workflow,
            )
        except BudgetExceededError as e:
            self.store.set_project_status(project_id, "paused")
            self.store.append_run_event(f"{project_id}:budget", "budget_exceeded_pause",
                                        {"reason": str(e)})
            gc_project_workspace(self.store, project_id)
            return ProjectOutcome(project_id, "paused", {})

    def _run_impl(self, project_id: str, *, title: str = "", goal: str = "",
                  agents: Optional[list[str]] = None,
                  tasks: Optional[list[dict]] = None,
                  workflow: Optional[str] = None) -> ProjectOutcome:
        existing = self.store.get_project(project_id) or {}
        existing_meta = dict(existing.get("meta") or {})
        proj_meta = {**existing_meta, "token_budget": self.config.token_budget, "goal": goal}
        if workflow:
            proj_meta["workflow"] = workflow
        launch = dict(existing_meta.get("launch") or {})
        if self.config.review_enabled:
            launch["review"] = True
        if self.config.split_enabled:
            launch["split"] = True
        if self.config.default_backend:
            launch["backend"] = self.config.default_backend
        if launch:
            proj_meta["launch"] = launch
        self.store.upsert_project(project_id, title=title, mode=self.config.mode,
                                  status="in_progress", meta=proj_meta)
        logging.info("▶ 启动项目：%s", project_id)
        if agents is None:
            agents = self._decisions.team_config(project_id, goal)
            logging.info("  agent 名册：%s", ", ".join(agents))
            if paused := self._pause_if_over_budget(project_id):
                return paused
        self._fire_team_ready(project_id, agents, title)
        # 升级：workflow 模式也支持 recurring — 每轮用 workflow 实例化 tasks
        if self.config.mode == "recurring":
            if tasks is not None:
                # workflow 模式 recurring：用 instantiate_tasks 每轮重新生成
                return self._run_recurring_with_workflow(project_id, goal, agents, tasks)
            return self._run_recurring(project_id, goal, agents)
        if tasks is None:
            tasks = self._decisions.task_plan(project_id, goal, agents)
        if self.config.split_enabled:
            tasks = self._expander.expand(project_id, tasks, agents)
        if paused := self._pause_if_over_budget(project_id):
            return paused
        check = check_plan([t for t in tasks if not t.get("loop")], set(agents))
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
        # paused 恢复时显式改回 in_progress，让 UI 立即反映"已恢复"
        if proj.get("status") == "paused":
            self.store.set_project_status(project_id, "in_progress")

        tasks = self._tasks_from_store(project_id)
        if not tasks:
            raise RuntimeError(f"项目无任务：{project_id}")
        wf = (proj.get("meta") or {}).get("workflow")
        if wf:
            from common.workflow.workflow_loader import load_workflow
            profile = load_workflow(wf)
            self._loops_by_id = {spec.id: spec for spec in profile.loops}
            tasks = self._merge_workflow_descriptions(wf, tasks)

        store_outcomes = {
            t["id"]: TaskOutcome(t["id"], (self.store.get_task(project_id, t["id"]) or {}).get("status", "pending"))
            for t in tasks
        }
        outcomes: dict[str, TaskOutcome] = {}
        for task in tasks:
            tid = task["id"]
            row = self.store.get_task(project_id, tid) or {}
            st = row.get("status", "pending")
            if st == "blocked":
                reason = deps_block(
                    task, store_outcomes, needs_review_blocks=self.config.needs_review_blocks,
                )
                if not reason:
                    self.store.set_task_status(project_id, tid, "pending")
                    continue
                outcomes[tid] = TaskOutcome(tid, "blocked", reason)
                continue
            if st in TERMINAL_OK | TERMINAL_BAD:
                outcomes[tid] = TaskOutcome(tid, st)
                continue
            if st == "in_progress":
                settled = self._pipeline.settle_in_progress_task(project_id, task)
                if settled:
                    outcomes[tid] = settled

        try:
            return self._dispatch(project_id, tasks, initial_outcomes=outcomes)
        except BudgetExceededError as e:
            self.store.set_project_status(project_id, "paused")
            self.store.append_run_event(f"{project_id}:budget", "budget_exceeded_pause",
                                        {"reason": str(e)})
            gc_project_workspace(self.store, project_id)
            return ProjectOutcome(project_id, "paused", outcomes)

    def _tasks_from_store(self, project_id: str) -> list[dict]:
        out: list[dict] = []
        for r in self.store.list_tasks(project_id):
            meta = r.get("meta") or {}
            row = {
                "id": r["task_id"],
                "name": r.get("name", ""),
                "agent": r.get("agent", ""),
                "reviewer": r.get("reviewer", ""),
                "task_type": r.get("task_type", ""),
                "dependencies": r.get("dependencies") or [],
                "description": meta.get("description", ""),
            }
            if meta.get("loop"):
                row["loop"] = meta["loop"]
            out.append(row)
        return out

    def _merge_workflow_descriptions(self, workflow_id: str, tasks: list[dict]) -> list[dict]:
        """resume 时从 workflow 补全 store 中缺失的 task description（intent 来源）。"""
        from common.workflow.workflow_loader import load_workflow
        desc_by_id = {
            t["id"]: t.get("description", "")
            for t in load_workflow(workflow_id).instantiate_tasks()
        }
        merged = []
        for t in tasks:
            row = dict(t)
            if not row.get("description"):
                row["description"] = desc_by_id.get(row["id"], "")
            merged.append(row)
        return merged

    def _persist_tasks(self, project_id: str, tasks: list[dict]) -> None:
        for t in tasks:
            desc = t.get("description", "")
            existing = self.store.get_task(project_id, t["id"]) or {}
            meta: dict = dict(existing.get("meta") or {})
            if desc:
                meta["description"] = desc
            if t.get("loop"):
                meta["loop"] = t["loop"]
            if t.get("split_depth") is not None:
                meta["split_depth"] = t["split_depth"]
            self.store.upsert_task(
                project_id, t["id"], name=t.get("name", ""), agent=t.get("agent", ""),
                reviewer=t.get("reviewer", ""), task_type=t.get("task_type", ""),
                dependencies=t.get("dependencies", []), status="pending",
                meta=meta or None,
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
            if self._over_budget(project_id):
                stop_status = "paused"
                break
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
        if final == "completed":
            self._maybe_extract_skills(project_id)
        return ProjectOutcome(project_id, final, overall)

    def _run_recurring_with_workflow(self, project_id: str, goal: str,
                                     agents: list[str],
                                     base_tasks: list[dict]) -> ProjectOutcome:
        """workflow 模式的周期循环：每轮用 workflow 实例化 tasks（注入 prior_summary）。"""
        overall: dict[str, TaskOutcome] = {}
        prior_summary = ""
        stop_status: Optional[str] = None
        from common.process.plan_expansion import prefix_cycle
        for cycle in range(1, max(1, self.config.max_cycles) + 1):
            if self._is_cancelled(project_id):
                stop_status = "cancelled"
                break
            # 每轮重新实例化 workflow tasks（保持 goal 前缀）
            tasks = [dict(t) for t in base_tasks]
            if prior_summary:
                # 注入上一轮摘要到每个 task 的 description
                for t in tasks:
                    desc = t.get("description", "")
                    if desc:
                        t["description"] = f"【上一轮摘要】{prior_summary[:500]}\n\n{desc}"
            if self.config.split_enabled:
                tasks = self._expander.expand(project_id, tasks, agents, cycle=cycle)
            if self._over_budget(project_id):
                stop_status = "paused"
                break
            tasks = prefix_cycle(tasks, cycle)
            self._persist_tasks(project_id, tasks)
            outcome = self._dispatch(project_id, tasks, persist=False)
            overall.update(outcome.tasks)
            prior_summary = self._cycle_summary(project_id, tasks)
            self.store.memory_write(project_id, f"周期 {cycle} 滚动摘要", prior_summary,
                                    tags=["cycle_summary"])
            self.store.append_run_event(f"{project_id}:cycle:{cycle}", "cycle_done",
                                        {"status": outcome.status, "mode": "workflow_recurring"})
            if outcome.status in ("cancelled", "aborted", "paused"):
                stop_status = outcome.status
                break
            if not any(o.status in TERMINAL_OK for o in outcome.tasks.values()):
                stop_status = "failed"
                break
        final = stop_status or "completed"
        self.store.set_project_status(project_id, final)
        if final == "completed":
            self._maybe_extract_skills(project_id)
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

    # ── DAG 调度（波次；L2 可选真并行）────────────────────────

    def _agents_from_tasks(self, by_id: dict[str, dict]) -> list[str]:
        return sorted({t.get("agent", "") for t in by_id.values() if t.get("agent")})

    def _inject_upstream_context(self, project_id: str, task: dict) -> dict:
        """升级：跨任务数据传递 — 将上游交付物摘要注入 task description。

        自动读取 dependencies 中已完成任务的交付物，截取前 800 字作为上下文。
        task 可通过 ``task_inputs`` 字段指定哪些上游的交付物需要注入及截取长度：
        ``task_inputs: [{task: "t1", max_chars: 1000}, ...]``
        未指定 task_inputs 时，自动注入全部依赖的交付物摘要。
        """
        deps = task.get("dependencies") or []
        if not deps:
            return task
        task_inputs = task.get("task_inputs") or []
        # 构建上游交付物摘要
        upstream_parts: list[str] = []
        for dep_id in deps:
            # 查找 task_inputs 中的配置
            config = next((ti for ti in task_inputs if ti.get("task") == dep_id), {})
            max_chars = config.get("max_chars", 800)
            dep_task = self.store.get_task(project_id, dep_id) or {}
            dep_type = dep_task.get("task_type", "")
            if not dep_type:
                continue
            from common.project.project_artifacts import task_deliverable_base, artifact_rel_path
            base_dir = task_deliverable_base(project_id, dep_id, dep_type)
            rel = artifact_rel_path(dep_id, dep_type)
            dv_path = base_dir / rel
            if not dv_path.exists():
                continue
            try:
                content = dv_path.read_text(encoding="utf-8")
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n...(截断)"
                upstream_parts.append(f"【上游任务 {dep_id} 交付物摘要】\n{content}")
            except Exception:
                pass
        if not upstream_parts:
            return task
        desc = task.get("description", "")
        task = dict(task)  # 不修改原 dict
        task["description"] = "\n\n".join(upstream_parts) + f"\n\n{desc}" if desc else "\n\n".join(upstream_parts)
        return task

    def _execute_task(self, project_id: str, task: dict) -> TaskExecuteResult:
        """跑单任务；失败时 triage。返回 outcome + triage 决策 + 可选拆分子任务。"""
        # 升级：跨任务数据传递 — 注入上游交付物摘要到 description
        task = self._inject_upstream_context(project_id, task)
        outcome = self._pipeline.run_task(project_id, task)
        if outcome.status != "failed":
            self._notify_task_done(project_id, task, outcome)
            return TaskExecuteResult(outcome)
        meta = (self.store.get_task(project_id, task["id"]) or {}).get("meta") or {}
        triage = self._decisions.triage(project_id, task, outcome.reason)
        decision = triage.decision
        if decision == "split" and triage.sub_tasks:
            self.store.append_run_event(
                f"{project_id}:{task['id']}:triage", "triage_split",
                {"children": [s["id"] for s in triage.sub_tasks]},
            )
            return TaskExecuteResult(outcome, decision, triage.sub_tasks)
        if decision == "retry" and meta.get("fail_reason") == "gate_exhausted":
            self._notify_task_done(project_id, task, outcome)
            return TaskExecuteResult(outcome, decision)
        if decision == "retry":
            outcome = self._pipeline.run_task(project_id, task)
            self._notify_task_done(project_id, task, outcome)
            return TaskExecuteResult(outcome)
        if decision == "reassign":
            outcome = self._pipeline.run_task(project_id, task)
            self._notify_task_done(project_id, task, outcome)
            return TaskExecuteResult(outcome)
        self._notify_task_done(project_id, task, outcome)
        return TaskExecuteResult(outcome, decision)

    def _execute_loop(self, project_id: str, placeholder: dict) -> TaskOutcome:
        """运行 workflow loop 占位 task（委托 loop_runtime.run_loop）。"""
        loop_id = str(placeholder.get("loop") or "").strip()
        spec = self._loops_by_id.get(loop_id)
        if spec is None:
            return TaskOutcome(placeholder["id"], "failed", f"未知 loop「{loop_id}」")

        goal_prefix = ""
        desc = placeholder.get("description", "")
        if desc.strip():
            goal_prefix = desc.strip() + "\n\n"

        proj_meta = (self.store.get_project(project_id) or {}).get("meta") or {}
        goal_text = str(proj_meta.get("goal") or "")

        on_round = None
        if self._hooks and self._hooks.on_loop_round_done:
            on_round = self._hooks.on_loop_round_done

        deps = RunLoopDeps(
            execute_task=self._execute_task,
            persist_tasks=self._persist_tasks,
            append_run_event=self.store.append_run_event,
            update_task_meta=self.store.update_task_meta,
            set_task_status=self.store.set_task_status,
            store=self.store,
            on_loop_round_done=on_round,
            needs_review_blocks=self.config.needs_review_blocks,
            parallel_enabled=self.config.parallel_enabled,
            max_parallel=self.config.max_parallel,
            expand_ready=(
                (lambda pid, by_id, order, outcomes, agents, cycle=0: self._expander.expand_ready(
                    pid, by_id, order, outcomes, agents, cycle=cycle,
                ))
                if self.config.split_enabled else None
            ),
        )
        return run_loop(
            project_id, placeholder, spec, deps=deps,
            goal_prefix=goal_prefix, goal_text=goal_text,
        )

    def _fire_team_ready(self, project_id: str, agents: Optional[list[str]], title: str) -> None:
        if not self._hooks or not self._hooks.on_team_ready or not agents:
            return
        try:
            self._hooks.on_team_ready(project_id, agents, title)
        except Exception:
            pass

    def _notify_task_done(self, project_id: str, task: dict, outcome: TaskOutcome) -> None:
        if not self._hooks or not self._hooks.on_task_done:
            return
        try:
            self._hooks.on_task_done(
                project_id, task.get("id", ""), outcome.status, task.get("agent", ""),
            )
        except Exception:
            pass

    def _dispatch(self, project_id: str, tasks: list[dict],
                  *, persist: bool = True,
                  initial_outcomes: Optional[dict[str, TaskOutcome]] = None) -> ProjectOutcome:
        by_id = {t["id"]: t for t in tasks}
        order = topological_order(tasks)
        outcomes: dict[str, TaskOutcome] = dict(initial_outcomes or {})
        aborted = False
        paused = False
        cancelled = False

        while len(outcomes) < len(order):
            if not (cancelled or aborted or paused) and self._is_cancelled(project_id):
                cancelled = True
            if not paused and self._over_budget(project_id):
                paused = True

            if cancelled or aborted or paused:
                reason = ("项目已取消" if cancelled else
                          "项目已中止" if aborted else "项目已暂停（token 超预算）")
                for tid in order:
                    if tid not in outcomes:
                        outcomes[tid] = self._block(project_id, tid, reason)
                break

            if self.config.split_enabled:
                agents = self._agents_from_tasks(by_id)
                while self._expander.expand_ready(
                    project_id, by_id, order, outcomes, agents,
                ):
                    if self._over_budget(project_id):
                        paused = True
                        break

            wave = ready_tasks(order, by_id, outcomes,
                               needs_review_blocks=self.config.needs_review_blocks)
            if not wave:
                for tid in order:
                    if tid in outcomes:
                        continue
                    dep_block = deps_block(by_id[tid], outcomes,
                                           needs_review_blocks=self.config.needs_review_blocks)
                    outcomes[tid] = self._block(project_id, tid, dep_block or "依赖未满足")
                break

            if len(wave) > 1:
                self.store.append_run_event(
                    f"{project_id}:dispatch", "parallel_wave",
                    {"tasks": wave, "count": len(wave)},
                )
                if self._hooks and self._hooks.on_wave:
                    try:
                        self._hooks.on_wave(project_id, wave)
                    except Exception:
                        pass

            parallel = self.config.parallel_enabled and len(wave) > 1
            loop_tids = {
                tid for tid in wave
                if by_id[tid].get("loop") and by_id[tid]["loop"] in self._loops_by_id
            }
            if parallel:
                workers = min(len(wave), self.config.max_parallel)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futs = {}
                    for tid in wave:
                        task = by_id[tid]
                        if tid in loop_tids:
                            futs[pool.submit(self._execute_loop, project_id, task)] = tid
                        else:
                            futs[pool.submit(self._execute_task, project_id, task)] = tid
                    for fut in as_completed(futs):
                        tid = futs[fut]
                        if tid in loop_tids:
                            outcomes[tid] = fut.result()
                        else:
                            result = fut.result()
                            if result.split_subtasks:
                                self._expander.apply_split(
                                    project_id, by_id, order, tid, result.split_subtasks,
                                    source="triage_split",
                                )
                                continue
                            outcomes[tid] = result.outcome
                            if result.triage_decision == "abort":
                                aborted = True
                        self._print_progress(project_id, outcomes, len(order))
            else:
                for tid in wave:
                    task = by_id[tid]
                    if task.get("loop") and task["loop"] in self._loops_by_id:
                        outcome = self._execute_loop(project_id, task)
                        outcomes[tid] = outcome
                    else:
                        result = self._execute_task(project_id, task)
                        if result.split_subtasks:
                            self._expander.apply_split(
                                project_id, by_id, order, tid, result.split_subtasks,
                                source="triage_split",
                            )
                            continue
                        outcomes[tid] = result.outcome
                        if result.triage_decision == "abort":
                            aborted = True
                    self._print_progress(project_id, outcomes, len(order))
                    if aborted:
                        break

        # L2 并行收尾：波次结束后结算已交卷但仍 in_progress 的任务
        for task in tasks:
            tid = task["id"]
            row = self.store.get_task(project_id, tid) or {}
            if row.get("status") != "in_progress":
                continue
            settled = self._pipeline.settle_in_progress_task(project_id, task)
            if settled:
                outcomes[tid] = settled

        proj_status = self._finalize(project_id, outcomes, aborted, paused, cancelled,
                                     persist=persist)
        return ProjectOutcome(project_id, proj_status, outcomes)

    def _is_cancelled(self, project_id: str) -> bool:
        try:
            from common.project.project_cancel import cancel_registry
            if cancel_registry.is_cancelled(project_id):
                return True
        except Exception:
            pass
        p = self.store.get_project(project_id)
        return bool(p and p.get("status") == "cancelled")

    def _over_budget(self, project_id: str) -> bool:
        if not self.config.token_budget:
            return False
        bs = check_budget(self.store, project_id,
                          BudgetConfig(self.config.token_budget, self.config.budget_alert_ratio))
        # L3：达降级阈值时先尝试降级，再判断是否硬停
        if bs.ratio is not None and bs.ratio >= self.config.budget_degrade_threshold:
            self._maybe_degrade_budget(project_id, bs)
        if bs.state == "over":
            self.store.append_run_event(f"{project_id}:budget", "budget_over",
                                        {"used": bs.used, "limit": bs.limit})
            return True
        if bs.state == "alert":
            self.store.append_run_event(f"{project_id}:budget", "budget_alert",
                                        {"used": bs.used, "limit": bs.limit, "ratio": bs.ratio})
        return False

    def _maybe_degrade_budget(self, project_id: str, bs) -> None:
        """L3：预算达降级阈值时切换轻量 backend/model（每项目仅一次）。"""
        proj = self.store.get_project(project_id)
        meta = (proj or {}).get("meta") or {}
        if meta.get("degraded"):
            return
        backend = self.config.budget_degrade_backend
        model = self.config.budget_degrade_model
        if not backend and not model:
            return
        patch: dict = {"degraded": True}
        if backend:
            patch["degrade_backend"] = backend
        if model:
            patch["degrade_model"] = model
        self.store.update_project_meta(project_id, **patch)
        self._apply_degrade_agents_config(project_id, backend, model)
        self.store.append_run_event(
            f"{project_id}:budget", "budget_degrade",
            {"used": bs.used, "limit": bs.limit, "ratio": bs.ratio,
             "backend": backend, "model": model},
        )

    def _apply_degrade_agents_config(self, project_id: str,
                                     backend: str, model: str) -> None:
        """将降级 backend/model 写入项目 agent 的 agents_config（供 Transport 读取）。"""
        agents = {r.get("agent") for r in self.store.list_tasks(project_id) if r.get("agent")}
        if not agents:
            return
        cfg: dict = {}
        cfg_path = paths.AGENTS_CONFIG_FILE
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        changed = False
        for aid in agents:
            entry = cfg.setdefault(aid, {})
            if backend:
                entry["backend"] = backend
                changed = True
            if model:
                entry["model"] = model
                changed = True
        if changed:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8",
            )

    def _pause_if_over_budget(self, project_id: str) -> Optional[ProjectOutcome]:
        """规划期 interaction 完成后检查 budget；超限则 paused，不再派发后续任务。"""
        if not self._over_budget(project_id):
            return None
        self.store.set_project_status(project_id, "paused")
        gc_project_workspace(self.store, project_id)
        return ProjectOutcome(project_id, "paused", {})

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
        # 兜底：outcomes 只含本轮跑过+settle 的 task，loop 中途退出时 DB 里可能仍有
        # pending/in_progress 的残留 task 不在 outcomes 里，导致 derive_project_status
        # 只看到 {needs_review}⊆TERMINAL_OK 误判 completed。这里用 DB 全量 task 状态校验：
        # 若算出 completed 但 DB 仍有活跃（非终态）task，降级 partially_failed，避免项目假完成。
        # 注意：cancelled（split 替换的旧 task）/ failed / blocked / needs_review / completed
        # 都是终态，不算残留；只 pending/in_progress/running 这类活跃态才算未跑完。
        if status == "completed" and not aborted and not paused and not cancelled:
            active_statuses = {"pending", "in_progress", "running", "ready"}
            active = [
                (t.get("task_id") or t.get("id") or "")
                for t in self.store.list_tasks(project_id)
                if (t.get("status") or "") in active_statuses
            ]
            if active:
                status = "partially_failed"
                self.store.append_run_event(
                    f"{project_id}:finalize",
                    "project_downgraded",
                    {
                        "reason": "DB 仍有活跃 task 但 outcomes 判 completed",
                        "active_count": len(active),
                        "sample": active[:5],
                    },
                )
        if persist:
            self.store.set_project_status(project_id, status)
            gc_project_workspace(self.store, project_id)
            if status == "completed":
                self._maybe_extract_skills(project_id)
                try:
                    from memstack.facade import on_project_complete
                    from memstack.orchestration.context import ProjectCompleteContext

                    on_project_complete(
                        ProjectCompleteContext(
                            project_id=project_id,
                            store=self.store,
                            status=status,
                        )
                    )
                except Exception:
                    pass
        return status

    def _maybe_extract_skills(self, project_id: str) -> None:
        if not self.config.skill_extract_enabled:
            return
        from pathlib import Path

        from common.skill.skill_extract import extract_skill_draft

        tasks = self.store.list_tasks(project_id)
        skill_task = next(
            (t for t in tasks if (t.get("task_id") or t.get("id")) == "skill-extract"),
            None,
        )
        if skill_task and skill_task.get("status") in TERMINAL_OK:
            candidates = [skill_task]
        else:
            candidates = [
                t for t in tasks
                if t.get("task_type") == "research" and t.get("status") in TERMINAL_OK
            ]
        for task in candidates:
            tid = task.get("task_id") or task.get("id") or ""
            if not tid:
                continue
            task_type = task.get("task_type", "")
            meta = task.get("meta") or {}
            ref = meta.get("ref") or artifact_rel_path(tid, task_type)
            base = task_deliverable_base(project_id, tid, task_type)
            deliverable = Path(ref) if Path(ref).is_absolute() else base / ref
            try:
                draft = extract_skill_draft(self.store, project_id, tid, deliverable)
                self.store.append_run_event(
                    f"{project_id}:skill_extract",
                    "skill_draft_written",
                    {"task_id": tid, "path": str(draft)},
                )
            except OSError as exc:
                logging.getLogger(__name__).warning(
                    "skill extract failed for %s:%s: %s", project_id, tid, exc
                )
