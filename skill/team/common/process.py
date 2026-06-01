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

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.agent_port import AgentPort
from common.gate import check_execute
from common.observability import BudgetConfig, check_budget
from common.paths import deliverables_dir
from common.store import Store

TERMINAL_OK = {"completed", "needs_review"}
TERMINAL_BAD = {"failed", "blocked"}


@dataclass
class ProcessConfig:
    mode: str = "one_shot"                 # one_shot | recurring
    max_gate_retries: int = 3              # 确定性门禁失败的重试上限（D18）
    review_enabled: bool = False           # 是否走同行评审（暂为占位，质量归 Agent）
    quality_floor: float = 0.6             # 自评低于此 → needs_review
    needs_review_blocks: bool = False      # needs_review 是否阻塞依赖者（默认否，D18）
    enforce_must_include: bool = False     # 透传 Gate（D14 默认关）
    inject_context: bool = True            # 注入直接上游摘要+引用（D16 第 1 层）
    token_budget: Optional[int] = None     # per-project token 硬上限（D17；None=不限）
    budget_alert_ratio: float = 0.8        # 预算告警阈值


@dataclass
class TaskOutcome:
    task_id: str
    status: str                            # completed | needs_review | failed | blocked
    reason: str = ""
    attempts: int = 0
    response: Optional[dict] = None


@dataclass
class ProjectOutcome:
    project_id: str
    status: str                            # completed | partially_failed | failed | aborted
    tasks: dict[str, TaskOutcome] = field(default_factory=dict)


def topological_order(tasks: list[dict]) -> list[str]:
    """Kahn 拓扑排序，返回任务 id 顺序；存在环则抛 ValueError。"""
    ids = {t["id"] for t in tasks}
    indeg = {t["id"]: 0 for t in tasks}
    graph: dict[str, list[str]] = {t["id"]: [] for t in tasks}
    for t in tasks:
        for dep in t.get("dependencies", []):
            if dep in ids:
                graph[dep].append(t["id"])
                indeg[t["id"]] += 1
    queue = deque(sorted(tid for tid, d in indeg.items() if d == 0))
    order: list[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) != len(ids):
        raise ValueError("任务依赖存在环")
    return order


