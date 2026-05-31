#!/usr/bin/env python3
"""Task dispatch runner for continuous-executor.

Ports task-executor DISPATCH_LOOP (evaluate → execute → QG → review) without
modifying task-executor. continuous_context is injected via host.build_execute_trigger_extras().
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.config import (
    POLL_INTERVAL,
    ACK_TIMEOUT,
    TASK_TIMEOUT,
    EVALUATE_TIMEOUT,
    MAX_RETRIES,
    MAX_EVALUATE_RETRIES,
    MAX_EXECUTE_RETRIES,
    NOTIFY_EVENT_TIMEOUT,
    PROJECT_DATA_CMD_TIMEOUT,
    SUBPROCESS_TIMEOUT,
)
from common.task_data_store import (
    deliverables_dir,
    get_task_description,
    get_task_info,
    get_task_name,
    get_task_status,
    journal_append,
    journal_clear,
    read_task_data,
    reset_task,
    response_dir,
    trigger_dir,
    update_task_status,
    write_task_data,
)
from common.response_finder import find_response_file
from common.validator import (
    generate_feedback,
    validate_deliverable_file,
    validate_evaluation_response,
    validate_execution_response,
)
from common.deliverable_merger import merge_subtask_deliverables

import engine as _engine


class TaskDispatchRunner:
    """Full task-executor-style dispatch loop, hosted by ContinuousExecutor."""

    def __init__(self, host, send_project_complete: bool = False):
        self.host = host
        self.send_project_complete = send_project_complete

    @property
    def project_id(self) -> str:
        return self.host.project_id

    def log(self, msg: str, level: str = "info"):
        self.host.log(msg, level)

    def log_fail(self, step: str, detail: str, extra: str = ""):
        self.host.log_fail(step, detail, extra)

    def state_quality_gate(self, *args, **kwargs):
        return self.host.state_quality_gate(*args, **kwargs)

    def state_review(self, *args, **kwargs):
        return self.host.state_review(*args, **kwargs)

    def _notify_task_event(self, event_type: str, agent_id: str, task_id: str, *extra_args, **kwargs):
        self.host._notify_task_event(event_type, agent_id, task_id, *extra_args, **kwargs)

    def _notify_subtask_event(
        self, event_type: str, agent_id: str, parent_task_id: str, subtask_id: str, sub_task_index=0
    ):
        notify_script = str(_engine.SKILLS / "notify-telegram" / "scripts" / "notify.py")
        if not Path(notify_script).exists():
            self.log("[DISPATCH_NOTIFY_TELEGRAM_SCRIPT_NOT_FOUND]", "warning")
            return
        rc, _, stderr = _engine._run_script(
            notify_script, self.project_id, event_type, agent_id, parent_task_id, subtask_id,
            timeout=NOTIFY_EVENT_TIMEOUT,
        )
        if rc != 0:
            self.log(f"[DISPATCH_NOTIFY_TELEGRAM_FAIL] event={event_type}, stderr={stderr[:200]}", "warning")

    def run(self) -> bool:
        """Run dispatch loop until queue is empty."""
        queue_script = _engine._script("task-queue/scripts/task_queue.py")
        loop_count = 0

        while True:
            loop_count += 1

            rc, stdout, stderr = _engine._run_script(queue_script, "status", self.project_id)
            if rc != 0:
                self.log_fail(
                    "DISPATCH_QUEUE_STATUS_FAIL",
                    f"检查队列状态失败：{stderr}",
                    f"project_id={self.project_id}, loop={loop_count}",
                )
                return False

            status = stdout.strip()
            self.log(f"[DISPATCH_QUEUE_STATUS] loop={loop_count}, status={status}")

            if status.startswith("running:"):
                task_id = status.split(":", 1)[1]
                self.log(f"[DISPATCH_WAITING] task_id={task_id} 正在执行，等待完成")
                task_info = get_task_info(self.project_id, task_id)
                if not self._wait_task_complete(task_id, task_info):
                    self.log_fail(
                        "DISPATCH_WAIT_FAIL",
                        f"任务 {task_id} 执行失败",
                        f"project_id={self.project_id}, loop={loop_count}",
                    )
                    return False
                continue

            rc, stdout, stderr = _engine._run_script(queue_script, "next", self.project_id)
            if rc != 0:
                self.log_fail(
                    "DISPATCH_NEXT_TASK_FAIL",
                    f"获取下一个任务失败：{stderr}",
                    f"project_id={self.project_id}, loop={loop_count}",
                )
                return False

            next_task = stdout.strip()
            if next_task == "none":
                self.log(f"[DISPATCH_LOOP_END] 所有任务已完成, loop={loop_count}")
                if self.send_project_complete:
                    _engine._notify_event("project_complete", "", self.project_id, "")
                break

            if ":" in next_task:
                parent_id = next_task.split(":", 1)[0]
                if get_task_info(self.project_id, parent_id):
                    self.log(f"[DISPATCH_PARENT_RESOLVE] from={next_task} → parent={parent_id}")
                    next_task = parent_id

            self.log(f"[DISPATCH_NEXT_TASK] task_id={next_task}, loop={loop_count}")

            task_info = get_task_info(self.project_id, next_task)
            if not task_info:
                self.log_fail(
                    "DISPATCH_TASK_INFO_NOT_FOUND",
                    f"任务信息未找到：{next_task}",
                    f"project_id={self.project_id}",
                )
                return False

            agent_id = task_info.get("agent", "")
            task_name = task_info.get("name", next_task)
            self.log(f"[DISPATCH_TASK_INFO] task_id={next_task}, name={task_name}, agent={agent_id}")

            self.log(f"[DISPATCH_EVALUATE_START] task_id={next_task}, agent={agent_id}")
            evaluation_result = self.state_evaluate_task(next_task, agent_id)
            if evaluation_result is None:
                self.log_fail(
                    "DISPATCH_EVALUATE_FAIL",
                    f"评估阶段失败：{next_task}",
                    f"agent={agent_id}, project_id={self.project_id}",
                )
                return False
            self.log(
                f"[DISPATCH_EVALUATE_END] task_id={next_task}, "
                f"should_split={evaluation_result.get('should_split')}"
            )

            if evaluation_result.get("should_split") and evaluation_result.get("sub_tasks"):
                sub_tasks = evaluation_result["sub_tasks"]
                self.log(f"[DISPATCH_SUBTASK_LOOP_START] parent_task={next_task}, sub_count={len(sub_tasks)}")

                for i, sub_task in enumerate(sub_tasks):
                    sub_task_id = sub_task.get("id")
                    sub_index = f"{i + 1}/{len(sub_tasks)}"
                    sub_name = sub_task.get("name", sub_task_id)
                    self.log(
                        f"[DISPATCH_SUBTASK_START] task_id={sub_task_id}, name={sub_name}, progress={sub_index}"
                    )
                    journal_append(self.project_id, "subtask_start", next_task, sub_task_id)
                    success = self.state_execute_task(
                        sub_task_id, agent_id, parent_task=next_task, sub_task_index=sub_index
                    )
                    if not success:
                        self.log_fail(
                            "DISPATCH_SUBTASK_FAIL",
                            f"子任务 {sub_task_id} 执行失败",
                            f"parent={next_task}, agent={agent_id}, progress={sub_index}",
                        )
                        return False
                    journal_clear(self.project_id)
                    self.log(f"[DISPATCH_SUBTASK_END] task_id={sub_task_id}, progress={sub_index}")

                parent_status = get_task_status(self.project_id, next_task)
                if parent_status != "completed":
                    self._update_task_via_cli(next_task, "completed")
                    self._notify_task_event("task_complete", agent_id, next_task)
                    self._run_cleanup(agent_id, next_task)
                    self.log(f"[DISPATCH_PARENT_COMPLETED] task_id={next_task}, sub_count={len(sub_tasks)}")
            else:
                self.log(f"[DISPATCH_EXECUTE_START] task_id={next_task}, agent={agent_id}, has_subtasks=false")
                self._notify_task_event("task_start", agent_id, next_task)
                success = self.state_execute_task(next_task, agent_id)
                if not success:
                    self.log_fail(
                        "DISPATCH_EXECUTE_FAIL",
                        f"任务 {next_task} 执行失败",
                        f"agent={agent_id}, project_id={self.project_id}",
                    )
                    return False
                self.log(f"[DISPATCH_EXECUTE_END] task_id={next_task}")

            ti = get_task_info(self.project_id, next_task) or {}
            task_type = ti.get("task_type", ti.get("type", ""))
            reviewer = task_info.get("reviewer", "")
            deliverable_path = ti.get("deliverable_path", "")
            summary = ti.get("summary", "")

            if not deliverable_path:
                subs = ti.get("subtasks", [])
                done = [s for s in subs if s.get("status") == "completed"]
                if done:
                    merged = merge_subtask_deliverables(self.project_id, next_task)
                    if merged:
                        deliverable_path = merged
                    summary = summary or "、".join(s.get("name", "") for s in done)
                    self.log(
                        f"[DISPATCH_REVIEW_PARENT_FALLBACK] task_id={next_task}, "
                        f"merged {len(done)} subtask deliverables"
                    )

            if task_type:
                gate_passed = self.state_quality_gate(next_task, task_type, deliverable_path)
                if not gate_passed:
                    continue

                self._notify_task_event("quality_gate_passed", agent_id, next_task)

                if reviewer and gate_passed:
                    if not self.state_review(next_task, reviewer, deliverable_path, summary):
                        continue
                    self._notify_task_event("review_passed", reviewer, next_task)
            else:
                self.log(f"[DISPATCH_QUALITY_GATE_SKIPPED] task_id={next_task}, reason=无 task_type")

            self.log(f"[DISPATCH_TASK_COMPLETED] task_id={next_task}, loop={loop_count}")

        return True

    def _wait_task_complete(self, task_id: str, task_info: dict = None) -> bool:
        self.log(f"[DISPATCH_WAIT_TASK] task_id={task_id}, timeout={TASK_TIMEOUT}s")
        deadline = time.time() + TASK_TIMEOUT
        retry_count = 0

        while time.time() < deadline:
            task_data = read_task_data(self.project_id)
            current = None
            for t in task_data.get("tasks", []):
                if t["id"] == task_id:
                    current = t
                    break

            if not current:
                self.log_fail(
                    "DISPATCH_WAIT_TASK_NOT_FOUND",
                    f"任务 {task_id} 不存在",
                    f"project_id={self.project_id}",
                )
                return False

            if current.get("status") == "completed":
                self.log(f"[DISPATCH_WAIT_COMPLETED] task_id={task_id}")

                if task_info:
                    deliverables = list(deliverables_dir(self.project_id).glob(f"{task_id}_*"))
                    if deliverables:
                        for dv in deliverables:
                            reqs = task_info.get("validation", {}) or {
                                "min_length": 200,
                                "required_sections": [],
                                "required_elements": [],
                            }
                            result = validate_deliverable_file(str(dv), reqs)
                            if not result.passed:
                                if retry_count < MAX_RETRIES:
                                    retry_count += 1
                                    reset_task(self.project_id, task_id)
                                    break
                                self.log_fail(
                                    "DISPATCH_WAIT_MAX_RETRIES",
                                    f"验证失败超过 {MAX_RETRIES} 次",
                                    f"task_id={task_id}",
                                )
                                return False
                return True

            if current.get("status") == "failed":
                reason = current.get("failure_reason", "")
                self.log_fail(
                    "DISPATCH_WAIT_TASK_FAILED",
                    f"任务 {task_id} 失败：{reason}",
                    f"project_id={self.project_id}",
                )
                return False

            time.sleep(POLL_INTERVAL)

        self.log_fail(
            "DISPATCH_WAIT_TIMEOUT",
            f"任务 {task_id} 超时（{TASK_TIMEOUT}s）",
            f"project_id={self.project_id}",
        )
        return False

    def state_evaluate_task(self, task_id: str, agent_id: str) -> Optional[dict]:
        self.log(f"[DISPATCH_EVALUATE_TASK] task_id={task_id}, agent={agent_id}")

        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        trigger_data = {
            "phase": "evaluate",
            "project_id": self.project_id,
            "task_id": task_id,
            "task_name": get_task_name(self.project_id, task_id),
            "description": get_task_description(self.project_id, task_id),
            "agent": agent_id,
            "created_at": datetime.now().isoformat(),
        }
        trigger_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")

        notify_script = _engine._script("agent-notify/scripts/notify_agent.py")
        rc, _, stderr = _engine._run_script(
            notify_script, "evaluate", self.project_id, task_id, agent_id,
            "--ack-timeout", str(ACK_TIMEOUT),
            timeout=ACK_TIMEOUT + 30,
        )
        if rc != 0:
            self.log_fail(
                "DISPATCH_EVALUATE_NOTIFY_FAIL",
                f"通知评估失败：{stderr}",
                f"task_id={task_id}, agent={agent_id}",
            )
            return None

        resp_path = response_dir(agent_id) / f"{self.project_id}_{task_id}.response"
        deadline = time.time() + EVALUATE_TIMEOUT
        retry_count = 0

        while time.time() < deadline:
            found_resp = find_response_file(
                self.project_id, agent_id, task_id, expected_phase="evaluate"
            )
            if found_resp:
                try:
                    response = json.loads(found_resp.read_text(encoding="utf-8"))
                    result = validate_evaluation_response(response, task_id)
                    if not result.passed:
                        if retry_count < MAX_EVALUATE_RETRIES:
                            retry_count += 1
                            feedback = self._generate_evaluate_feedback(result.failures, task_id)
                            self._retry_evaluate(agent_id, task_id, feedback, retry_count)
                            continue
                        self.log(
                            f"[DISPATCH_EVALUATE_FALLBACK] retry_exceeded, no split task_id={task_id}",
                            "warning",
                        )
                        return {"should_split": False, "sub_tasks": []}

                    should_split = response.get("should_split", False)
                    sub_tasks = response.get("sub_tasks", [])

                    if should_split and sub_tasks:
                        self._add_sub_tasks(task_id, agent_id, sub_tasks)
                        self._notify_task_event("task_split", agent_id, task_id, str(len(sub_tasks)))
                        for sub_task in sub_tasks:
                            sub_task_id = sub_task.get("id")
                            if sub_task_id:
                                self._notify_subtask_event(
                                    "subtask_created", agent_id, task_id, sub_task_id
                                )
                        self._update_task_via_cli(task_id, "in_progress")
                    return {"should_split": should_split, "sub_tasks": sub_tasks}

                except (json.JSONDecodeError, OSError) as e:
                    self.log(f"[DISPATCH_EVALUATE_READ_FAIL] task_id={task_id}, error={e}", "warning")
                    if resp_path.exists():
                        resp_path.unlink()

            time.sleep(POLL_INTERVAL)

        self.log_fail(
            "DISPATCH_EVALUATE_TIMEOUT",
            f"评估超时（{EVALUATE_TIMEOUT}s）",
            f"task_id={task_id}, agent={agent_id}",
        )
        return None

    def _add_sub_tasks(self, parent_task_id: str, agent_id: str, sub_tasks: list):
        data = read_task_data(self.project_id)
        now = datetime.now().isoformat()
        parent_task = None
        for t in data.get("tasks", []):
            if t["id"] == parent_task_id:
                parent_task = t
                break
        if not parent_task:
            raise Exception(f"父任务 {parent_task_id} 不存在")

        if "subtasks" not in parent_task:
            parent_task["subtasks"] = []

        for st in sub_tasks:
            st_id = st.get("id")
            if not st_id:
                continue
            if any(existing.get("id") == st_id for existing in parent_task.get("subtasks", [])):
                continue
            parent_task["subtasks"].append({
                "id": st_id,
                "name": st.get("name", ""),
                "description": st.get("description", ""),
                "agent": agent_id,
                "task_type": parent_task.get("task_type", ""),
                "reviewer": parent_task.get("reviewer", agent_id),
                "status": "pending",
                "dependencies": st.get("dependencies", []),
                "parent_task": parent_task_id,
                "timeout_minutes": parent_task.get("timeout_minutes"),
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "completed_at": None,
            })

        parent_task["updated_at"] = now
        write_task_data(self.project_id, data)

    def _retry_evaluate(self, agent_id: str, task_id: str, feedback: str, retry_count: int):
        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        if trigger_path.exists():
            trigger_data = json.loads(trigger_path.read_text(encoding="utf-8"))
            trigger_data["retry_feedback"] = feedback
            trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")

        notify_script = _engine._script("agent-notify/scripts/notify_agent.py")
        try:
            _engine._run_script(
                notify_script, "evaluate", self.project_id, task_id, agent_id,
                "--ack-timeout", str(ACK_TIMEOUT), timeout=ACK_TIMEOUT + 30,
            )
        except subprocess.TimeoutExpired:
            self.log(f"[DISPATCH_EVALUATE_RETRY_TIMEOUT] task_id={task_id}", "warning")

    def _generate_evaluate_feedback(self, failures: list, task_id: str) -> str:
        feedback = "你的响应未通过验证，请重新生成。\n\n"
        feedback += "【要求】只输出 JSON，不要包含任何其他文字、markdown 代码块或解释。\n\n"
        feedback += "验证失败项:\n"
        for f in failures:
            feedback += f"- {f}\n"
        return feedback

    def state_execute_task(
        self,
        task_id: str,
        agent_id: str,
        parent_task: Optional[str] = None,
        sub_task_index: Optional[str] = None,
    ) -> bool:
        if get_task_status(self.project_id, task_id) == "completed":
            self.log(f"[DISPATCH_EXECUTE_SKIP] task_id={task_id} already completed")
            return True

        task_info = get_task_info(self.project_id, task_id) or {}
        dv_dir = deliverables_dir(self.project_id)
        deliverable_path = str(dv_dir / f"{task_id}_deliverable.md")
        task_type = task_info.get("task_type", "")
        deliverable_template, check_rules = _engine._read_deliverable_template(task_type)
        standard_requirements = {
            "required_sections": check_rules.get("required_sections", []),
            "must_include_keywords": check_rules.get("must_include", []),
            "min_length": check_rules.get("min_length", 0),
        }

        trigger_data = {
            "phase": "execute",
            "project_id": self.project_id,
            "task_id": task_id,
            "task_name": task_info.get("name", ""),
            "description": task_info.get("description", ""),
            "agent": agent_id,
            "parent_task": parent_task,
            "sub_task_index": sub_task_index,
            "deliverable_path": deliverable_path,
            "task_type": task_type,
            "template": deliverable_template,
            "standard_requirements": standard_requirements,
            "created_at": datetime.now().isoformat(),
        }
        if hasattr(self.host, "build_execute_trigger_extras"):
            trigger_data.update(self.host.build_execute_trigger_extras(task_info))

        update_task_status(self.project_id, task_id, "in_progress")

        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        trigger_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")

        if parent_task:
            self._notify_subtask_event("subtask_start", agent_id, parent_task, task_id)

        notify_script = _engine._script("agent-notify/scripts/notify_agent.py")
        args = ["execute", self.project_id, task_id, agent_id, "--ack-timeout", str(ACK_TIMEOUT)]
        if parent_task:
            args.extend(["--parent", parent_task])
        if sub_task_index:
            args.extend(["--index", sub_task_index])

        try:
            rc, _, stderr = _engine._run_script(notify_script, *args, timeout=ACK_TIMEOUT + 30)
            if rc != 0:
                self.log_fail(
                    "DISPATCH_EXECUTE_NOTIFY_FAIL",
                    f"通知执行失败：{stderr}",
                    f"task_id={task_id}, agent={agent_id}",
                )
                return False
        except subprocess.TimeoutExpired:
            self.log_fail(
                "DISPATCH_EXECUTE_NOTIFY_TIMEOUT",
                "通知超时（150s），agent 无响应",
                f"task_id={task_id}, agent={agent_id}",
            )
            return False

        resp_dir = response_dir(agent_id)
        resp_path = resp_dir / f"{self.project_id}_{task_id}.response"
        for stale in resp_dir.glob(f"{self.project_id}_{task_id}*"):
            if stale.name != resp_path.name:
                try:
                    stale.unlink()
                except OSError:
                    pass

        task_timeout_sec = (task_info.get("timeout_minutes") or 30) * 60
        deadline = time.time() + task_timeout_sec
        retry_count = 0

        while time.time() < deadline:
            found_resp = find_response_file(
                self.project_id, agent_id, task_id, expected_phase="execute"
            )
            if found_resp:
                try:
                    response = json.loads(found_resp.read_text(encoding="utf-8"))

                    if "raw_response" in response and "status" not in response:
                        raw = response.get("raw_response", "")
                        dv_match = re.search(r"`([^`]+_deliverable\.md)`", raw)
                        dv_from_raw = dv_match.group(1) if dv_match else ""
                        actual_dv = (
                            dv_from_raw
                            if (dv_from_raw and Path(dv_from_raw).exists())
                            else deliverable_path
                        )
                        response["status"] = (
                            "completed" if (actual_dv and Path(actual_dv).exists()) else "failed"
                        )
                        response["deliverable_path"] = actual_dv
                        response["summary"] = raw[:500]
                        response["phase"] = "execute"
                        response["task_id"] = task_id

                    if "runId" in response and "status" not in response:
                        result_data = response.get("result", {})
                        meta = result_data.get("meta", {}) if isinstance(result_data, dict) else {}
                        prompt_text = meta.get("finalPromptText", "") if isinstance(meta, dict) else ""
                        dv_match = re.search(r"`([^`]+_deliverable\.md)`", prompt_text)
                        dv_from_prompt = dv_match.group(1) if dv_match else ""
                        actual_dv = (
                            dv_from_prompt
                            if (dv_from_prompt and Path(dv_from_prompt).exists())
                            else deliverable_path
                        )
                        response["status"] = (
                            "completed" if (actual_dv and Path(actual_dv).exists()) else "failed"
                        )
                        response["deliverable_path"] = actual_dv
                        response["summary"] = (response.get("summary", "") or "")[:500]

                    result = validate_execution_response(response, task_id, deliverable_path)
                    if not result.passed:
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            reset_task(self.project_id, task_id)
                            feedback = self._generate_execute_feedback(result.failures, task_id)
                            self._retry_execute(
                                agent_id, task_id, parent_task, sub_task_index, feedback
                            )
                            continue
                        if parent_task:
                            self._notify_subtask_event(
                                "subtask_failed", agent_id, parent_task, task_id, sub_task_index
                            )
                        return False

                    dv_path = Path(deliverable_path)
                    resp_dv = response.get("deliverable_path", "")
                    if resp_dv and Path(resp_dv).exists():
                        dv_path = Path(resp_dv)

                    if not dv_path.exists():
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            reset_task(self.project_id, task_id)
                            continue
                        if parent_task:
                            self._notify_subtask_event(
                                "subtask_failed", agent_id, parent_task, task_id, sub_task_index
                            )
                        return False

                    reqs = task_info.get("validation", {}) or {
                        "min_length": 200,
                        "required_sections": [],
                        "required_elements": [],
                    }
                    dv_result = validate_deliverable_file(str(dv_path), reqs)
                    if not dv_result.passed:
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            reset_task(self.project_id, task_id)
                            feedback = self._generate_execute_feedback(dv_result.failures, task_id)
                            self._retry_execute(
                                agent_id, task_id, parent_task, sub_task_index, feedback
                            )
                            continue
                        if parent_task:
                            self._notify_subtask_event(
                                "subtask_failed", agent_id, parent_task, task_id, sub_task_index
                            )
                        return False

                    if parent_task:
                        update_task_status(self.project_id, task_id, "completed")
                        self._notify_subtask_event("subtask_complete", agent_id, parent_task, task_id)
                    else:
                        self._update_task_via_cli(task_id, "completed")

                    self._run_cleanup(agent_id, task_id)
                    return True

                except (json.JSONDecodeError, OSError) as e:
                    self.log(f"[DISPATCH_EXECUTE_READ_FAIL] {e}", "warning")
                    if resp_path.exists():
                        resp_path.unlink()

            time.sleep(POLL_INTERVAL)

        self.log(f"[DISPATCH_EXECUTE_TIMEOUT] task_id={task_id}", "error")
        return False

    def _retry_execute(
        self,
        agent_id: str,
        task_id: str,
        parent_task: Optional[str],
        sub_task_index: Optional[str],
        feedback: str,
    ):
        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        if trigger_path.exists():
            trigger_data = json.loads(trigger_path.read_text(encoding="utf-8"))
            trigger_data["retry_feedback"] = feedback
            trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")

        notify_script = _engine._script("agent-notify/scripts/notify_agent.py")
        args = ["execute", self.project_id, task_id, agent_id, "--ack-timeout", str(ACK_TIMEOUT)]
        if parent_task:
            args.extend(["--parent", parent_task])
        if sub_task_index:
            args.extend(["--index", sub_task_index])
        try:
            _engine._run_script(notify_script, *args, timeout=ACK_TIMEOUT + 30)
        except subprocess.TimeoutExpired:
            self.log(f"[DISPATCH_EXECUTE_RETRY_TIMEOUT] task_id={task_id}", "warning")

    def _generate_execute_feedback(self, failures: list, task_id: str) -> str:
        feedback = "你的响应未通过验证，请重新生成。\n\n"
        feedback += "【要求】只输出 JSON，不要包含任何其他文字、markdown 代码块或解释。\n\n"
        feedback += "验证失败项:\n"
        for f in failures:
            feedback += f"- {f}\n"
        return feedback

    def _update_task_via_cli(self, task_id: str, status: str):
        script = _engine._script("project-data/scripts/project_data.py")
        rc, _, stderr = _engine._run_script(
            script, "update-task", self.project_id, task_id, status,
            timeout=PROJECT_DATA_CMD_TIMEOUT,
        )
        if rc != 0:
            self.log(
                f"[DISPATCH_UPDATE_VIA_CLI_FAIL] task_id={task_id}, stderr={stderr[:200]}",
                "warning",
            )

    def _run_cleanup(self, agent_id: str, task_id: str):
        script = str(_engine.SKILLS / "task-cleanup" / "scripts" / "cleanup.py")
        if not Path(script).exists():
            return
        _engine._run_script(script, self.project_id, agent_id, task_id, timeout=30)
