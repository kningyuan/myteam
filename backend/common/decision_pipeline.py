#!/usr/bin/env python3
"""决策类 Interaction 流水线 — team_config / task_plan / evaluate / triage。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from common.agent_bootstrap import auto_create_agent
from common.agent_id_policy import (
    normalize_agent_ids,
    normalize_plan_tasks,
    normalize_agent_id,
    partition_auto_create_candidates,
)
from common.agent_port import AgentPort
from common.plan_splice import normalize_subtasks, validate_subtasks
from common.plan_gate import check_plan
from common.process_types import BudgetExceededError, ProcessConfig
from common.paths import workspace_dir
from common.prompt_templates import render_kind_intent
from common.store import Store


@dataclass
class DecisionPipeline:
    store: Store
    port: AgentPort
    config: ProcessConfig
    release_files: Callable[[str, str], None]

    def team_config(self, project_id: str, goal: str) -> list[str]:
        iid = f"{project_id}:team_config"
        req = {
            "interaction_id": iid,
            "kind": "team_config", "project_id": project_id, "agent_id": "main",
            "intent": render_kind_intent("team_config", {"goal": goal}),
            "input": {"goal": goal},
            "response_schema": "team_config.result@1.0",
        }
        res = self.port.run(req)
        if res.status == "budget_exceeded":
            raise BudgetExceededError(res.reason or "交互级 token 超预算")
        if res.status != "done":
            raise RuntimeError(f"team_config 失败：{res.status} {res.reason}")
        agents = normalize_agent_ids(res.response["result"]["agents"])
        self.release_files("main", iid)

        missing = [a for a in agents if not workspace_dir(a).exists()]
        if missing and self.config.auto_create_agents:
            allowed, rejected = partition_auto_create_candidates(missing)
            if rejected:
                raise RuntimeError(
                    f"team_config 返回未注册 agent，禁止 auto_create：{', '.join(rejected)}")
            if allowed:
                self.store.append_run_event(f"{project_id}:team_config", "auto_create_agents",
                                            {"agent_ids": allowed})
            for aid in allowed:
                auto_create_agent(aid, description=f"自动创建的 agent：{aid}",
                                  backend=self.config.default_backend,
                                  model=self.config.default_model)
        elif missing and not self.config.auto_create_agents:
            raise RuntimeError(
                f"team_config 返回了未就绪的 agent（auto_create_agents=False）：{missing}")

        return agents

    def task_plan(self, project_id: str, goal: str, agents: list[str], *,
                  cycle: int = 0, prior_summary: str = "") -> list[dict]:
        agents = normalize_agent_ids(agents)
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
                "intent": render_kind_intent("task_plan", {
                    "goal": goal,
                    "team": ", ".join(agents),
                }),
                "input": plan_input,
                "response_schema": "task_plan.result@1.0",
                "retry_feedback": feedback,
            }
            res = self.port.run(req)
            if res.status == "budget_exceeded":
                self.release_files("main", iid)
                raise BudgetExceededError(res.reason or "交互级 token 超预算")
            if res.status != "done":
                self.release_files("main", iid)
                raise RuntimeError(f"task_plan 失败：{res.status} {res.reason}")
            tasks = normalize_plan_tasks(res.response["result"]["tasks"])
            check = check_plan(tasks, team)
            if check.passed:
                self.release_files("main", iid)
                return tasks
            feedback = [check.feedback]
            self.store.append_run_event(iid, "plan_rejected", {"reason": check.feedback})
            self.release_files("main", iid)
        raise RuntimeError(
            f"task_plan 校验失败（重试 {self.config.max_plan_retries} 次仍未通过）：{feedback[0]}")

    def evaluate(self, project_id: str, task: dict, agents: list[str],
                 depth: int, *, cycle: int = 0) -> Optional[list[dict]]:
        agents = normalize_agent_ids(agents)
        team = set(agents)
        feedback: list[str] = []
        base_iid = f"{project_id}:{task['id']}:evaluate" + (f":c{cycle}" if cycle else "")
        for attempt in range(1, self.config.max_plan_retries + 1):
            iid = base_iid + ("" if attempt == 1 else f":{attempt}")
            res = self.port.run({
                "interaction_id": iid, "kind": "evaluate",
                "project_id": project_id, "task_id": task["id"],
                "agent_id": task.get("agent", ""),
                "intent": render_kind_intent("evaluate", {}),
                "input": {"task": task, "depth": depth,
                          "max_depth": self.config.max_split_depth,
                          "max_subtasks": self.config.max_subtasks, "team": agents},
                "response_schema": "evaluate.result@1.0",
                "retry_feedback": feedback,
            })
            agent = task.get("agent", "")
            if res.status != "done":
                self.release_files(agent, iid)
                return None
            result = res.response.get("result") or {}
            if not result.get("should_split"):
                self.release_files(agent, iid)
                return None
            subs = normalize_subtasks(result.get("sub_tasks") or [], task)
            bad = validate_subtasks(subs, team, max_fanout=self.config.max_subtasks)
            if not bad:
                self.release_files(agent, iid)
                return subs
            feedback = [bad]
            self.store.append_run_event(iid, "split_rejected", {"reason": bad})
            self.release_files(agent, iid)
        return None

    def triage(self, project_id: str, task: dict, reason: str) -> str:
        tid = task["id"]
        row = self.store.get_task(project_id, tid) or {}
        meta = row.get("meta") or {}
        req = {
            "interaction_id": f"{project_id}:{tid}:triage",
            "kind": "triage", "project_id": project_id, "task_id": tid,
            "agent_id": "main", "intent": f"任务 {tid} 失败，请决策",
            "input": {
                "task": task,
                "reason": reason,
                "fail_reason": meta.get("fail_reason", ""),
                "fail_detail": meta.get("fail_detail", ""),
            },
            "response_schema": "triage.result@1.0",
        }
        res = self.port.run(req)
        if res.status != "done":
            self.release_files("main", req["interaction_id"])
            return "drop"
        result = res.response["result"]
        decision = result.get("decision", "drop")
        self.release_files("main", req["interaction_id"])
        if decision == "reassign" and result.get("target_agent"):
            target = normalize_agent_id(result["target_agent"])
            self.store.upsert_task(project_id, tid, agent=target,
                                   name=task.get("name", ""),
                                   task_type=task.get("task_type", ""),
                                   dependencies=task.get("dependencies", []))
            task["agent"] = target
        return decision
