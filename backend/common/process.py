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
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.agent_port import AgentPort, finalize_interaction, read_adoptable_response
from common.gate import check_execute
from common.observability import BudgetConfig, check_budget
from common.project_artifacts import (
    artifact_rel_path,
    is_code_project_task,
    scan_project_dir,
    task_deliverable_base,
    task_project_dir,
)
from common.paths import (
    AGENTS_CONFIG_FILE,
    AGENTS_REGISTRY_FILE,
    WORKSPACE_PREFIX,
    WORKSPACES_DIR,
    deliverables_dir,
    workspace_dir,
)
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
    split_enabled: bool = False            # 派发前静态递归展开（evaluate）；默认关，opt-in
    max_split_depth: int = 2               # 递归拆分深度上限 → 终止性硬底（无论 agent 怎么判都收敛）
    max_subtasks: int = 8                  # 单次拆分子任务数上限（防扇出爆炸）
    auto_create_agents: bool = True        # team_config 时自动创建未就绪 agent
    default_backend: str = "opencode"      # 自动创建 agent 时的默认后端
    default_model: str = ""                # 自动创建 agent 时的默认模型


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
            if dep not in ids:
                raise ValueError(f"依赖 {dep} 未在任务列表中")
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


@dataclass
class PlanCheckResult:
    """plan gate 校验结果。passed=False 时 feedback 包含给 agent 的打回理由。"""
    passed: bool
    feedback: str = ""


def check_plan(tasks: list[dict], team: set[str], *,
               max_fanout: Optional[int] = None) -> PlanCheckResult:
    """确定性门禁：校验 task DAG 的 agent/类型/依赖/无环/扇出。

    task_plan（顶层）和 evaluate（子任务拆分）的输出都经过此门禁，
    保证所有进入 _dispatch 的 DAG 符合同一套标准。

    校验项（按顺序短路）：
    1. id 唯一性
    2. agent ∈ team（名册）
    3. task_type ∈ registry（注册表）
    4. 无 dangling 依赖（所有 dep 指向本批次内的 id）
    5. 无环（Kahn 拓扑排序可收敛）
    6. 可选扇出上限（仅 evaluate 子任务启用）
    """
    # 1. id 唯一
    ids = [t.get("id", "") for t in tasks]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        return PlanCheckResult(False, f"任务 id 有重复：{', '.join(dupes)}")

    id_set = set(ids)

    # 2. agent ∈ team
    bad_agents = sorted({t.get("agent", "") for t in tasks
                         if t.get("agent", "") not in team})
    if bad_agents:
        return PlanCheckResult(False,
            f"以下 agent 不在团队名册中：{', '.join(bad_agents)}；"
            f"每个任务的 agent 只能从 [{', '.join(sorted(team))}] 中选。")

    # 3. task_type ∈ registry
    bad_types = sorted({t.get("task_type", "") for t in tasks
                        if get_spec(t.get("task_type", "")) is None})
    if bad_types:
        return PlanCheckResult(False,
            f"以下 task_type 未在注册表中：{', '.join(bad_types)}；"
            f"只能用已注册的类型。")

    # 4. 无 dangling 依赖
    dangling = sorted({d for t in tasks for d in t.get("dependencies", [])
                       if d not in id_set})
    if dangling:
        return PlanCheckResult(False,
            f"依赖引用了不存在的任务 id：{', '.join(dangling)}；"
            f"请仅引用本批次内的任务。")

    # 5. 无环
    try:
        topological_order(tasks)
    except ValueError:
        return PlanCheckResult(False, "任务依赖存在环，请重新规划。")

    # 6. 可选扇出上限
    if max_fanout is not None and len(tasks) > max_fanout:
        return PlanCheckResult(False,
            f"子任务数 {len(tasks)} 超过上限 {max_fanout}，请合并。")

    return PlanCheckResult(True)


