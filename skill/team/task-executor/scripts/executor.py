#!/usr/bin/env python3
"""Task Executor - 流程引擎

控制团队协作项目的标准执行流程。固定状态机，确保流程 100% 准确。
Agent 只负责执行具体任务和提供决策输入。

状态机：
  INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP → COMPLETE
  DISPATCH_LOOP 内部: evaluate → execute → QUALITY_GATE → REVIEW → loop
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

# 使用 team-ok 的公共模块
TEAM_OK_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TEAM_OK_DIR))
from common.config import (
    POLL_INTERVAL,
    ACK_TIMEOUT,
    TASK_TIMEOUT,
    EVALUATE_TIMEOUT,
    EXECUTE_TIMEOUT,
    MAX_RETRIES,
    MAX_EVALUATE_RETRIES,
    MAX_EXECUTE_RETRIES,
    NOTIFY_AGENT_TIMEOUT,
    TEAM_CONFIG_TIMEOUT,
    TEAM_CONFIG_MAX_RETRIES,
    TASK_PLAN_TIMEOUT,
    TASK_PLAN_MAX_RETRIES,
    NOTIFY_EVENT_TIMEOUT,
    PROJECT_DATA_CMD_TIMEOUT,
    SUBPROCESS_TIMEOUT,
)
from common.logger import get_skill_logger, log_skill_step_failure
from common.quality_gate import QualityGate, run_quality_gate
from common.cross_review import run_cross_review
from common.deliverable_merger import merge_subtask_deliverables
from common.task_data_store import (
    deliverables_dir,
    get_task_description,
    get_task_info,
    get_task_name,
    get_task_status,
    is_pid_alive,
    journal_append,
    journal_clear,
    mark_task_failed,
    project_dir,
    read_task_data,
    reset_task,
    response_dir,
    task_data_path,
    trigger_dir,
    update_task_status,
    write_task_data,
)
# 别名：兼容测试中的 _read_task_data / _write_task_data 引用
_read_task_data = read_task_data
_write_task_data = write_task_data
_project_dir = project_dir
from common.response_finder import clear_task_response_files, find_response_file
from common.resume_engine import resume_task_data
from common.validator import (
    ValidationResult,
    generate_feedback,
    validate_deliverable_file,
    validate_output,
    validate_task_plan,
    validate_team_config,
    validate_evaluation_response,
    validate_execution_response,
)

from common.paths import PROJECTS_DIR, TEAM_OK_DIR, templates_file
from common.agent_registry import format_registry_for_prompt
from common.skill_settings import is_auto_group_enabled
from common.contracts import contracts_enabled as _contracts_enabled

SKILLS = TEAM_OK_DIR

# 本地交付物模板文件路径
TEMPLATES_FILE = templates_file()


# 配置
TEAM_OK = True             # 标记为 team-ok 模式
SUB_TASK_ID_PREFIX = "sub_"  # 子任务 ID 前缀（executor 生成）


def _script(path: str) -> str:
    """返回 team-ok 下脚本的绝对路径。"""
    return str(SKILLS / path)


def _read_deliverable_template(task_type: str) -> tuple[dict, dict]:
    """从本地 templates.yaml 读取任务类型的交付物模板和校验规则。

    Returns:
        (deliverable_template, check_rules)  — 不存在或出错时返回两个空 dict
    """
    if not yaml:
        return {}, {}
    if not TEMPLATES_FILE.exists():
        return {}, {}
    try:
        with open(TEMPLATES_FILE, encoding="utf-8") as f:
            all_templates = yaml.safe_load(f)
        if not isinstance(all_templates, dict):
            return {}, {}
        task_cfg = all_templates.get(task_type, {})
        if not isinstance(task_cfg, dict):
            return {}, {}
        return (
            task_cfg.get("deliverable_template", {}),
            task_cfg.get("check_rules", {}),
        )
    except (yaml.YAMLError, OSError, AttributeError) as e:
        print(f"[TEMPLATE_READ_FAIL] task_type={task_type}, error={e}", file=sys.stderr)
        return {}, {}


def _run_script(script: str, *args, timeout: int = SUBPROCESS_TIMEOUT) -> tuple[int, str, str]:
    """运行一个脚本，返回 (returncode, stdout, stderr)。"""
    cmd = [sys.executable, script] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _notify_agent(
    event: str, agent_id: str, project_id: str, task_id: str = "", payload: dict = None
) -> bool:
    """通知 Agent，返回是否成功。"""
    script = _script("agent-notify/scripts/notify_agent.py")
    args = [event, project_id]
    if task_id:
        args.append(task_id)
    args.append(agent_id)
    rc, stdout, stderr = _run_script(script, *args, timeout=NOTIFY_AGENT_TIMEOUT)
    return rc == 0


# ============================================================================
# 状态机核心
# ============================================================================


class Executor:
    """流程引擎，控制团队协作项目的完整执行流程。"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.logger = get_skill_logger(project_id)
        self.state = "INIT"
        self.team: list[str] = []
        self.tasks: list[dict] = []
        self.retry_counts: dict[str, int] = {}
        self.quality_gate_retries: dict[str, int] = {}

    def log(self, msg: str, level: str = "info"):
        """统一日志入口，写入 skill-logs/skills.log。"""
        getattr(self.logger, level)(f"[EXECUTOR] {msg}", extra={"skill_name": "EXECUTOR"})

    def log_fail(self, step: str, detail: str, extra_text: str = ""):
        """写入失败日志并记录到全局错误日志。"""
        self.log(f"[{step}] {detail}", "error")
        log_skill_step_failure(self.project_id, "EXECUTOR", step, detail, extra_text)

    def try_resume(self, project_name: str) -> bool:
        """尝试恢复已中断的项目：按名称查找 project_id，释放队列，重置卡住的任务。"""
        projects_dir = PROJECTS_DIR
        if not projects_dir.exists():
            return False

        found_id = None
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            json_path = proj_dir / "task_data.json"
            if not json_path.exists():
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if data.get("project", {}).get("name") == project_name:
                    found_id = data["project"]["id"]
                    break
            except (json.JSONDecodeError, OSError):
                continue

        if not found_id:
            return False

        self.project_id = found_id
        self.logger = get_skill_logger(found_id)
        self.log(f"[EXECUTOR_RESUME_START] project_id={found_id}")

        # 释放队列锁（队列文件不存在也继续）
        queue_script = _script("task-queue/scripts/task_queue.py")
        rc, stdout, stderr = _run_script(queue_script, "release", found_id)
        if rc != 0:
            self.log(f"[EXECUTOR_RESUME_RELEASE_FAIL] project_id={found_id}, stderr={stderr[:100]}", "warning")

        # 读取任务数据并恢复（清理 journal、去重子任务、重置卡住状态）
        task_data = resume_task_data(found_id)
        if task_data is not None:
            write_task_data(found_id, task_data)
            self.log(f"[EXECUTOR_RESUME_TASKS_RESET] project_id={found_id}")
        else:
            self.log(f"[EXECUTOR_RESUME_NO_CHANGES] project_id={found_id}")

        self.log(f"[EXECUTOR_RESUME_OK] project_id={found_id}")
        return True

    def state_init(self, project_name: str, description: str) -> bool:
        """创建项目。"""
        self.project_description = description
        self.log(f"[EXECUTOR_INIT_START] project_name={project_name}")

        script = _script("project-init/scripts/init.py")
        rc, stdout, stderr = _run_script(script, project_name, description)

        if rc != 0:
            self.log_fail("EXECUTOR_INIT_FAIL",
                          f"项目创建失败：{stderr}",
                          f"project_name={project_name}, rc={rc}")
            return False

        # 从 stdout 最后一行读取 project_id
        lines = stdout.strip().split("\n")
        pid = lines[-1].strip() if lines else ""
        if pid and pid.startswith("pro_"):
            self.project_id = pid
            # 项目 ID 确定后，重建 logger 以写入正确目录
            self.logger = get_skill_logger(pid)
            self.log(f"[EXECUTOR_INIT_END] project_id={self.project_id}")
            return True

        self.log_fail("EXECUTOR_INIT_FAIL",
                      f"无法解析 project_id：{stdout}",
                      f"project_name={project_name}")
        return False

    # ------------------------------------------------------------------
    # 状态 2: TEAM_CONFIG - 请求 Main Agent 配置团队
    # ------------------------------------------------------------------

    def state_team_config(self) -> bool:
        """请求 Main Agent 配置团队。"""
        self.log(f"[EXECUTOR_TEAM_CONFIG_START] project_id={self.project_id}")

        # 创建请求文件
        req_dir = response_dir("main")
        req_dir.mkdir(parents=True, exist_ok=True)
        req_file = req_dir / f"{self.project_id}_team_config.request"

        request = {
            "event": "request_team_config",
            "project_id": self.project_id,
            "message": (
                "请根据以下项目描述，返回参与项目的 worker agent 列表。\n"
                "基于项目类型和需求推断需要的角色，不需要局限于描述中出现的词。\n\n"
                + format_registry_for_prompt(workers_only=True)
                + "\n\n规则：严格按照下方 JSON 格式返回，不要包含其他文字，不要用 markdown 包裹。\n"
                "agent 名称必须是英文小写 id。\n"
                "不要包含 main（协调者自动参与）。\n\n"
                "项目描述：\n"
                + (self.project_description if hasattr(self, "project_description") else "")
            ),
            "expected_format": {
                "agents": ["agent_1", "agent_2"]
            },
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        self.log(f"[EXECUTOR_TEAM_CONFIG_REQUEST] file={req_file}")

        # 通知 Main Agent
        notify_ok = _notify_agent("team_config", "main", self.project_id, payload=request)
        if not notify_ok:
            self.log(f"[EXECUTOR_TEAM_CONFIG_NOTIFY_FAIL] main_agent_notify_failed", "warning")

        # 等待 Main Agent 返回团队配置
        resp_file = req_dir / f"{self.project_id}_team_config.response"
        deadline = time.time() + TEAM_CONFIG_TIMEOUT

        self.log(f"[EXECUTOR_TEAM_CONFIG_WAIT] timeout={TEAM_CONFIG_TIMEOUT}s")
        retry_count = 0
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    self.log(f"[EXECUTOR_TEAM_CONFIG_JSON_FAIL] invalid JSON in response", "warning")
                    resp_file.unlink()
                    continue

                result = validate_team_config(response)
                if result.passed:
                    self.team = response.get("agents", [])
                    self.log(f"[EXECUTOR_TEAM_CONFIG_SUCCESS] agents={','.join(self.team)}")
                    self._persist_team_and_group()
                    return True
                else:
                    retry_count += 1
                    self.log(f"[EXECUTOR_TEAM_CONFIG_VALIDATE_FAIL] retry={retry_count}, failures={result.failures}", "warning")

                    # 重试超过 2 次后，停止任务
                    if retry_count >= TEAM_CONFIG_MAX_RETRIES:
                        self.log_fail("EXECUTOR_TEAM_CONFIG_FAIL",
                                      f"团队配置验证失败：{result.failures}",
                                      f"project_id={self.project_id}")
                        return False

                    # 重新通知 Main，附上验证失败信息
                    request["retry_feedback"] = result.failures
                    with open(req_file, "w", encoding="utf-8") as f:
                        json.dump(request, f, ensure_ascii=False, indent=2)
                    _notify_agent("team_config", "main", self.project_id, payload=request)
                    self.log(f"[EXECUTOR_TEAM_CONFIG_RETRY] retry_feedback_sent")

            time.sleep(POLL_INTERVAL)

        self.log_fail("EXECUTOR_TEAM_CONFIG_TIMEOUT",
                      "等待团队配置超时",
                      f"project_id={self.project_id}, timeout={TEAM_CONFIG_TIMEOUT}s")
        return False

    def _persist_team_and_group(self) -> None:
        """将团队写入 task_data，并自动创建/同步 myteam 项目协作群。"""
        try:
            data = read_task_data(self.project_id)
            data.setdefault("project", {})["agents"] = list(self.team)
            write_task_data(self.project_id, data)
            pname = data.get("project", {}).get("name", self.project_id)
        except Exception as e:
            self.log(f"[EXECUTOR_TEAM_PERSIST_WARN] {e}", "warning")
            pname = self.project_id

        if not is_auto_group_enabled():
            return
        try:
            from bridge.myteam_notify import setup_project_group

            ok, msg = setup_project_group(self.project_id, self.team, project_name=pname)
            if ok:
                self.log(f"[EXECUTOR_PROJECT_GROUP] {msg}")
            else:
                self.log(f"[EXECUTOR_PROJECT_GROUP_FAIL] {msg}", "warning")
        except Exception as e:
            self.log(f"[EXECUTOR_PROJECT_GROUP_FAIL] {e}", "warning")

    # ------------------------------------------------------------------
    # 状态 3: TASK_PLAN - 请求 Main Agent 规划任务
    # ------------------------------------------------------------------

    def state_task_plan(self) -> bool:
        """请求 Main Agent 规划任务列表和依赖关系。"""
        self.log(f"[EXECUTOR_TASK_PLAN_START] project_id={self.project_id}, team_count={len(self.team)}")

        req_dir = response_dir("main")
        req_file = req_dir / f"{self.project_id}_task_plan.request"

        request = {
            "event": "request_task_plan",
            "project_id": self.project_id,
            "team": self.team,
                        "message": (
                "请为团队中的 agent 规划任务列表和依赖关系。\n\n"
                "规则：\n"
                "1. 每个任务必须分配给团队中已有的 agent（当前团队成员：" + "、".join(self.team) + "）\n"
                "2. 禁止分配给不在以上团队成员列表中的角色\n"
                "3. 严格按照下方 JSON 格式返回，不要包含其他文字，不要用 markdown 包裹\n"
                "4. task id 格式为 task_001, task_002...\n\n"
                "【agent 角色 → task_type 映射】根据 agent 角色选择对应的产出类型标准：\n"
                "- product → prd（需求分析文档：背景与目标、需求描述、验收标准、范围界定）\n"
                "- developer → code-deliverable（代码交付物：方案设计、实现说明、测试覆盖）\n"
                "- tester → test-plan（测试计划：测试范围、测试用例、正常/边界/异常路径）\n"
                "- researcher → research（调研报告：调研背景、调研方法、核心发现、结论建议）\n"
                "- consultation → strategy（策略建议：问题定义、方案对比、推荐方案、风险评估）\n"
                "- content → content（内容文案：目标读者、内容框架、正文内容、来源引用）\n"
                "- seo → seo-plan（SEO 方案：关键词策略、技术优化、内容优化、效果预期）\n"
                "- docs → docs（技术文档：文档目标、内容结构、使用说明、更新日志）\n"
                "- designer → design-review（设计方案：一致性、可访问性、响应式）\n"
                "- coordinator → task-handoff（交接文档：交接摘要、交付物清单、依赖关系）\n"
            ),
            "expected_format": {
                "tasks": [
                    {
                        "id": "task_001",
                        "name": "任务名称",
                        "agent": "researcher",
                        "task_type": "research | strategy | prd | code-deliverable | test-plan | content | seo-plan | docs | design-review | task-handoff",
                        "reviewer": "tester | developer | coordinator | product | consultation | seo | docs | main",
                        "description": "任务描述",
                        "dependencies": [],
                    }
                ]
            },
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        self.log(f"[EXECUTOR_TASK_PLAN_REQUEST] file={req_file}")

        _notify_agent("task_plan", "main", self.project_id, payload=request)

        resp_file = req_dir / f"{self.project_id}_task_plan.response"
        deadline = time.time() + TASK_PLAN_TIMEOUT

        self.log(f"[EXECUTOR_TASK_PLAN_WAIT] timeout={TASK_PLAN_TIMEOUT}s")
        retry_count = 0
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    self.log(f"[EXECUTOR_TASK_PLAN_JSON_FAIL] invalid JSON in response", "warning")
                    resp_file.unlink()
                    continue

                result = validate_task_plan(response, self.team)
                if result.passed:
                    self.tasks = response.get("tasks", [])
                    task_ids = [t.get("id", "?") for t in self.tasks]
                    self.log(f"[EXECUTOR_TASK_PLAN_SUCCESS] task_count={len(self.tasks)}, tasks={','.join(task_ids)}")
                    return True
                else:
                    retry_count += 1
                    self.log(f"[EXECUTOR_TASK_PLAN_VALIDATE_FAIL] retry={retry_count}, failures={result.failures}", "warning")

                    # 重试超过 3 次后，停止任务
                    if retry_count >= TASK_PLAN_MAX_RETRIES:
                        self.log_fail("EXECUTOR_TASK_PLAN_FAIL",
                                      f"任务规划验证失败：{result.failures}",
                                      f"project_id={self.project_id}, team={self.team}")
                        return False

                    request["retry_feedback"] = result.failures
                    with open(req_file, "w", encoding="utf-8") as f:
                        json.dump(request, f, ensure_ascii=False, indent=2)
                    _notify_agent("task_plan", "main", self.project_id, payload=request)
                    self.log(f"[EXECUTOR_TASK_PLAN_RETRY] retry_feedback_sent")

            time.sleep(POLL_INTERVAL)

        self.log_fail("EXECUTOR_TASK_PLAN_TIMEOUT",
                      "等待任务规划超时",
                      f"project_id={self.project_id}, timeout={TASK_PLAN_TIMEOUT}s")
        return False

    # ------------------------------------------------------------------
    # 状态 3.5: ADD_TASKS - 将规划的任务写入项目
    # ------------------------------------------------------------------

    def state_add_tasks(self) -> bool:
        """将 Main Agent 规划的任务写入项目。"""
        self.log(f"[EXECUTOR_ADD_TASKS_START] project_id={self.project_id}, task_count={len(self.tasks)}")

        script = _script("project-data/scripts/project_data.py")
        added_ids = []

        for task in self.tasks:
            deps = ",".join(task.get("dependencies", []))
            task_id = task.get("id", "?")
            task_type = task.get("task_type", "")
            reviewer = task.get("reviewer", "")
            args_list = [
                script, "add-task",
                self.project_id,
                task["name"],
                task.get("agent", ""),
                task.get("description", ""),
                deps,
            ]
            if task_type:
                args_list.extend(["--task-type", task_type])
            if reviewer:
                args_list.extend(["--reviewer", reviewer])
            rc, stdout, stderr = _run_script(*args_list)
            if rc != 0:
                self.log_fail("EXECUTOR_ADD_TASKS_FAIL",
                              f"添加任务失败：{task['name']} - {stderr}",
                              f"task_id={task_id}, agent={task.get('agent','')}")
                return False
            added_ids.append(task_id)
            self.log(f"[EXECUTOR_TASK_ADDED] task_id={task_id}, name={task['name']}, agent={task.get('agent','')}")

        # 确认项目
        rc, stdout, stderr = _run_script(script, "confirm", self.project_id)
        if rc != 0:
            self.log_fail("EXECUTOR_CONFIRM_FAIL",
                          f"确认项目失败：{stderr}",
                          f"project_id={self.project_id}, added_tasks={','.join(added_ids)}")
            return False

        self.log(f"[EXECUTOR_ADD_TASKS_END] project_id={self.project_id}, tasks={','.join(added_ids)}")
        return True

    # ------------------------------------------------------------------
    # 状态 4: DISPATCH_LOOP - 循环调度任务
    # ------------------------------------------------------------------

    def state_dispatch_loop(self) -> bool:
        """循环调度任务，直到所有任务完成（新架构：评估→执行）。"""
        self.log(f"[EXECUTOR_DISPATCH_LOOP_START] project_id={self.project_id}")

        queue_script = _script("task-queue/scripts/task_queue.py")
        loop_count = 0

        while True:
            loop_count += 1

            # 1. 检查队列状态
            rc, stdout, stderr = _run_script(
                queue_script, "status", self.project_id
            )
            if rc != 0:
                self.log_fail("EXECUTOR_QUEUE_STATUS_FAIL",
                              f"检查队列状态失败：{stderr}",
                              f"project_id={self.project_id}, loop={loop_count}")
                return False

            status = stdout.strip()
            self.log(f"[EXECUTOR_QUEUE_STATUS] loop={loop_count}, status={status}")

            # 如果队列正在运行，等待
            if status.startswith("running:"):
                task_id = status.split(":", 1)[1]
                self.log(f"[EXECUTOR_WAITING] task_id={task_id} 正在执行，等待完成")
                if not self._wait_task_complete(task_id):
                    self.log_fail("EXECUTOR_WAIT_FAIL",
                                  f"任务 {task_id} 执行失败",
                                  f"project_id={self.project_id}, loop={loop_count}")
                    return False
                continue

            # 2. 获取下一个任务
            rc, stdout, stderr = _run_script(queue_script, "next", self.project_id)
            if rc != 0:
                self.log_fail("EXECUTOR_NEXT_TASK_FAIL",
                              f"获取下一个任务失败：{stderr}",
                              f"project_id={self.project_id}, loop={loop_count}")
                return False

            next_task = stdout.strip()
            if next_task == "none":
                self.log(f"[EXECUTOR_DISPATCH_LOOP_END] 所有任务已完成, loop={loop_count}")
                break

            # 处理 queue 返回的 parent:subtask 格式（如 task_001:task_001_2）
            if ":" in next_task:
                parent_id = next_task.split(":", 1)[0]
                parent_info = get_task_info(self.project_id, parent_id)
                if parent_info:
                    self.log(f"[EXECUTOR_NEXT_PARENT_RESOLVE] from={next_task} → parent={parent_id}")
                    next_task = parent_id

            self.log(f"[EXECUTOR_NEXT_TASK] task_id={next_task}, loop={loop_count}")

            # 3. 获取任务信息
            task_info = get_task_info(self.project_id, next_task)
            if not task_info:
                self.log_fail("EXECUTOR_TASK_INFO_NOT_FOUND",
                              f"任务信息未找到：{next_task}",
                              f"project_id={self.project_id}")
                return False

            agent_id = task_info.get("agent", "")
            task_name = task_info.get("name", next_task)
            self.log(f"[EXECUTOR_TASK_INFO] task_id={next_task}, name={task_name}, agent={agent_id}")

            # 4. 评估阶段：让 Worker 评估任务是否需要拆分
            self.log(f"[EXECUTOR_EVALUATE_START] task_id={next_task}, agent={agent_id}")
            evaluation_result = self.state_evaluate_task(next_task, agent_id)
            if evaluation_result is None:
                self.log_fail("EXECUTOR_EVALUATE_FAIL",
                              f"评估阶段失败：{next_task}",
                              f"agent={agent_id}, project_id={self.project_id}")
                return False
            self.log(f"[EXECUTOR_EVALUATE_END] task_id={next_task}, should_split={evaluation_result.get('should_split')}")

            # 5. 如果有子任务，循环执行子任务
            if evaluation_result.get("should_split") and evaluation_result.get("sub_tasks"):
                sub_tasks = evaluation_result["sub_tasks"]
                self.log(f"[EXECUTOR_SUBTASK_LOOP_START] parent_task={next_task}, sub_count={len(sub_tasks)}")

                for i, sub_task in enumerate(sub_tasks):
                    sub_task_id = sub_task.get("id")
                    sub_index = f"{i+1}/{len(sub_tasks)}"
                    sub_name = sub_task.get("name", sub_task_id)

                    self.log(f"[EXECUTOR_SUBTASK_START] task_id={sub_task_id}, name={sub_name}, progress={sub_index}")
                    # 写 journal 以便崩溃恢复时知道哪个子任务正在执行
                    journal_append(self.project_id, "subtask_start", next_task, sub_task_id)
                    success = self.state_execute_task(
                        sub_task_id, agent_id,
                        parent_task=next_task,
                        sub_task_index=sub_index
                    )
                    if not success:
                        self.log_fail("EXECUTOR_SUBTASK_FAIL",
                                      f"子任务 {sub_task_id} 执行失败",
                                      f"parent={next_task}, agent={agent_id}, progress={sub_index}")
                        return False
                    # 子任务完成后清理 journal（标记该点已安全到达）
                    journal_clear(self.project_id)
                    self.log(f"[EXECUTOR_SUBTASK_END] task_id={sub_task_id}, progress={sub_index}")

                # 所有子任务完成，标记父任务完成（如果还未完成）
                parent_status = get_task_status(self.project_id, next_task)
                if parent_status != "completed":
                    self._update_task_via_cli(next_task, "completed")
                    self._notify_task_event("task_complete", agent_id, next_task)
                    self._run_cleanup(agent_id, next_task)
                    self.log(f"[EXECUTOR_PARENT_COMPLETED] task_id={next_task}, sub_count={len(sub_tasks)}")

            else:
                # 无子任务，直接执行
                self.log(f"[EXECUTOR_EXECUTE_START] task_id={next_task}, agent={agent_id}, has_subtasks=false")
                self._notify_task_event("task_start", agent_id, next_task)
                success = self.state_execute_task(next_task, agent_id)
                if not success:
                    self.log_fail("EXECUTOR_EXECUTE_FAIL",
                                  f"任务 {next_task} 执行失败",
                                  f"agent={agent_id}, project_id={self.project_id}")
                    return False
                self.log(f"[EXECUTOR_EXECUTE_END] task_id={next_task}")

            # ── QUALITY GATE + REVIEW (per-task) ──
            # 从 task_data 获取 task_type、reviewer、交付物路径
            ti = get_task_info(self.project_id, next_task) or {}
            task_type = ti.get("task_type", ti.get("type", ""))
            reviewer = task_info.get("reviewer", "")

            # 获取交付物路径（从 task_data 的状态更新中读取）
            deliverable_path = ti.get("deliverable_path", "")
            summary = ti.get("summary", "")

            # 父任务：子任务已完成但父任务字段为空时，合并子任务交付物
            if not deliverable_path:
                subs = ti.get("subtasks", [])
                done = [s for s in subs if s.get("status") == "completed"]
                if done:
                    merged = merge_subtask_deliverables(self.project_id, next_task)
                    if merged:
                        deliverable_path = merged
                    summary = summary or "、".join(s.get("name", "") for s in done)
                    self.log(f"[EXECUTOR_REVIEW_PARENT_FALLBACK] task_id={next_task}, "
                             f"merged {len(done)} subtask deliverables")

            # 质量门禁：仅在 task_type 存在时执行
            if task_type:
                gate_passed = self.state_quality_gate(
                    next_task, task_type, deliverable_path,
                )
                if not gate_passed:
                    # 门禁失败（重试次数未耗尽时），重新调度该任务
                    continue  # 回到循环顶部重新调度

                # 质量门禁通过通知
                self._notify_task_event("quality_gate_passed", agent_id, next_task)

                # 交叉审核：仅在 reviewer 存在且门禁通过后执行
                if reviewer and gate_passed:
                    if not self.state_review(
                        next_task, reviewer, deliverable_path, summary,
                    ):
                        continue  # 审核未通过，重新调度
                    # 审核通过通知
                    self._notify_task_event("review_passed", reviewer, next_task)
            else:
                self.log(f"[EXECUTOR_QUALITY_GATE_SKIPPED] task_id={next_task}, reason=无 task_type")

            self.log(f"[EXECUTOR_TASK_COMPLETED] task_id={next_task}, loop={loop_count}")

        return True

    def _wait_task_complete(
        self, task_id: str, task_info: dict = None
    ) -> bool:
        """等待任务完成，验证结果，失败则重试。"""
        self.log(f"[EXECUTOR_WAIT_TASK] task_id={task_id}, timeout={TASK_TIMEOUT}s")
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
                self.log_fail("EXECUTOR_WAIT_TASK_NOT_FOUND",
                              f"任务 {task_id} 不存在",
                              f"project_id={self.project_id}")
                return False

            # 检查任务是否完成
            if current.get("status") == "completed":
                self.log(f"[EXECUTOR_WAIT_COMPLETED] task_id={task_id}")

                # 验证交付物
                if task_info:
                    # 查找交付物文件
                    task_name = task_info.get("name", task_id)
                    deliverables = list(
                        deliverables_dir(self.project_id).glob(f"{task_id}_*")
                    )

                    if not deliverables:
                        self.log(f"[EXECUTOR_WAIT_NO_DELIVERABLE] task_id={task_id}", "warning")
                    else:
                        for dv in deliverables:
                            self.log(f"[EXECUTOR_WAIT_CHECK_DV] file={dv.name}")
                            # 使用默认验证要求
                            reqs = task_info.get("validation", {})
                            if not reqs:
                                reqs = {
                                    "min_length": 200,
                                    "required_sections": [],
                                    "required_elements": [],
                                }
                            result = validate_deliverable_file(str(dv), reqs)
                            if not result.passed:
                                if retry_count < MAX_RETRIES:
                                    retry_count += 1
                                    self.log(
                                        f"[EXECUTOR_WAIT_DV_FAIL] task_id={task_id}, retry={retry_count}, failures={result.failures}",
                                        "warning",
                                    )
                                    # 通知 Agent 重试
                                    agent = task_info.get("agent", "")
                                    feedback = generate_feedback(
                                        result.failures, task_name
                                    )
                                    _notify_agent(
                                        "retry_task",
                                        agent,
                                        self.project_id,
                                        task_id,
                                        payload={
                                            "retry_count": retry_count,
                                            "retry_feedback": result.failures,
                                            "feedback": feedback,
                                        },
                                    )
                                    self.log(f"[EXECUTOR_WAIT_RETRY] task_id={task_id}, agent={agent}, retry={retry_count}")
                                    # 重置任务为 pending 等待重试
                                    reset_task(self.project_id, task_id)
                                    break  # 跳出 for 循环，重新等待
                                else:
                                    self.log_fail("EXECUTOR_WAIT_MAX_RETRIES",
                                                  f"验证失败超过 {MAX_RETRIES} 次",
                                                  f"task_id={task_id}")
                                    return False

                return True  # 验证通过

            # 检查任务是否失败
            if current.get("status") == "failed":
                reason = current.get('failure_reason', '')
                self.log_fail("EXECUTOR_WAIT_TASK_FAILED",
                              f"任务 {task_id} 失败：{reason}",
                              f"project_id={self.project_id}")
                return False

            time.sleep(POLL_INTERVAL)

        self.log_fail("EXECUTOR_WAIT_TIMEOUT",
                      f"任务 {task_id} 超时（{TASK_TIMEOUT}s）",
                      f"project_id={self.project_id}")
        return False

    def _reset_task(self, task_id: str):
        """将任务重置为 pending 状态（支持顶层任务和子任务）。"""
        self.log(f"[EXECUTOR_RESET_TASK] task_id={task_id}")
        try:
            data = read_task_data(self.project_id)
            now = datetime.now().isoformat()
            found = False

            for t in data.get("tasks", []):
                if t.get("id") == task_id:
                    if t.get("status") and not t.get("started_at"):
                        t["started_at"] = None
                    t["status"] = "pending"
                    t["updated_at"] = now
                    found = True
                    break
                for st in t.get("subtasks", []):
                    if st.get("id") == task_id:
                        st["status"] = "pending"
                        st["updated_at"] = now
                        if st.get("started_at"):
                            st["started_at"] = None
                        if st.get("completed_at"):
                            st["completed_at"] = None
                        found = True
                        break
                if found:
                    break

            if found:
                write_task_data(self.project_id, data)
                self.log(f"[EXECUTOR_RESET_TASK_OK] task_id={task_id}")
            else:
                self.log(f"[EXECUTOR_RESET_TASK_NOT_FOUND] task_id={task_id}", "warning")
        except Exception as e:
            self.log(f"[EXECUTOR_RESET_TASK_FAIL] task_id={task_id}, error={e}", "warning")

    # ------------------------------------------------------------------
    # 新增：评估阶段（EVALUATE）
    # ------------------------------------------------------------------

    def state_evaluate_task(self, task_id: str, agent_id: str) -> Optional[dict]:
        """让 Worker Agent 评估任务是否需要拆分。

        返回:
            如果 should_split=true: {"should_split": True, "sub_tasks": [...]}
            如果 should_split=false: {"should_split": False, "sub_tasks": []}
            如果失败: None
        """
        self.log(f"[EXECUTOR_EVALUATE_TASK] task_id={task_id}, agent={agent_id}")

        # Step 1: 创建评估触发文件
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
        self.log(f"[EXECUTOR_EVALUATE_TRIGGER] file={trigger_path}")

        cleared = clear_task_response_files(self.project_id, agent_id, task_id)
        if cleared:
            self.log(f"[EXECUTOR_EVALUATE_CLEAR] task_id={task_id}, removed={cleared}")

        # Step 2: 通知 Agent 评估（ACK 模式 - 短超时确认消息送达）
        notify_script = _script("agent-notify/scripts/notify_agent.py")
        rc, stdout, stderr = _run_script(
            notify_script, "evaluate", self.project_id, task_id, agent_id,
            "--ack-timeout", str(ACK_TIMEOUT),
            timeout=ACK_TIMEOUT + 30
        )
        if rc != 0:
            self.log_fail("EXECUTOR_EVALUATE_NOTIFY_FAIL",
                          f"通知评估失败：{stderr}",
                          f"task_id={task_id}, agent={agent_id}")
            return None
        self.log(f"[EXECUTOR_EVALUATE_NOTIFIED] agent={agent_id}, task_id={task_id}")

        # Step 3: 等待 response 文件
        resp_path = response_dir(agent_id) / f"{self.project_id}_{task_id}.response"
        deadline = time.time() + EVALUATE_TIMEOUT
        min_mtime = trigger_path.stat().st_mtime

        retry_count = 0
        while time.time() < deadline:
            found_resp = find_response_file(
                self.project_id, agent_id, task_id,
                expected_phase="evaluate", min_mtime=min_mtime,
            )
            if found_resp:
                try:
                    response = json.loads(found_resp.read_text(encoding="utf-8"))
                    self.log(f"[EXECUTOR_EVALUATE_RESPONSE] task_id={task_id}, should_split={response.get('should_split')}")

                    # Step 4: 验证响应
                    result = validate_evaluation_response(response, task_id)
                    if not result.passed:
                        self.log(f"[EXECUTOR_EVALUATE_VALIDATE_FAIL] task_id={task_id}, failures={result.failures}", "warning")
                        if retry_count < MAX_EVALUATE_RETRIES:
                            retry_count += 1
                            feedback = self._generate_evaluate_feedback(result.failures, task_id)
                            self._retry_evaluate(agent_id, task_id, feedback, retry_count)
                            continue
                        else:
                            self.log(f"[EXECUTOR_EVALUATE_FALLBACK] retry_exceeded, assuming no split for task_id={task_id}", "warning")
                            return {"should_split": False, "sub_tasks": []}

                    # Step 5: 验证通过
                    should_split = response.get("should_split", False)
                    sub_tasks = response.get("sub_tasks", [])

                    if should_split and sub_tasks:
                        self.log(f"[EXECUTOR_EVALUATE_SPLIT] task_id={task_id}, sub_count={len(sub_tasks)}")
                        # 添加子任务到项目
                        self._add_sub_tasks(task_id, agent_id, sub_tasks)
                        # 发送群通报
                        self._notify_task_event("task_split", agent_id, task_id, str(len(sub_tasks)))
                        # 发送子任务创建通知
                        for sub_task in sub_tasks:
                            sub_task_id = sub_task.get("id")
                            if sub_task_id:
                                self._notify_subtask_event("subtask_created", agent_id, task_id, sub_task_id)
                        # 更新父任务状态为 in_progress
                        self._update_task_via_cli(task_id, "in_progress")
                    else:
                        self.log(f"[EXECUTOR_EVALUATE_NO_SPLIT] task_id={task_id}")

                    return {"should_split": should_split, "sub_tasks": sub_tasks}

                except (json.JSONDecodeError, OSError) as e:
                    self.log(f"[EXECUTOR_EVALUATE_READ_FAIL] task_id={task_id}, error={e}", "warning")
                    if resp_path.exists():
                        resp_path.unlink()  # 删除损坏的文件，继续等待

            time.sleep(POLL_INTERVAL)

        self.log_fail("EXECUTOR_EVALUATE_TIMEOUT",
                      f"评估超时（{EVALUATE_TIMEOUT}s）",
                      f"task_id={task_id}, agent={agent_id}")
        return None

    def _add_sub_tasks(self, parent_task_id: str, agent_id: str, sub_tasks: list[dict]):
        """添加子任务到父任务的 subtasks 数组（直接读写 task_data.json）。"""
        self.log(f"[EXECUTOR_ADD_SUBTASKS_START] parent={parent_task_id}, count={len(sub_tasks)}")

        try:
            data = read_task_data(self.project_id)
            now = datetime.now().isoformat()

            # 查找父任务
            parent_task = None
            for t in data.get("tasks", []):
                if t["id"] == parent_task_id:
                    parent_task = t
                    break
            if not parent_task:
                raise Exception(f"父任务 {parent_task_id} 不存在")

            # 确保 subtasks 数组存在
            if "subtasks" not in parent_task:
                parent_task["subtasks"] = []

            for st in sub_tasks:
                st_id = st.get("id")
                if not st_id:
                    self.log(f"[SKIP] subtask without id: name={st.get('name', '?')}", "warning")
                    continue
                # 幂等：已存在的子任务跳过
                if any(existing.get("id") == st_id for existing in parent_task.get("subtasks", [])):
                    self.log(f"[SKIP] duplicate subtask id={st_id}", "warning")
                    continue
                subtask_entry = {
                    "id": st_id,
                    "name": st.get("name", ""),
                    "description": st.get("description", ""),
                    "agent": agent_id,
                    "task_type": parent_task.get("task_type", ""),  # 从父任务继承
                    "reviewer": parent_task.get("reviewer", agent_id),
                    "status": "pending",
                    "dependencies": st.get("dependencies", []),
                    "parent_task": parent_task_id,
                    "timeout_minutes": parent_task.get("timeout_minutes"),
                    "created_at": now,
                    "updated_at": now,
                    "started_at": None,
                    "completed_at": None,
                }
                parent_task["subtasks"].append(subtask_entry)
                self.log(f"[EXECUTOR_SUBTASK_ADDED] sub_task_id={subtask_entry['id']}, name={subtask_entry['name']}")

            parent_task["updated_at"] = now
            write_task_data(self.project_id, data)

            self.log(f"[EXECUTOR_ADD_SUBTASKS_END] parent={parent_task_id}, sub_count={len(sub_tasks)}")

        except Exception as e:
            self.log_fail("EXECUTOR_ADD_SUBTASKS_FAIL",
                          f"添加子任务失败: {e}",
                          f"parent={parent_task_id}")
            raise

    def _retry_evaluate(self, agent_id: str, task_id: str, feedback: str, retry_count: int):
        """重试评估通知。"""
        self.log(f"[EXECUTOR_EVALUATE_RETRY] task_id={task_id}, agent={agent_id}, attempt={retry_count}")

        # 更新 trigger 文件，加入反馈
        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        if trigger_path.exists():
            trigger_data = json.loads(trigger_path.read_text(encoding="utf-8"))
            trigger_data["retry_feedback"] = feedback
            trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.log(f"[EXECUTOR_EVALUATE_RETRY_TRIGGER] updated={trigger_path}")

        # 重新通知（ACK 模式）
        notify_script = _script("agent-notify/scripts/notify_agent.py")
        try:
            rc, _, _ = _run_script(notify_script, "evaluate", self.project_id, task_id, agent_id,
                                   "--ack-timeout", str(ACK_TIMEOUT), timeout=ACK_TIMEOUT + 30)
        except subprocess.TimeoutExpired:
            self.log(f"[EXECUTOR_EVALUATE_RETRY_TIMEOUT] task_id={task_id}, agent={agent_id}", "warning")
            return
        self.log(f"[EXECUTOR_EVALUATE_RETRY_NOTIFIED] task_id={task_id}, agent={agent_id}, rc={rc}")

    def _generate_evaluate_feedback(self, failures: list[str], task_id: str) -> str:
        """生成评估失败的反馈。"""
        feedback = "你的响应未通过验证，请重新生成。\n\n"
        feedback += "【要求】只输出 JSON，不要包含任何其他文字、markdown 代码块或解释。\n\n"
        feedback += f"验证失败项:\n"
        for f in failures:
            feedback += f"- {f}\n"
        return feedback

    # ------------------------------------------------------------------
    # 新增：执行阶段（EXECUTE）
    # ------------------------------------------------------------------

    def state_execute_task(self, task_id: str, agent_id: str, parent_task: Optional[str] = None, sub_task_index: Optional[str] = None) -> bool:
        """让 Worker Agent 执行任务。

        返回:
            True: 执行成功
            False: 执行失败
        """
        self.log(f"[EXECUTOR_EXECUTE_TASK] task_id={task_id}, agent={agent_id}" +
                 (f", parent={parent_task}, progress={sub_task_index}" if parent_task else ""))

        # 跳过已 completed 的任务（崩溃恢复后，已完成子任务无需重做）
        current_status = get_task_status(self.project_id, task_id)
        if current_status == "completed":
            self.log(f"[EXECUTOR_EXECUTE_SKIP] task_id={task_id} already completed, skipping")
            return True

        # Step 1: 创建执行触发文件
        task_info = get_task_info(self.project_id, task_id)
        dv_dir = deliverables_dir(self.project_id)
        deliverable_filename = f"{task_id}_deliverable.md"
        deliverable_path = str(dv_dir / deliverable_filename)

        # 获取 task_type 和本地模板（用于指导 agent 产出格式）
        task_type = task_info.get("task_type", "")
        deliverable_template, check_rules = _read_deliverable_template(task_type)
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

        # 记录开始时间戳（子任务和顶层任务均适用）
        update_task_status(self.project_id, task_id, "in_progress")

        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        trigger_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"[EXECUTOR_EXECUTE_TRIGGER] file={trigger_path}, deliverable={deliverable_path}")

        cleared = clear_task_response_files(self.project_id, agent_id, task_id)
        if cleared:
            self.log(f"[EXECUTOR_EXECUTE_CLEAR] task_id={task_id}, removed={cleared}")
        min_mtime = trigger_path.stat().st_mtime

        # Step 2: 子任务开始通知（在阻塞式 openclaw 调用之前发送，确保通知反映真实启动时机）
        if parent_task:
            self._notify_subtask_event("subtask_start", agent_id, parent_task, task_id)

        # Step 3: 通知 Agent 执行（ACK 模式 - 短超时确认消息送达）
        notify_script = _script("agent-notify/scripts/notify_agent.py")
        args = ["execute", self.project_id, task_id, agent_id,
                "--ack-timeout", str(ACK_TIMEOUT)]
        if parent_task:
            args.extend(["--parent", parent_task])
        if sub_task_index:
            args.extend(["--index", sub_task_index])

        try:
            rc, stdout, stderr = _run_script(notify_script, *args, timeout=ACK_TIMEOUT + 30)
            if rc != 0:
                self.log_fail("EXECUTOR_EXECUTE_NOTIFY_FAIL",
                              f"通知执行失败：{stderr}",
                              f"task_id={task_id}, agent={agent_id}")
                return False
        except subprocess.TimeoutExpired:
            self.log_fail("EXECUTOR_EXECUTE_NOTIFY_TIMEOUT",
                          f"通知超时（150s），agent 无响应",
                          f"task_id={task_id}, agent={agent_id}")
            return False
        self.log(f"[EXECUTOR_EXECUTE_NOTIFIED] agent={agent_id}, task_id={task_id}")

        # Step 5: 等待 response 文件（使用任务级超时）
        task_timeout_sec = (task_info.get("timeout_minutes") or 30) * 60
        deadline = time.time() + task_timeout_sec

        retry_count = 0
        while time.time() < deadline:
            found_resp = find_response_file(
                self.project_id, agent_id, task_id,
                expected_phase="execute", min_mtime=min_mtime,
            )
            if found_resp:
                try:
                    response = json.loads(found_resp.read_text(encoding="utf-8"))
                    self.log(f"[EXECUTOR_EXECUTE_RESPONSE] task_id={task_id}, status={response.get('status')}")

                    # 处理 raw_response（Agent 返回自然语言而非结构化 JSON）
                    # 迁移开关（D11/F1）：契约严格路径下不再做 raw_response 抢救。
                    if not _contracts_enabled() and "raw_response" in response and "status" not in response:
                        raw = response.get("raw_response", "")
                        self.log(f"[EXECUTOR_EXECUTE_RAW_RESPONSE] task_id={task_id}, raw_len={len(raw)}")
                        import re as _re
                        dv_match = _re.search(r'`([^`]+_deliverable\.md)`', raw)
                        dv_from_raw = dv_match.group(1) if dv_match else ""
                        actual_dv = dv_from_raw if (dv_from_raw and Path(dv_from_raw).exists()) else deliverable_path
                        response["status"] = "completed" if (actual_dv and Path(actual_dv).exists()) else "failed"
                        response["deliverable_path"] = actual_dv
                        response["summary"] = raw[:500]
                        # raw_response 中的 JSON 可能有不合法字符导致 json.loads 失败，
                        # 但我们可以从上下文知道 task_id 和 phase，直接补上。
                        response["phase"] = "execute"
                        response["task_id"] = task_id
                        self.log(f"[EXECUTOR_EXECUTE_RAW_RESOLVED] task_id={task_id}, status={response['status']}, dv={actual_dv}")

                    # 处理 OpenCode 适配器输出格式（runId / status / result 结构）
                    # 迁移开关（D11/F1）：契约严格路径下不再做 runId 抢救。
                    if not _contracts_enabled() and "runId" in response and "status" not in response:
                        raw = response.get("summary", "") or ""
                        self.log(f"[EXECUTOR_EXECUTE_OPENCODE_FORMAT] task_id={task_id}, raw_len={len(raw)}")
                        # 从 result.meta.finalPromptText 提取 deliverable 路径
                        result_data = response.get("result", {})
                        meta = result_data.get("meta", {}) if isinstance(result_data, dict) else {}
                        prompt_text = meta.get("finalPromptText", "") if isinstance(meta, dict) else ""
                        import re as _re
                        dv_match = _re.search(r'`([^`]+_deliverable\.md)`', prompt_text)
                        dv_from_prompt = dv_match.group(1) if dv_match else ""
                        actual_dv = dv_from_prompt if (dv_from_prompt and Path(dv_from_prompt).exists()) else deliverable_path
                        response["status"] = "completed" if (actual_dv and Path(actual_dv).exists()) else "failed"
                        response["deliverable_path"] = actual_dv
                        response["summary"] = raw[:500]
                        self.log(f"[EXECUTOR_EXECUTE_OPENCODE_RESOLVED] task_id={task_id}, status={response['status']}, dv={actual_dv}")

                    # Step 6: 验证响应
                    result = validate_execution_response(response, task_id, deliverable_path)
                    if not result.passed:
                        self.log(f"[EXECUTOR_EXECUTE_VALIDATE_FAIL] task_id={task_id}, failures={result.failures}", "warning")
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            # 重置任务状态，重新通知
                            reset_task(self.project_id, task_id)
                            feedback = self._generate_execute_feedback(result.failures, task_id)
                            self._retry_execute(agent_id, task_id, parent_task, sub_task_index, feedback)
                            continue
                        else:
                            self.log_fail("EXECUTOR_EXECUTE_FAIL",
                                          f"任务 {task_id} 执行失败：验证（重试耗尽）",
                                          f"agent={agent_id}, parent_task={parent_task}")
                            if parent_task:
                                self._notify_subtask_event("subtask_failed", agent_id, parent_task, task_id, sub_task_index)
                            return False

                    # Step 7: 验证 deliverable 文件
                    dv_path = Path(deliverable_path) if deliverable_path else None
                    if not dv_path or not dv_path.exists():
                        # Worker 可能使用了自定义路径
                        resp_dv = response.get("deliverable_path", "")
                        dv_path = Path(resp_dv) if resp_dv else None

                    if not dv_path or not dv_path.exists():
                        self.log(f"[EXECUTOR_EXECUTE_DELIVERABLE_MISSING] task_id={task_id}, path={deliverable_path}", "warning")
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            reset_task(self.project_id, task_id)
                            continue
                        else:
                            self.log_fail("EXECUTOR_EXECUTE_FAIL",
                                          f"任务 {task_id} 执行失败：交付物缺失（重试耗尽）",
                                          f"agent={agent_id}, parent_task={parent_task}")
                            if parent_task:
                                self._notify_subtask_event("subtask_failed", agent_id, parent_task, task_id, sub_task_index)
                            return False

                    # 使用默认验证要求
                    reqs = task_info.get("validation", {})
                    if not reqs:
                        reqs = {
                            "min_length": 200,
                            "required_sections": [],
                            "required_elements": [],
                        }
                    dv_result = validate_deliverable_file(str(dv_path), reqs)
                    if not dv_result.passed:
                        self.log(f"[EXECUTOR_EXECUTE_DELIVERABLE_VALIDATE_FAIL] task_id={task_id}, failures={dv_result.failures}", "warning")
                        if retry_count < MAX_EXECUTE_RETRIES:
                            retry_count += 1
                            reset_task(self.project_id, task_id)
                            feedback = self._generate_execute_feedback(dv_result.failures, task_id)
                            self._retry_execute(agent_id, task_id, parent_task, sub_task_index, feedback)
                            continue
                        else:
                            self.log_fail("EXECUTOR_EXECUTE_FAIL",
                                          f"任务 {task_id} 执行失败：交付物验证（重试耗尽）",
                                          f"agent={agent_id}, parent_task={parent_task}")
                            if parent_task:
                                self._notify_subtask_event("subtask_failed", agent_id, parent_task, task_id, sub_task_index)
                            return False

                    # Step 8: 验证通过，调用 skill 更新状态
                    if parent_task:
                        update_task_status(self.project_id, task_id, "completed")
                        self._notify_subtask_event("subtask_complete", agent_id, parent_task, task_id)
                    else:
                        self._update_task_via_cli(task_id, "completed")

                    self.log(f"任务 {task_id} 执行成功")
                    self._run_cleanup(agent_id, task_id)
                    return True

                except (json.JSONDecodeError, OSError) as e:
                    self.log(f"读取响应文件失败: {e}", "warning")
                    if resp_path.exists():
                        resp_path.unlink()

            time.sleep(POLL_INTERVAL)

        self.log(f"执行超时（{task_timeout_sec}s）", "error")
        return False

    def _retry_execute(self, agent_id: str, task_id: str, parent_task: Optional[str], sub_task_index: Optional[str], feedback: str):
        """重试执行通知。"""
        self.log(f"[EXECUTOR_EXECUTE_RETRY] task_id={task_id}, agent={agent_id}")

        # 更新 trigger 文件
        trigger_path = trigger_dir(agent_id) / f"{self.project_id}_{task_id}.trigger"
        if trigger_path.exists():
            trigger_data = json.loads(trigger_path.read_text(encoding="utf-8"))
            trigger_data["retry_feedback"] = feedback
            trigger_path.write_text(json.dumps(trigger_data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.log(f"[EXECUTOR_EXECUTE_RETRY_TRIGGER] updated={trigger_path}")

        # 重新通知（ACK 模式）
        notify_script = _script("agent-notify/scripts/notify_agent.py")
        args = ["execute", self.project_id, task_id, agent_id,
                "--ack-timeout", str(ACK_TIMEOUT)]
        if parent_task:
            args.extend(["--parent", parent_task])
        if sub_task_index:
            args.extend(["--index", sub_task_index])
        try:
            rc, _, _ = _run_script(notify_script, *args, timeout=ACK_TIMEOUT + 30)
        except subprocess.TimeoutExpired:
            self.log(f"[EXECUTOR_EXECUTE_RETRY_TIMEOUT] task_id={task_id}, agent={agent_id}", "warning")
            return
        self.log(f"[EXECUTOR_EXECUTE_RETRY_NOTIFIED] task_id={task_id}, agent={agent_id}, rc={rc}")

    def _generate_execute_feedback(self, failures: list[str], task_id: str) -> str:
        """生成执行失败的反馈。"""
        feedback = "你的响应未通过验证，请重新生成。\n\n"
        feedback += "【要求】只输出 JSON，不要包含任何其他文字、markdown 代码块或解释。\n\n"
        feedback += f"验证失败项:\n"
        for f in failures:
            feedback += f"- {f}\n"
        return feedback

    # ------------------------------------------------------------------
    # 新增辅助方法
    def _update_task_via_cli(self, task_id: str, status: str):
        """通过 project_data.py 更新任务状态（自带通知），用于顶层任务。"""
        script = _script("project-data/scripts/project_data.py")
        rc, stdout, stderr = _run_script(
            script, "update-task", self.project_id, task_id, status,
            timeout=PROJECT_DATA_CMD_TIMEOUT
        )
        if rc != 0:
            self.log(f"[EXECUTOR_UPDATE_VIA_CLI_FAIL] task_id={task_id}, status={status}, stderr={stderr[:200]}", "warning")

    def _notify_task_event(self, event_type: str, agent_id: str, task_id: str, *extra_args, **kwargs):
        """向 myteam 项目群发送任务事件通报。"""
        try:
            from bridge.myteam_notify import post_project_group_message

            feedback = kwargs.get("feedback", "")
            extra = feedback or " ".join(str(a) for a in extra_args if a is not None)
            ok, _ = post_project_group_message(
                self.project_id, event_type, agent_id or "", task_id or "", extra=extra,
            )
            if ok:
                self.log(f"[EXECUTOR_GROUP_NOTIFY_OK] event={event_type}, task={task_id}")
            else:
                self.log(f"[EXECUTOR_GROUP_NOTIFY_FAIL] event={event_type}, task={task_id}", "warning")
        except Exception as e:
            self.log(f"[EXECUTOR_GROUP_NOTIFY_FAIL] {e}", "warning")

    def _notify_subtask_event(self, event_type: str, agent_id: str, parent_task_id: str, subtask_id: str, sub_task_index: int = 0):
        """向 myteam 项目群发送子任务事件。"""
        try:
            from bridge.myteam_notify import post_project_group_message

            ok, _ = post_project_group_message(
                self.project_id, event_type, agent_id or "", subtask_id or "",
                extra=f"parent={parent_task_id}",
            )
            if ok:
                self.log(f"[EXECUTOR_GROUP_NOTIFY_OK] event={event_type}, subtask={subtask_id}")
        except Exception as e:
            self.log(f"[EXECUTOR_GROUP_NOTIFY_FAIL] {e}", "warning")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] [{event_type}] subtask={subtask_id}\n")

    def _run_cleanup(self, agent_id: str, task_id: str):
        """清理工作区文件（.trigger / .response）。"""
        script = str(SKILLS / "task-cleanup" / "scripts" / "cleanup.py")
        if not Path(script).exists():
            self.log(f"[EXECUTOR_CLEANUP_SCRIPT_NOT_FOUND] path={script}", "warning")
            return
        rc, stdout, stderr = _run_script(
            script, self.project_id, agent_id, task_id, timeout=30
        )
        if rc == 0:
            self.log(f"[EXECUTOR_CLEANUP_OK] task_id={task_id}, output={stdout[:60]}")
        else:
            self.log(f"[EXECUTOR_CLEANUP_FAIL] task_id={task_id}, stderr={stderr[:200]}", "warning")

    def _get_project_name(self) -> str:
        """获取项目名称。"""
        task_data = read_task_data(self.project_id)
        return task_data.get("project", {}).get("name", self.project_id)

    # ------------------------------------------------------------------
    # 状态 5: COMPLETE - 项目完成
    # ------------------------------------------------------------------

    def state_complete(self) -> bool:
        """完成项目，发送通知。"""
        self.log(f"[EXECUTOR_COMPLETE_START] project_id={self.project_id}")

        # 更新项目状态
        script = _script("project-data/scripts/project_data.py")
        rc, stdout, stderr = _run_script(
            script, "update-project", self.project_id, "completed"
        )

        if rc != 0:
            self.log(f"[EXECUTOR_COMPLETE_UPDATE_FAIL] stderr={stderr}", "warning")
        else:
            self.log(f"[EXECUTOR_COMPLETE_PROJECT_UPDATED] project_id={self.project_id}, status=completed")

        self.log(f"[EXECUTOR_COMPLETE_END] project_id={self.project_id}")
        return True

    # ─── 质量门禁状态 ──────────────────────────────────────────────

    def state_quality_gate(self, task_id: str, task_type: str,
                           deliverable_path: str, content: str = "") -> bool:
        """对任务执行质量门禁检查。

        调用 quality_gate.py 通过 gbrain CLI 读取标准规则并校验交付物。
        失败则退回 Agent 重做，最多重试 3 次。

        Returns:
            True if gate passed or skipped, False if failed or retries exhausted
        """
        self.log(f"[EXECUTOR_QUALITY_GATE_START] task_id={task_id}, type={task_type}")

        # 检查重试次数
        retry_key = f"{task_id}"
        current_retries = self.quality_gate_retries.get(retry_key, 0)

        if current_retries >= 3:
            # 重试耗尽 — 标记为 needs_review 而非静默放过
            self.log_fail("EXECUTOR_QUALITY_GATE_MAX_RETRIES",
                          f"质量门禁重试超过 3 次：{task_id}",
                          f"project_id={self.project_id}")
            task_data = read_task_data(self.project_id)
            for t in task_data.get("tasks", []):
                if t["id"] == task_id:
                    t["status"] = "needs_review"
                    t["quality_gate_exhausted"] = True
                    break
            write_task_data(self.project_id, task_data)
            # 重试耗尽，通知审核者（而非执行 agent）
            self._notify_task_event("quality_gate_failed", None, task_id)
            return False  # 不阻塞流程，但标记了问题

        # 父任务有子任务但无独立 deliverable_path 时，合并子任务交付物
        actual_deliverable_path = deliverable_path
        if not actual_deliverable_path:
            merged = merge_subtask_deliverables(self.project_id, task_id)
            if merged:
                actual_deliverable_path = merged
                self.log(f"[EXECUTOR_QUALITY_GATE_MERGE] task_id={task_id}, "
                         f"merged subtask deliverables to: {merged}")

        # 执行门禁检查
        result = run_quality_gate(
            self.project_id, task_type, actual_deliverable_path, content,
        )

        if result.skipped:
            self.log(f"[EXECUTOR_QUALITY_GATE_SKIPPED] task_id={task_id}, "
                     f"reason=标准页面不存在或 gbrain 不可用")
            return True

        if result.passed:
            self.log(f"[EXECUTOR_QUALITY_GATE_PASSED] task_id={task_id}")
            return True

        # 门禁未通过 — 退回 Agent 重做
        self.quality_gate_retries[retry_key] = current_retries + 1
        self.log(f"[EXECUTOR_QUALITY_GATE_FAILED] task_id={task_id}, "
                 f"retry={current_retries + 1}/3, failures={len(result.failures)}")

        # 检查任务是否有子任务（子任务已完成的不应被丢弃）
        task_data = read_task_data(self.project_id)
        has_subtasks = False
        for t in task_data.get("tasks", []):
            if t["id"] == task_id and t.get("subtasks"):
                has_subtasks = True
                break

        # 获取任务对应的执行 agent，用于通知
        notify_agent_id = None
        for t in task_data.get("tasks", []):
            if t["id"] == task_id:
                notify_agent_id = t.get("agent")
                break

        if has_subtasks:
            # 有子任务时：子任务已完成，重做无意义。标记 needs_review 不阻塞流程
            self.log(f"[EXECUTOR_QUALITY_GATE_SUBTASK_SKIP] task_id={task_id} "
                     f"has completed subtasks, marking needs_review instead of retry")
            task_data = read_task_data(self.project_id)
            for t in task_data.get("tasks", []):
                if t["id"] == task_id:
                    t["status"] = "needs_review"
                    t["quality_gate_issues"] = result.failures
                    t["quality_gate_exhausted"] = True
                    break
            write_task_data(self.project_id, task_data)
            self._notify_task_event("quality_gate_failed", notify_agent_id, task_id,
                                    feedback=result.feedback)
        else:
            # 无子任务时正常重置重试 + 重新入队
            reset_task(self.project_id, task_id)
            # 调用 task_queue.py enqueue 将任务重新加入队列
            queue_script = _script("task-queue/scripts/task_queue.py")
            _run_script(queue_script, "enqueue", self.project_id, task_id)
            self._notify_task_event("task_retry", notify_agent_id, task_id,
                                    feedback=result.feedback)

        return False  # dispatch_loop 会重新调度此任务

    # ─── 交叉审核状态 ──────────────────────────────────────────────

    def state_review(self, task_id: str, reviewer: str,
                     deliverable_path: str, summary: str) -> bool:
        """对任务执行交叉审核。

        调用 cross_review.py 创建交接文档，通知审核者，等待结果。
        超时则标记为 needs_review，不阻塞流程。

        Returns:
            True if review passed, skipped, or timed out (non-blocking).
        """
        self.log(f"[EXECUTOR_REVIEW_START] task_id={task_id}, reviewer={reviewer}")

        # 从本地模板获取章节描述，供 cross review 使用
        template_sections = None
        task_info = get_task_info(self.project_id, task_id)
        task_type = task_info.get("task_type", "") if task_info else ""
        if task_type:
            dt, _ = _read_deliverable_template(task_type)
            sections = dt.get("sections", []) if isinstance(dt, dict) else []
            if sections and isinstance(sections, list):
                template_sections = [
                    {"name": s.get("name", ""), "description": s.get("description", "")}
                    for s in sections if isinstance(s, dict)
                ]

        result = run_cross_review(
            self.project_id, task_id, reviewer,
            deliverable_path, summary,
            template_sections=template_sections,
        )

        if result.passed:
            self.log(f"[EXECUTOR_REVIEW_PASSED] task_id={task_id}")
            return True

        if result.timed_out:
            self.log(f"[EXECUTOR_REVIEW_TIMEOUT] task_id={task_id}, reviewer={reviewer}")
            # 标记任务为 needs_review 但不返回 False（不阻塞流程）
            task_data = read_task_data(self.project_id)
            for task in task_data.get("tasks", []):
                if task["id"] == task_id:
                    task["status"] = "needs_review"
                    break
            write_task_data(self.project_id, task_data)
            return True

        if result.skipped:
            self.log(f"[EXECUTOR_REVIEW_SKIPPED] task_id={task_id}")
            return True

        # 审核未通过 — 退回 Agent（重新入队）
        self.log(f"[EXECUTOR_REVIEW_FAILED] task_id={task_id}, feedback={result.feedback[:50]}")
        self._update_task_via_cli(task_id, "pending")
        queue_script = _script("task-queue/scripts/task_queue.py")
        _run_script(queue_script, "enqueue", self.project_id, task_id)
        self._notify_task_event("task_retry", None, task_id, feedback=result.feedback)
        return False

    # ─── 状态机定义 ───────────────────────────────────────────────────
    # 新增状态只需在列表中添加一项，state_xxx 方法自动被调用
    STATE_ORDER = [
        "init", "team_config", "task_plan", "add_tasks",
        "dispatch_loop",
        "complete",
    ]

    def _run_states(self, states_to_run: list[str], init_args: tuple = ()) -> bool:
        """执行一系列状态，通过 getattr 自动分派。每个状态异常被捕获并记录。"""
        for state_name in states_to_run:
            try:
                method = getattr(self, f"state_{state_name}", None)
                if not method:
                    self.log_fail("EXECUTOR_UNKNOWN_STATE",
                                  f"未知状态：{state_name}",
                                  f"project_id={self.project_id}")
                    return False

                self.state = state_name.upper()
                self.log(f"[EXECUTOR_STATE_ENTER] state={self.state}")

                success = method(*init_args) if state_name == "init" else method()
                if not success:
                    self.log_fail("EXECUTOR_STATE_FAIL",
                                  f"状态 {self.state} 执行失败",
                                  f"project_id={self.project_id}")
                    return False
                self.log(f"[EXECUTOR_STATE_EXIT] state={self.state}")
            except Exception as e:
                self.log_fail("EXECUTOR_STATE_EXCEPTION",
                              f"状态 {self.state} 异常: {e}",
                              f"project_id={self.project_id}")
                return False

        return True

    def run_from_state(self, start_state: str) -> bool:
        """从指定状态开始执行流程引擎。"""
        start_state = start_state.lower()
        if start_state not in self.STATE_ORDER:
            self.log_fail("EXECUTOR_UNKNOWN_STATE",
                          f"未知状态：{start_state}",
                          f"project_id={self.project_id}")
            return False

        start_idx = self.STATE_ORDER.index(start_state)
        states_to_run = self.STATE_ORDER[start_idx:]

        init_args = ("自动创建项目", "由流程引擎自动创建") if start_state == "init" else ()
        self.log(f"[EXECUTOR_RUN_FROM_STATE] start_state={start_state}, states={','.join(states_to_run)}")
        return self._run_states(states_to_run, init_args=init_args)

    def run(self, project_name: str, description: str) -> bool:
        """运行完整的流程引擎。"""
        self.project_description = description
        self.log(f"[EXECUTOR_RUN_START] project_name={project_name}")

        # 从 INIT 开始完整执行，传递项目名称和描述
        result = self._run_states(self.STATE_ORDER, init_args=(project_name, description))

        if result:
            self.log(f"[EXECUTOR_RUN_END] project_id={self.project_id}")
        return result


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Task Executor — 流程引擎，控制团队协作项目标准执行流程"
    )
    parser.add_argument("project_name", nargs="?", default="", help="项目名称（可选，用于新建项目）")
    parser.add_argument("description", nargs="?", default="", help="项目描述（可选）")
    parser.add_argument(
        "--project-id",
        help="现有项目 ID（指定后跳过 INIT/TEAM_CONFIG/TASK_PLAN/ADD_TASKS）",
    )
    parser.add_argument(
        "--state",
        help="从指定状态开始执行（init, team_config, task_plan, add_tasks, dispatch_loop, complete）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="恢复已中断的项目（按项目名称查找，自动释放队列并重置卡住的任务）",
    )

    args = parser.parse_args()

    executor = Executor(args.project_id or "")

    # 恢复模式：按名称查找项目、释放队列、重置卡住任务、恢复执行
    if args.resume:
        if not executor.try_resume(args.project_name):
            print(f"\n❌ 未找到项目：{args.project_name}", file=sys.stderr)
            sys.exit(1)
        print(f"🔁 恢复项目：{executor.project_id}")
        success = executor.run_from_state("dispatch_loop")
    # 如果指定了 --project-id，直接从 DISPATCH_LOOP 开始
    elif args.project_id:
        executor.project_id = args.project_id
        start_state = args.state or "dispatch_loop"
        success = executor.run_from_state(start_state)
    else:
        success = executor.run(args.project_name, args.description)

    if success:
        print(f"\n✅ 流程引擎执行成功")
        print(f"   Project ID: {executor.project_id}")
        sys.exit(0)
    else:
        print(f"\n❌ 流程引擎执行失败（状态：{executor.state}）", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()