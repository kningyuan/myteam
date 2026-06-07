#!/usr/bin/env python3
"""Execute 任务流水线 — Gate 重试、质量判定、上游上下文注入。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from common.agent_port import AgentPort, finalize_interaction, read_adoptable_response
from common.gate import check_execute
from common.process_types import ProcessConfig, TaskOutcome
from common.project_artifacts import (
    artifact_rel_path,
    is_code_project_task,
    scan_project_dir,
    task_deliverable_base,
    task_project_dir,
)
from common.registry import get_spec
from common.store import Store


@dataclass
class TaskPipeline:
    store: Store
    port: AgentPort
    config: ProcessConfig
    release_files: Callable[[str, str], None]

    def run_task(self, project_id: str, task: dict) -> TaskOutcome:
        tid = task["id"]
        agent = self.store.get_task(project_id, tid).get("agent") or task.get("agent", "")
        task_type = task.get("task_type", "")
        base_dir = task_deliverable_base(project_id, tid, task_type)
        if is_code_project_task(task_type):
            task_project_dir(project_id, tid)
        rel_path = artifact_rel_path(tid, task_type)
        feedback: list[str] = []

        context = self.build_context(project_id, task) if self.config.inject_context else {}

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
                self.release_files(agent, req["interaction_id"])
                self.store.set_task_status(project_id, tid, "failed")
                return TaskOutcome(tid, "failed", f"端口 {res.status}: {res.reason}", attempt)

            resp = res.response
            resp.setdefault("meta", {})
            if isinstance(resp["meta"], dict):
                resp["meta"].setdefault("task_type", task_type)
                resp["meta"].setdefault("task_id", tid)
            gate_res = check_execute(resp, base_dir=str(base_dir),
                                     enforce_must_include=self.config.enforce_must_include)
            if gate_res.passed:
                outcome = self._finalize_success(
                    project_id, task, resp, attempt, rel_path, task_type,
                    interaction_id=req["interaction_id"], agent=agent,
                )
                return outcome

            feedback = [f"[{f['rule']}] 期望：{f['expected']}；实际：{f['actual']}"
                        for f in gate_res.failures]
            self.store.append_run_event(req["interaction_id"], "gate_failed",
                                        {"failures": gate_res.failures})
            self.release_files(agent, req["interaction_id"])

        self.store.set_task_status(project_id, tid, "failed")
        return TaskOutcome(tid, "failed", "确定性门禁重试耗尽", self.config.max_gate_retries)

    def settle_in_progress_task(self, project_id: str, task: dict) -> Optional[TaskOutcome]:
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

        resp = self.load_interaction_response(latest)
        if resp is None:
            return None
        return self.apply_execute_gate(project_id, task, resp, latest.get("attempt") or 1,
                                       interaction_id=iid)

    def load_interaction_response(self, interaction: dict) -> Optional[dict]:
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

    def apply_execute_gate(self, project_id: str, task: dict, resp: dict, attempt: int,
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
        agent = task.get("agent", "")
        return self._finalize_success(
            project_id, task, resp, attempt, rel_path, task_type,
            interaction_id=interaction_id, agent=agent,
        )

    def build_context(self, project_id: str, task: dict) -> dict:
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

    def capture_summary(self, project_id: str, tid: str, resp: dict, rel_path: str) -> None:
        quality = resp.get("quality") or {}
        outcome = (resp.get("result") or {}).get("outcome") or {}
        artifact = outcome.get("artifact") or {}
        summary = resp.get("notes") or quality.get("notes") or artifact.get("title") or ""
        self.store.update_task_meta(project_id, tid, summary=summary, ref=rel_path)

    def quality_status(self, resp: dict) -> str:
        q = resp.get("quality") or {}
        score = q.get("score")
        gaps = q.get("known_gaps") or []
        if gaps or (isinstance(score, (int, float)) and score < self.config.quality_floor):
            return "needs_review"
        return "completed"

    def peer_review(self, project_id: str, task: dict, status: str,
                    task_type: str, rel_path: str) -> str:
        tid = task["id"]
        reviewer = (self.store.get_task(project_id, tid) or {}).get("reviewer") \
            or task.get("reviewer", "")
        if not reviewer:
            return status
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
            self.release_files(reviewer, iid)
            self.store.append_run_event(iid, "review_unreachable", {"reason": res.reason})
            return "needs_review"
        result = res.response.get("result", {})
        passed = bool(result.get("passed"))
        self.store.append_run_event(iid, "review_done",
                                    {"passed": passed, "feedback": result.get("feedback", "")})
        self.release_files(reviewer, iid)
        return "completed" if passed else "needs_review"

    def _finalize_success(self, project_id: str, task: dict, resp: dict, attempt: int,
                          rel_path: str, task_type: str, *, interaction_id: str,
                          agent: str) -> TaskOutcome:
        tid = task["id"]
        status = self.quality_status(resp)
        if self.config.review_enabled:
            status = self.peer_review(project_id, task, status, task_type, rel_path)
        self.store.set_task_status(project_id, tid, status)
        self.capture_summary(project_id, tid, resp, rel_path)
        if is_code_project_task(task_type):
            proj = task_project_dir(project_id, tid)
            self.store.update_task_meta(
                project_id, tid,
                artifacts=scan_project_dir(proj),
                artifact_base="code_project",
                ref=rel_path,
            )
        self.store.append_run_event(interaction_id, "gate_passed",
                                    {"final_status": status})
        self.release_files(agent, interaction_id)
        return TaskOutcome(tid, status, "", attempt, resp)