_IDENTITY_TEMPLATES = {
    "IDENTITY.md": """# Agent Identity

emoji: 🤖
name: {name}
role: {role}
description: {description}
""",
    "AGENTS.md": """# {name} - Agent 配置

## 核心定位
{description}

## 工作流程
1. 接收任务
2. 分析需求
3. 执行工作
4. 输出结果

## 协作方式
- 通过 .trigger/.response 文件系统通信
- 返回 JSON 格式的 structured response
""",
    "SOUL.md": """# {name} - 灵魂与行为准则

## 行为准则
1. 准确：确保输出正确可靠
2. 高效：快速响应，不浪费资源
3. 协作：积极与其他 Agent 配合
4. 透明：清晰说明工作状态
""",
    "USER.md": """# 用户信息

用户: 待配置
联系方式: 待配置
偏好: 待配置
""",
    "TOOLS.md": """# 可用工具

## 基础工具
- 文件读写：读取和写入工作目录中的文件
- 代码执行：执行 shell 命令
- 网络请求：进行 HTTP 请求
""",
    "HEARTBEAT.md": """# 心跳检查项

## 每日检查
- [ ] 工作目录是否正常
- [ ] 身份文件是否完整
- [ ] 工具是否可用
""",
}


def _auto_create_agent(agent_id: str, *, name: str = "", role: str = "worker",
                        description: str = "",
                        backend: str = "opencode", model: str = "") -> bool:
    """自动创建 agent 工作目录、身份文件和注册项。

    供 _team_config 在 Main 返回未就绪 agent 时调用。
    纯模板生成（不调用 LLM），保证内核启动确定性。
    """
    ws_dir = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"
    if ws_dir.exists():
        return True  # 已存在，无需创建

    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / ".trigger").mkdir(exist_ok=True)
    (ws_dir / ".response").mkdir(exist_ok=True)

    display_name = name or agent_id
    desc = description or f"自动创建的 agent：{agent_id}"
    for fname, template in _IDENTITY_TEMPLATES.items():
        content = template.format(name=display_name, role=role, description=desc)
        (ws_dir / fname).write_text(content.strip() + "\n", encoding="utf-8")

    # 注册到 agents_config.json
    AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if AGENTS_CONFIG_FILE.exists():
        try:
            cfg = json.loads(AGENTS_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg[agent_id] = {"backend": backend, "model": model, "extra": {}}
    AGENTS_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    # 注册到 agents_registry.json
    reg = {"version": "1.0", "agents": {}}
    if AGENTS_REGISTRY_FILE.exists():
        try:
            reg = json.loads(AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    reg.setdefault("agents", {})
    reg["agents"][agent_id] = {
        "name": display_name, "role": role,
        "description": desc, "capabilities": [], "task_types": [],
    }
    AGENTS_REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")

    return True


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
            if self.config.split_enabled:
                tasks = self._expand_plan(project_id, tasks, agents)
        # 最终断言：无论 tasks 从哪条路径来，进入持久化/调度前必须通过 plan gate
        check = check_plan(tasks, set(agents))
        if not check.passed:
            raise RuntimeError(f"plan gate 校验失败（{project_id}）：{check.feedback}")
        self._persist_tasks(project_id, tasks)
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
                settled = self._settle_in_progress_task(project_id, task)
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
        agents = res.response["result"]["agents"]

        # 动态创建：Main 返回的 agent 若无工作目录则自动创建
        missing = [a for a in agents if not workspace_dir(a).exists()]
        if missing and self.config.auto_create_agents:
            self.store.append_run_event(f"{project_id}:team_config", "auto_create_agents",
                                        {"agent_ids": missing})
            for aid in missing:
                _auto_create_agent(aid, description=f"自动创建的 agent：{aid}",
                                   backend=self.config.default_backend,
                                   model=self.config.default_model)
        elif missing and not self.config.auto_create_agents:
            raise RuntimeError(
                f"team_config 返回了未就绪的 agent（auto_create_agents=False）：{missing}")

        return agents

    def _task_plan(self, project_id: str, goal: str, agents: list[str],
                   *, cycle: int = 0, prior_summary: str = "") -> list[dict]:
        """规划任务 DAG。经 check_plan 门禁校验（agent/类型/环/依赖）；
        越界则带 feedback 重试，耗尽则显式失败（不让漏网 DAG 进调度）。

        recurring：cycle>0 时带上一周期的滚动摘要做轮次继承（注入 input.prior_summary）。"""
        team = set(agents)
        feedback: list[str] = []
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
            check = check_plan(tasks, team)
            if check.passed:
                return tasks
            feedback = [check.feedback]
            self.store.append_run_event(iid, "plan_rejected", {"reason": check.feedback})
        raise RuntimeError(
            f"task_plan 校验失败（重试 {self.config.max_plan_retries} 次仍未通过）：{feedback[0]}")

    # ── 派发前静态递归展开（evaluate → 折回 DAG）──────────────────

    def _expand_plan(self, project_id: str, tasks: list[dict],
                     agents: list[str], *, cycle: int = 0) -> list[dict]:
        """派发前的**静态**递归展开：对每个任务问一次 evaluate，should_split 则就地展开成
        子任务、重接依赖、入队继续展开。深度/扇出有界 → 必然收敛。展开产物仍是静态 DAG，
        `_dispatch` / 持久化 / 恢复全部不变（动态改图留作 v2）。

        cycle>0（recurring）时给 evaluate 交互 id 加 :c{cycle} 后缀，避免跨周期撞 id。"""
        result: dict[str, dict] = {t["id"]: t for t in tasks}
        worklist = deque((t["id"], 0) for t in tasks)
        suffix = f":c{cycle}" if cycle else ""
        while worklist:
            tid, depth = worklist.popleft()
            if depth >= self.config.max_split_depth:
                continue                              # 深度硬底：到顶不再问，保证终止
            task = result.get(tid)
            if task is None:
                continue                              # 已被上一层展开替换掉
            subs = self._evaluate(project_id, task, agents, depth, cycle=cycle)
            if not subs:
                continue
            self._splice(result, task, subs)
            self.store.append_run_event(
                f"{project_id}:{tid}:evaluate{suffix}", "task_split",
                {"parent": tid, "children": [s["id"] for s in subs], "depth": depth})
            worklist.extend((s["id"], depth + 1) for s in subs)
        return list(result.values())

    def _evaluate(self, project_id: str, task: dict, agents: list[str],
                  depth: int, *, cycle: int = 0) -> Optional[list[dict]]:
        """问 task 的 assigned agent「要不要拆」。照 _task_plan 的 检查→feedback→重试 样板：
        子任务须 agent∈team & task_type∈registry & 组内无环 & 不超扇出，否则带 feedback 重试。
        返回经校验+归一的子任务（dict 列表）；不拆/不可达/重试耗尽 → None（原样执行，不阻断）。"""
        team = set(agents)
        feedback: list[str] = []
        base_iid = f"{project_id}:{task['id']}:evaluate" + (f":c{cycle}" if cycle else "")
        for attempt in range(1, self.config.max_plan_retries + 1):
            iid = base_iid + ("" if attempt == 1 else f":{attempt}")
            res = self.port.run({
                "interaction_id": iid, "kind": "evaluate",
                "project_id": project_id, "task_id": task["id"],
                "agent_id": task.get("agent", ""),
                "intent": "评估任务是否需要拆分为子任务",
                "input": {"task": task, "depth": depth,
                          "max_depth": self.config.max_split_depth,
                          "max_subtasks": self.config.max_subtasks, "team": agents},
                "response_schema": "evaluate.result@1.0",
                "retry_feedback": feedback,
            })
            if res.status != "done":
                return None                           # 评估不可达 → 保守不拆
            result = res.response.get("result") or {}
            if not result.get("should_split"):
                return None
            subs = self._normalize_subtasks(result.get("sub_tasks") or [], task)
            bad = self._validate_subtasks(subs, team)
            if not bad:
                return subs
            feedback = [bad]
            self.store.append_run_event(iid, "split_rejected", {"reason": bad})
        return None                                   # 重试耗尽 → 原样执行（不阻断）

    def _normalize_subtasks(self, subs: list[dict], parent: dict) -> list[dict]:
        """加父前缀防撞名（仿 _prefix_cycle）；空 agent/task_type 回填父任务值；
        子任务内部依赖只引用同组兄弟 id，一并加前缀。"""
        pid = parent["id"]
        out: list[dict] = []
        for s in subs:
            out.append({
                "id": f"{pid}.{s['id']}",
                "name": s.get("name", ""),
                "agent": s.get("agent") or parent.get("agent", ""),
                "task_type": s.get("task_type") or parent.get("task_type", ""),
                "description": s.get("description", ""),
                "reviewer": s.get("reviewer", ""),
                "dependencies": [f"{pid}.{d}" for d in (s.get("dependencies") or [])],
            })
        return out

    def _validate_subtasks(self, subs: list[dict], team: set[str]) -> str:
        """委托给 check_plan（加扇出上限），兼容旧返回格式（空串=通过）。"""
        return check_plan(subs, team,
                          max_fanout=self.config.max_subtasks).feedback

    def _splice(self, result: dict[str, dict], parent: dict, subs: list[dict]) -> None:
        """用 subs 替换 result 中的 parent：入口子任务（无组内依赖）继承父的上游依赖；
        原先依赖 parent 的外部任务改为依赖**全部**子任务（串行执行 → 零并行损失）。"""
        pid = parent["id"]
        parent_deps = list(parent.get("dependencies", []))
        sub_ids = [s["id"] for s in subs]
        for s in subs:
            if not s["dependencies"]:                 # 入口子任务：接上父的上游
                s["dependencies"] = list(parent_deps)
            result[s["id"]] = s
        del result[pid]
        for t in result.values():                     # 外部依赖重接：dep==pid → 全部子任务
            deps = t.get("dependencies", [])
            if pid in deps:
                t["dependencies"] = [d for d in deps if d != pid] + sub_ids

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
            planned = self._task_plan(project_id, goal, agents,
                                      cycle=cycle, prior_summary=prior_summary)
            if self.config.split_enabled:
                planned = self._expand_plan(project_id, planned, agents, cycle=cycle)
            tasks = _prefix_cycle(planned, cycle)
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
        base_dir = task_deliverable_base(project_id, tid, task_type)
        if is_code_project_task(task_type):
            task_project_dir(project_id, tid)
        rel_path = artifact_rel_path(tid, task_type)
        feedback: list[str] = []

        context = self._build_context(project_id, task) if self.config.inject_context else {}

        for attempt in range(1, self.config.max_gate_retries + 1):
            req = {
                "interaction_id": f"{project_id}:{tid}:execute:{attempt}",
                "kind": "execute", "project_id": project_id, "task_id": tid,
                "agent_id": agent, "intent": task.get("description", task.get("name", "")),
                "input": {
                    "task": task,
                    "deliverable_path": rel_path,
                    "deliverable_base": str(base_dir),
                },
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
                resp["meta"].setdefault("task_id", tid)
            gate_res = check_execute(resp, base_dir=str(base_dir),
                                     enforce_must_include=self.config.enforce_must_include)
            if gate_res.passed:
                status = self._quality_status(resp)
                if self.config.review_enabled:
                    status = self._peer_review(project_id, task, status, task_type, rel_path)
                self.store.set_task_status(project_id, tid, status)
                self._capture_summary(project_id, tid, resp, rel_path)
                if is_code_project_task(task_type):
                    proj = task_project_dir(project_id, tid)
                    self.store.update_task_meta(
                        project_id, tid,
                        artifacts=scan_project_dir(proj),
                        artifact_base="code_project",
                        ref=rel_path,
                    )
                self.store.append_run_event(req["interaction_id"], "gate_passed",
                                            {"final_status": status})
                return TaskOutcome(tid, status, "", attempt, resp)

            feedback = [f"[{f['rule']}] 期望：{f['expected']}；实际：{f['actual']}"
                        for f in gate_res.failures]
            self.store.append_run_event(req["interaction_id"], "gate_failed",
                                        {"failures": gate_res.failures})

        self.store.set_task_status(project_id, tid, "failed")
        return TaskOutcome(tid, "failed", "确定性门禁重试耗尽", self.config.max_gate_retries)

    def _settle_in_progress_task(self, project_id: str, task: dict) -> Optional[TaskOutcome]:
        """结算中断前已交卷但未入账的 execute（不重跑 agent）。"""
        tid = task["id"]
        exec_rows = [
            i for i in self.store.list_interactions(project_id)
            if i.get("task_id") == tid and i.get("kind") == "execute"
        ]
        if not exec_rows:
            return None
        latest = max(exec_rows, key=lambda i: (i.get("attempt") or 1, i.get("started_at") or ""))
        iid = latest["interaction_id"]
        agent = latest.get("agent_id") or task.get("agent", "")

        if latest.get("status") in ("pending", "running"):
            resp, resp_path = read_adoptable_response(agent, iid)
            if resp is None or resp_path is None:
                return None
            finalize_interaction(self.store, iid, resp_path, resp)
            self.store.append_run_event(iid, "resume_adopted", {"reason": "断点续跑回收响应"})
            latest = self.store.get_interaction(iid) or latest

        if latest.get("status") != "done":
            return None

        resp = self._load_interaction_response(latest)
        if resp is None:
            return None
        return self._apply_execute_gate(project_id, task, resp, latest.get("attempt") or 1,
                                        interaction_id=iid)

    def _load_interaction_response(self, interaction: dict) -> Optional[dict]:
        ref = interaction.get("response_ref")
        if ref:
            p = Path(ref)
            if p.is_file():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
        agent = interaction.get("agent_id") or ""
        resp, _ = read_adoptable_response(agent, interaction["interaction_id"])
        return resp

    def _apply_execute_gate(self, project_id: str, task: dict, resp: dict, attempt: int,
                            *, interaction_id: str) -> Optional[TaskOutcome]:
        tid = task["id"]
        task_type = task.get("task_type", "")
        base_dir = task_deliverable_base(project_id, tid, task_type)
        rel_path = artifact_rel_path(tid, task_type)
        resp = dict(resp)
        resp.setdefault("meta", {})
        if isinstance(resp["meta"], dict):
            resp["meta"].setdefault("task_type", task_type)
            resp["meta"].setdefault("task_id", tid)
        gate_res = check_execute(resp, base_dir=str(base_dir),
                                 enforce_must_include=self.config.enforce_must_include)
        if not gate_res.passed:
            return None
        status = self._quality_status(resp)
        if self.config.review_enabled:
            status = self._peer_review(project_id, task, status, task_type, rel_path)
        self.store.set_task_status(project_id, tid, status)
        self._capture_summary(project_id, tid, resp, rel_path)
        if is_code_project_task(task_type):
            proj = task_project_dir(project_id, tid)
            self.store.update_task_meta(
                project_id, tid,
                artifacts=scan_project_dir(proj),
                artifact_base="code_project",
                ref=rel_path,
            )
        self.store.append_run_event(interaction_id, "gate_passed", {"final_status": status})
        return TaskOutcome(tid, status, "", attempt, resp)

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
            "input": {
                "task": task,
                "deliverable_path": rel_path,
                "deliverable_base": str(task_deliverable_base(project_id, tid, task_type)),
                "acceptance_criteria": spec.acceptance_criteria if spec else [],
            },
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