class Process:
    def __init__(self, store: Store, port: AgentPort, config: Optional[ProcessConfig] = None):
        self.store = store
        self.port = port
        self.config = config or ProcessConfig()

    # ── 入口 ─────────────────────────────────────────────────

    def run(self, project_id: str, *, title: str = "", goal: str = "",
            agents: Optional[list[str]] = None,
            tasks: Optional[list[dict]] = None) -> ProjectOutcome:
        """跑一个项目。

        若给定 agents/tasks 则直接用（便于测试与已规划场景）；否则走 team_config / task_plan
        两个 Interaction 由 Main 决策（live 路径）。
        """
        self.store.upsert_project(project_id, title=title, mode=self.config.mode,
                                  status="in_progress")
        if agents is None:
            agents = self._team_config(project_id, goal)
        if tasks is None:
            tasks = self._task_plan(project_id, goal, agents)
        for t in tasks:
            self.store.upsert_task(
                project_id, t["id"], name=t.get("name", ""), agent=t.get("agent", ""),
                reviewer=t.get("reviewer", ""), task_type=t.get("task_type", ""),
                dependencies=t.get("dependencies", []), status="pending",
            )
        return self._dispatch(project_id, tasks)

    # ── team_config / task_plan（决策类 Interaction）──────────

    def _team_config(self, project_id: str, goal: str) -> list[str]:
        req = {
            "interaction_id": f"{project_id}:team_config",
            "kind": "team_config", "project_id": project_id, "agent_id": "main",
            "intent": "为目标配置团队", "input": {"goal": goal},
            "response_schema": "team_config.result@1.0",
        }
        res = self.port.run(req)
        if res.status != "done":
            raise RuntimeError(f"team_config 失败：{res.status} {res.reason}")
        return res.response["result"]["agents"]

    def _task_plan(self, project_id: str, goal: str, agents: list[str]) -> list[dict]:
        req = {
            "interaction_id": f"{project_id}:task_plan",
            "kind": "task_plan", "project_id": project_id, "agent_id": "main",
            "intent": "规划任务与依赖", "input": {"goal": goal, "team": agents},
            "response_schema": "task_plan.result@1.0",
        }
        res = self.port.run(req)
        if res.status != "done":
            raise RuntimeError(f"task_plan 失败：{res.status} {res.reason}")
        return res.response["result"]["tasks"]

    # ── DAG 调度（串行，D12）──────────────────────────────────

    def _dispatch(self, project_id: str, tasks: list[dict]) -> ProjectOutcome:
        by_id = {t["id"]: t for t in tasks}
        order = topological_order(tasks)
        outcomes: dict[str, TaskOutcome] = {}
        aborted = False
        paused = False

        for tid in order:
            if aborted or paused:
                reason = "项目已中止" if aborted else "项目已暂停（token 超预算）"
                outcomes[tid] = self._block(project_id, tid, reason)
                continue
            if self._over_budget(project_id):
                paused = True
                outcomes[tid] = self._block(project_id, tid, "项目已暂停（token 超预算）")
                continue
            task = by_id[tid]
            dep_block = self._deps_block(task, outcomes)
            if dep_block:
                outcomes[tid] = self._block(project_id, tid, dep_block)
                continue

            outcome = self._run_task(project_id, task)
            if outcome.status == "failed":
                decision = self._triage(project_id, task, outcome.reason)
                if decision == "retry":
                    outcome = self._run_task(project_id, task)
                elif decision == "reassign":
                    outcome = self._run_task(project_id, task)  # agent 已被 triage 改写
                elif decision == "abort":
                    aborted = True
                # drop：保持 failed，不再处理
            outcomes[tid] = outcome

        proj_status = self._finalize(project_id, outcomes, aborted, paused)
        return ProjectOutcome(project_id, proj_status, outcomes)

    def _over_budget(self, project_id: str) -> bool:
        """方案丙（D17）：到硬上限 → 暂停项目 + 上报，后续任务不再派发。"""
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

    def _deps_block(self, task: dict, outcomes: dict[str, TaskOutcome]) -> str:
        for dep in task.get("dependencies", []):
            o = outcomes.get(dep)
            if o is None:
                continue
            if o.status in TERMINAL_BAD:
                return f"上游 {dep} 为 {o.status}"
            if o.status == "needs_review" and self.config.needs_review_blocks:
                return f"上游 {dep} 待评审（阻塞策略）"
        return ""

    # ── 单任务 execute 管线：契约/格式门禁 + 重试 + 质量判定 ──

    def _run_task(self, project_id: str, task: dict) -> TaskOutcome:
        tid = task["id"]
        agent = self.store.get_task(project_id, tid).get("agent") or task.get("agent", "")
        task_type = task.get("task_type", "")
        base_dir = deliverables_dir(project_id)
        rel_path = f"{tid}_deliverable.md"
        feedback: list[str] = []

        context = self._build_context(project_id, task) if self.config.inject_context else {}

        for attempt in range(1, self.config.max_gate_retries + 1):
            req = {
                "interaction_id": f"{project_id}:{tid}:execute:{attempt}",
                "kind": "execute", "project_id": project_id, "task_id": tid,
                "agent_id": agent, "intent": task.get("description", task.get("name", "")),
                "input": {"task": task, "deliverable_path": rel_path},
                "context": context,
                "response_schema": "execute.result@1.0",
                "constraints": {"task_type": task_type},
                "retry_feedback": feedback,
            }
            res = self.port.run(req)
            if res.status != "done":
                # 端口看门狗/传输终态：客观失败（D18）
                self.store.set_task_status(project_id, tid, "failed")
                return TaskOutcome(tid, "failed", f"端口 {res.status}: {res.reason}", attempt)

            resp = res.response
            # 门禁需要 task_type 来取注册表规则；注入到 meta 供 gate 读取
            resp.setdefault("meta", {})
            if isinstance(resp["meta"], dict):
                resp["meta"].setdefault("task_type", task_type)
            gate_res = check_execute(resp, base_dir=str(base_dir),
                                     enforce_must_include=self.config.enforce_must_include)
            if gate_res.passed:
                status = self._quality_status(resp)
                self.store.set_task_status(project_id, tid, status)
                self._capture_summary(project_id, tid, resp, rel_path)
                self.store.append_run_event(req["interaction_id"], "gate_passed",
                                            {"final_status": status})
                return TaskOutcome(tid, status, "", attempt, resp)

            feedback = [f"[{f['rule']}] 期望：{f['expected']}；实际：{f['actual']}"
                        for f in gate_res.failures]
            self.store.append_run_event(req["interaction_id"], "gate_failed",
                                        {"failures": gate_res.failures})

        self.store.set_task_status(project_id, tid, "failed")
        return TaskOutcome(tid, "failed", "确定性门禁重试耗尽", self.config.max_gate_retries)

    # ── Context-Memory 第 1 层：直接上游摘要 + 引用注入（D16）──

    def _build_context(self, project_id: str, task: dict) -> dict:
        """注入**直接上游**的「摘要 + 引用」（非全文、非全历史）。

        摘要由产出 agent 在 submit_result 时写、存 task.meta（_capture_summary）；
        拼装/注入 = 框架机制，摘要内容 = agent（D16 判责）。
        """
        upstream = []
        for dep in task.get("dependencies", []):
            row = self.store.get_task(project_id, dep)
            meta = (row.get("meta") if row else None) or {}
            if meta.get("summary") or meta.get("ref"):
                upstream.append({
                    "task_id": dep,
                    "summary": meta.get("summary", ""),
                    "ref": meta.get("ref", ""),
                })
        return {"upstream": upstream} if upstream else {}

    def _capture_summary(self, project_id: str, tid: str, resp: dict, rel_path: str) -> None:
        """从 agent 响应抽取摘要 + 引用，存 task.meta 供下游注入（D16）。"""
        quality = resp.get("quality") or {}
        outcome = (resp.get("result") or {}).get("outcome") or {}
        artifact = outcome.get("artifact") or {}
        summary = resp.get("notes") or quality.get("notes") or artifact.get("title") or ""
        self.store.update_task_meta(project_id, tid, summary=summary, ref=rel_path)

    def _quality_status(self, resp: dict) -> str:
        """质量未确认 → needs_review（默认不阻塞，D18）。"""
        q = resp.get("quality") or {}
        score = q.get("score")
        gaps = q.get("known_gaps") or []
        if gaps or (isinstance(score, (int, float)) and score < self.config.quality_floor):
            return "needs_review"
        return "completed"

    # ── triage（重试耗尽 → 委托 Main 决策，D18）───────────────

    def _triage(self, project_id: str, task: dict, reason: str) -> str:
        tid = task["id"]
        req = {
            "interaction_id": f"{project_id}:{tid}:triage",
            "kind": "triage", "project_id": project_id, "task_id": tid,
            "agent_id": "main", "intent": f"任务 {tid} 失败，请决策",
            "input": {"task": task, "reason": reason},
            "response_schema": "triage.result@1.0",
        }
        res = self.port.run(req)
        if res.status != "done":
            return "drop"  # Main 不可达 → 保守丢弃（任务保持 failed）
        result = res.response["result"]
        decision = result.get("decision", "drop")
        if decision == "reassign" and result.get("target_agent"):
            self.store.upsert_task(project_id, tid, agent=result["target_agent"],
                                   name=task.get("name", ""),
                                   task_type=task.get("task_type", ""),
                                   dependencies=task.get("dependencies", []))
            task["agent"] = result["target_agent"]
        return decision

    # ── 收尾 ─────────────────────────────────────────────────

    def _block(self, project_id: str, tid: str, reason: str) -> TaskOutcome:
        self.store.set_task_status(project_id, tid, "blocked")
        self.store.append_run_event(f"{project_id}:{tid}:blocked", "blocked", {"reason": reason})
        return TaskOutcome(tid, "blocked", reason)

    def _finalize(self, project_id: str, outcomes: dict[str, TaskOutcome],
                  aborted: bool, paused: bool = False) -> str:
        statuses = {o.status for o in outcomes.values()}
        if aborted:
            status = "aborted"
        elif paused:
            status = "paused"
        elif statuses <= TERMINAL_OK:
            status = "completed"
        elif statuses & {"completed", "needs_review"}:
            status = "partially_failed"
        else:
            status = "failed"
        self.store.set_project_status(project_id, status)
        return status
