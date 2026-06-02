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
from common.registry import get_spec
from common.store import Store

TERMINAL_OK = {"completed", "needs_review"}
TERMINAL_BAD = {"failed", "blocked"}


@dataclass
class ProcessConfig:
    mode: str = "one_shot"                 # one_shot | recurring
    max_gate_retries: int = 3              # 确定性门禁失败的重试上限（D18）
    max_plan_retries: int = 2              # task_plan 指派团队外 agent 时的重试上限
    review_enabled: bool = False           # 是否走同行评审（暂为占位，质量归 Agent）
    quality_floor: float = 0.6             # 自评低于此 → needs_review
    needs_review_blocks: bool = False      # needs_review 是否阻塞依赖者（默认否，D18）
    enforce_must_include: bool = False     # 透传 Gate（D14 默认关）
    inject_context: bool = True            # 注入直接上游摘要+引用（D16 第 1 层）
    token_budget: Optional[int] = None     # per-project token 硬上限（D17；None=不限）
    budget_alert_ratio: float = 0.8        # 预算告警阈值
    max_cycles: int = 3                    # recurring 模式的周期上限（防空转，D10）


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


def _prefix_cycle(tasks: list[dict], cycle: int) -> list[dict]:
    """给一轮任务的 id 与依赖加 ``cN_`` 前缀，避免跨周期覆盖、便于可观测区分轮次。"""
    pref = f"c{cycle}_"
    return [{**t, "id": pref + t["id"],
             "dependencies": [pref + d for d in t.get("dependencies", [])]} for t in tasks]


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
                                  status="in_progress",
                                  meta={"token_budget": self.config.token_budget,
                                        "goal": goal})
        if agents is None:
            agents = self._team_config(project_id, goal)
        # recurring：未预置 tasks 时走周期循环（周期迭代 + 轮次继承，D10）
        if self.config.mode == "recurring" and tasks is None:
            return self._run_recurring(project_id, goal, agents)
        if tasks is None:
            tasks = self._task_plan(project_id, goal, agents)
        self._persist_tasks(project_id, tasks)
        return self._dispatch(project_id, tasks)

    def _persist_tasks(self, project_id: str, tasks: list[dict]) -> None:
        for t in tasks:
            self.store.upsert_task(
                project_id, t["id"], name=t.get("name", ""), agent=t.get("agent", ""),
                reviewer=t.get("reviewer", ""), task_type=t.get("task_type", ""),
                dependencies=t.get("dependencies", []), status="pending",
            )

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

    def _task_plan(self, project_id: str, goal: str, agents: list[str],
                   *, cycle: int = 0, prior_summary: str = "") -> list[dict]:
        """规划任务 DAG。硬校验：每个任务的 agent 必须 ∈ team（team_config 选出的名册）；
        越界则带 feedback 重试，耗尽仍越界则显式失败（不让漏网 agent 进调度）。

        recurring：cycle>0 时带上一周期的滚动摘要做轮次继承（注入 input.prior_summary）。"""
        team = set(agents)
        feedback: list[str] = []
        bad: list[str] = []
        base_iid = f"{project_id}:task_plan" + (f":c{cycle}" if cycle else "")
        plan_input = {"goal": goal, "team": agents}
        if cycle:
            plan_input["cycle"] = cycle
            plan_input["prior_summary"] = prior_summary
        for attempt in range(1, self.config.max_plan_retries + 1):
            iid = base_iid + ("" if attempt == 1 else f":{attempt}")
            req = {
                "interaction_id": iid,
                "kind": "task_plan", "project_id": project_id, "agent_id": "main",
                "intent": "规划任务与依赖", "input": plan_input,
                "response_schema": "task_plan.result@1.0",
                "retry_feedback": feedback,
            }
            res = self.port.run(req)
            if res.status != "done":
                raise RuntimeError(f"task_plan 失败：{res.status} {res.reason}")
            tasks = res.response["result"]["tasks"]
            bad = sorted({t.get("agent", "") for t in tasks if t.get("agent", "") not in team})
            if not bad:
                return tasks
            feedback = [f"以下 agent 不在团队名册中：{', '.join(bad)}；"
                        f"每个任务的 agent 只能从 [{', '.join(agents)}] 中选，请重新规划。"]
            self.store.append_run_event(iid, "plan_rejected", {"invalid_agents": bad})
        raise RuntimeError(
            f"task_plan 指派了团队外 agent {bad}（重试 {self.config.max_plan_retries} 次仍未修正）")

    # ── recurring：周期循环 + 轮次继承（D10）────────────────────

    def _run_recurring(self, project_id: str, goal: str, agents: list[str]) -> ProjectOutcome:
        """有界周期循环：每周期重规划（注入上一周期滚动摘要）→ 跑 DAG → 摘要滚动入 KB。

        团队 team_config 一次定、各周期复用。停止条件（任一）：达到 max_cycles、外部取消、
        中止/超预算、或本周期零完成（避免空转）。项目状态由本循环统一收尾，不在周期间反复落终态。
        """
        overall: dict[str, TaskOutcome] = {}
        prior_summary = ""
        stop_status: Optional[str] = None
        for cycle in range(1, max(1, self.config.max_cycles) + 1):
            if self._is_cancelled(project_id):
                stop_status = "cancelled"
                break
            tasks = _prefix_cycle(
                self._task_plan(project_id, goal, agents,
                                cycle=cycle, prior_summary=prior_summary),
                cycle)
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
                stop_status = "failed"  # 本周期零产出 → 停，避免无意义空转
                break
        final = stop_status or "completed"
        self.store.set_project_status(project_id, final)
        return ProjectOutcome(project_id, final, overall)

    def _cycle_summary(self, project_id: str, tasks: list[dict]) -> str:
        """把本周期各任务的成果摘要拼成一份滚动摘要，作为下一周期 task_plan 的上下文。"""
        parts: list[str] = []
        for t in tasks:
            row = self.store.get_task(project_id, t["id"]) or {}
            summary = (row.get("meta") or {}).get("summary")
            if summary:
                parts.append(f"- {row.get('name') or t['id']}: {summary}")
        return "\n".join(parts) or "（本周期无可用摘要）"

    # ── DAG 调度（串行，D12）──────────────────────────────────

    def _dispatch(self, project_id: str, tasks: list[dict],
                  *, persist: bool = True) -> ProjectOutcome:
        by_id = {t["id"]: t for t in tasks}
        order = topological_order(tasks)
        outcomes: dict[str, TaskOutcome] = {}
        aborted = False
        paused = False
        cancelled = False

        for tid in order:
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

        proj_status = self._finalize(project_id, outcomes, aborted, paused, cancelled,
                                     persist=persist)
        return ProjectOutcome(project_id, proj_status, outcomes)

    def _is_cancelled(self, project_id: str) -> bool:
        """协作式取消：外部把项目状态置为 cancelled，调度循环在任务间隙观察后停止派发。"""
        p = self.store.get_project(project_id)
        return bool(p and p.get("status") == "cancelled")

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
                if self.config.review_enabled:
                    status = self._peer_review(project_id, task, status, task_type, rel_path)
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

    # ── 同行评审（开关 review_enabled；reviewer 由 main 在 task_plan 指派）──

    def _peer_review(self, project_id: str, task: dict, status: str,
                     task_type: str, rel_path: str) -> str:
        """开关打开且 main 指派了 reviewer 时，发 kind=review 给该 agent 对照验收标准评审。

        判责：机制（何时评/契约/打回语义）= 框架；选谁评 = main；标准 = 业务配置
        （acceptance_criteria @ 注册表）；判断 = reviewer agent。打回 → needs_review（不静默通过）。
        """
        tid = task["id"]
        reviewer = (self.store.get_task(project_id, tid) or {}).get("reviewer") \
            or task.get("reviewer", "")
        if not reviewer:
            return status  # 开关开但 main 未指派 reviewer：视为本任务无需评审
        spec = get_spec(task_type) if task_type else None
        iid = f"{project_id}:{tid}:review"
        res = self.port.run({
            "interaction_id": iid, "kind": "review",
            "project_id": project_id, "task_id": tid, "agent_id": reviewer,
            "intent": f"评审任务 {tid} 的交付物",
            "input": {"task": task, "deliverable_path": rel_path,
                      "acceptance_criteria": spec.acceptance_criteria if spec else []},
            "response_schema": "review.result@1.0",
        })
        if res.status != "done":
            self.store.append_run_event(iid, "review_unreachable", {"reason": res.reason})
            return "needs_review"  # 评审不可达 → 质量未确认，不静默放行
        result = res.response.get("result", {})
        passed = bool(result.get("passed"))
        self.store.append_run_event(iid, "review_done",
                                    {"passed": passed, "feedback": result.get("feedback", "")})
        # reviewer 是权威：通过 → 升级为 completed（即便自评因 known_gaps 标了 needs_review）；
        # 打回 → needs_review（不静默通过）。
        return "completed" if passed else "needs_review"

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
                  aborted: bool, paused: bool = False, cancelled: bool = False,
                  persist: bool = True) -> str:
        statuses = {o.status for o in outcomes.values()}
        if cancelled:
            status = "cancelled"
        elif aborted:
            status = "aborted"
        elif paused:
            status = "paused"
        elif statuses <= TERMINAL_OK:
            status = "completed"
        elif statuses & {"completed", "needs_review"}:
            status = "partially_failed"
        else:
            status = "failed"
        if persist:
            self.store.set_project_status(project_id, status)
        return status
