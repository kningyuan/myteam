#!/usr/bin/env python3
"""Execute 任务流水线 — Gate 重试、质量判定、上游上下文注入。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from common.agent_port import AgentPort, finalize_interaction, read_adoptable_response
from common.agent_transport import lookup_interaction_session
from common.gate import check_execute
from common.process_types import BudgetExceededError, ProcessConfig, TaskOutcome
from common.project_artifacts import (
    artifact_rel_path,
    is_code_project_task,
    scan_project_dir,
    task_deliverable_base,
    task_project_dir,
)
from common.deliverable_guarantee import (
    deliverable_abs_path,
    scaffold_markdown_deliverable,
    scaffold_process_artifacts,
)
from common.experience import promote_ledger_to_memory
from common.prompt_templates import render_execute_intent
from common.registry import get_spec
from common.store import Store

# 纯格式门禁失败：仅章节标题结构问题，可短 retry 修标题而不重写正文
_FORMAT_ONLY_RULES = frozenset({"section_level", "required_sections"})


def _is_pure_format_failure(failures: list[dict]) -> bool:
    return bool(failures) and all(f.get("rule") in _FORMAT_ONLY_RULES for f in failures)


def _port_fail_reason(status: str, detail: str) -> str:
    if status == "timed_out":
        return "timeout_idle"
    if status == "no_response":
        return "no_response"
    if status == "error":
        return "cli_error"
    if "门禁" in detail or "gate" in detail.lower():
        return "gate_exhausted"
    return status


def _resolve_deliverable_path(resp: dict, base_dir: Path) -> Optional[str]:
    outcome = (resp.get("result") or {}).get("outcome") or {}
    artifact = outcome.get("artifact") or {}
    rel_path = artifact.get("path", "")
    if not rel_path:
        return None
    p = Path(rel_path)
    if p.is_absolute():
        return str(p)
    return str(base_dir / rel_path)


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

        spec = get_spec(task_type)
        for attempt in range(1, self.config.max_gate_retries + 1):
            if attempt == 1:
                if not is_code_project_task(task_type):
                    scaffold_markdown_deliverable(
                        deliverable_abs_path(base_dir, rel_path, task_type),
                        spec,
                        title=task.get("name", tid),
                    )
                profile = spec.delivery_profile if spec else "none"
                if profile and profile != "none":
                    scaffold_process_artifacts(base_dir, profile)
            inp = {
                "task": task,
                "deliverable_path": rel_path,
                "deliverable_base": str(base_dir),
            }
            if spec and spec.acceptance_criteria:
                inp["acceptance_criteria"] = list(spec.acceptance_criteria)
            if attempt > 1:
                prev_sid = lookup_interaction_session(
                    self.store, f"{project_id}:{tid}:execute:{attempt - 1}",
                )
                if prev_sid:
                    inp["session_id"] = prev_sid
            req = {
                "interaction_id": f"{project_id}:{tid}:execute:{attempt}",
                "kind": "execute", "project_id": project_id, "task_id": tid,
                "agent_id": agent, "intent": render_execute_intent(task),
                "input": inp,
                "context": context,
                "response_schema": "execute.result@1.0",
                "constraints": {"task_type": task_type},
                "retry_feedback": feedback,
            }
            res = self.port.run(req)
            if res.status == "budget_exceeded":
                self.release_files(agent, req["interaction_id"])
                raise BudgetExceededError(res.reason or "交互级 token 超预算")
            if res.status != "done":
                self.release_files(agent, req["interaction_id"])
                self.store.set_task_status(project_id, tid, "failed")
                detail = f"端口 {res.status}: {res.reason}"
                self.store.update_task_meta(
                    project_id, tid,
                    fail_reason=_port_fail_reason(res.status, detail),
                    fail_detail=detail,
                )
                return TaskOutcome(tid, "failed", detail, attempt)

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
            if _is_pure_format_failure(gate_res.failures):
                dv_abs = _resolve_deliverable_path(resp, base_dir)
                if dv_abs:
                    feedback.append(f"上一轮交付物文件：{dv_abs}")
                feedback.append(
                    "请只调整 Markdown 标题结构以通过门禁，保留正文内容；"
                    "禁止重读仓库或重写内容。"
                )
            gf_payload: dict = {"failures": gate_res.failures}
            sid = inp.get("session_id") or lookup_interaction_session(
                self.store, req["interaction_id"],
            )
            if sid:
                gf_payload["session_id"] = sid
            self.store.append_run_event(req["interaction_id"], "gate_failed", gf_payload)
            self.release_files(agent, req["interaction_id"])

        self.store.set_task_status(project_id, tid, "failed")
        self.store.update_task_meta(
            project_id, tid,
            fail_reason="gate_exhausted",
            fail_detail="确定性门禁重试耗尽",
        )
        return TaskOutcome(tid, "failed", "确定性门禁重试耗尽", self.config.max_gate_retries)

    def settle_in_progress_task(self, project_id: str, task: dict) -> Optional[TaskOutcome]:
        """结算中断前已交卷但未入账的 execute（不重跑 agent）。"""
        tid = task["id"]
        row = self.store.get_task(project_id, tid) or {}
        task_st = row.get("status", "pending")
        if task_st in ("completed", "needs_review", "failed", "blocked"):
            return None  # 任务已终态，防双写

        exec_rows = [
            i for i in self.store.list_interactions(project_id)
            if i.get("task_id") == tid and i.get("kind") == "execute"
        ]
        if not exec_rows:
            return None
        latest = max(exec_rows, key=lambda i: (i.get("attempt") or 1, i.get("started_at") or ""))
        iid = latest["interaction_id"]
        agent = latest.get("agent_id") or task.get("agent", "")

        if latest.get("status") in ("pending", "running", "timed_out"):
            resp, resp_path = read_adoptable_response(agent, iid)
            if resp is None or resp_path is None:
                return None
            cur = self.store.get_interaction(iid)
            if not cur or cur.get("status") not in ("pending", "running", "timed_out"):
                return None  # interaction 已被其他路径结算
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
        base_dir = task_deliverable_base(project_id, tid, task_type)
        promote_ledger_to_memory(base_dir, project_id, tid, task_type, self.store)
        self.release_files(agent, interaction_id)
        return TaskOutcome(tid, status, "", attempt, resp)
