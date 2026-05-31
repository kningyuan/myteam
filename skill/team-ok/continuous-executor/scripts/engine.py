#!/usr/bin/env python3
"""Continuous Executor - 持续任务引擎

管理持续性项目的标准执行流程。与 task-executor 相同架构：
确定性状态机 + LLM Agent 负责决策。

状态机：CRASH_RECOVERY → INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP → COMPLETE

核心差异：DISPATCH_LOOP 每次只执行一轮 cycle，完成后更新 next_cycle_at 并退出。
通过 cron 或手动触发下一轮。
"""

import fcntl
import json
import os
import subprocess
import sys
import re
import copy
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.config import (
    POLL_INTERVAL,
    SUBPROCESS_TIMEOUT,
    NOTIFY_EVENT_TIMEOUT,
    TEAM_CONFIG_TIMEOUT,
    TASK_PLAN_TIMEOUT,
    TEAM_CONFIG_MAX_RETRIES,
    TASK_PLAN_MAX_RETRIES,
    NOTIFY_AGENT_TIMEOUT,
    PROJECT_DATA_CMD_TIMEOUT,
    ACK_TIMEOUT,
)
from common.logger import get_skill_logger, log_skill_step_failure, normalize_project_id
from common.quality_gate import run_quality_gate
from common.cross_review import run_cross_review
from common.deliverable_merger import merge_subtask_deliverables
from common.task_data_store import (
    project_dir,
    read_task_data,
    write_task_data,
    get_task_info,
    get_task_name,
    get_task_status,
    update_task_status,
    task_data_path,
    trigger_dir,
    response_dir,
    deliverables_dir,
    is_pid_alive,
    atomic_write_json,
    reset_task,
)
from common.validator import validate_team_config, validate_task_plan
from common.response_finder import find_response_file

HOME = Path.home()
BASE = HOME / ".openclaw"
SKILLS = BASE / "skills" / "team-ok"

CONTINUOUS_DIR = BASE / "tasks" / "continuous"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.yaml"
TEMPLATES_FILE = SKILLS / "templates" / "templates.yaml"

DEFAULT_CYCLE_CONFIG = {
    "interval_days": 7,
    "max_empty_before_backoff": 10,
    "backoff_factor": 2,
    "max_sleep_sec": 86400,
    # F2: 滚动窗口保留最近 N 轮 Deputy 评审摘要，供 Main cycle_plan 看趋势
    "recent_reviews_window": 3,
    # F3: cycle_summaries 内存上限；超出部分落盘到 archive/cycle_summaries.jsonl
    "max_inmemory_summaries": 50,
    # F4: 是否归档本轮 .trigger / .response（关闭时只保留默认行为）
    "archive_cycle_files": True,
}

# 按 task_type 路由交叉评审同侪（避免全部汇到 main 形成单点 + 自规划自评审）。
# 每项为候选列表，按优先级取第一个 != 产出 agent 的候选；都冲突则回退 main。
TASK_TYPE_REVIEWERS = {
    "research": ["analyst", "researcher"],
    "strategy": ["product", "main"],
    "content": ["seo", "coordinator"],
    "publish-post": ["seo", "coordinator"],
    "code-deliverable": ["tester", "developer"],
    "test-plan": ["developer", "tester"],
    "report": ["main", "product"],
}


def route_reviewer(task_type: str, agent: str, requested: Optional[str] = None) -> str:
    """选交叉评审同侪：按 task_type 路由，规避自评审与 main 单点。

    - 显式指定了非 main、且不是产出者本人的 reviewer → 尊重之。
    - 否则按 TASK_TYPE_REVIEWERS 取首个不等于产出 agent 的候选。
    - 都冲突或无映射 → 回退 main。
    """
    agent = (agent or "").strip()
    requested = (requested or "").strip()
    if requested and requested != "main" and requested != agent:
        return requested
    for candidate in TASK_TYPE_REVIEWERS.get((task_type or "").strip(), ["main"]):
        if candidate != agent:
            return candidate
    return "main"


def _read_deliverable_template(task_type: str) -> tuple[dict, dict]:
    """从 templates.yaml 读取交付物模板和校验规则。"""
    if not yaml or not TEMPLATES_FILE.exists():
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
    except (yaml.YAMLError, OSError, AttributeError):
        return {}, {}


def load_merged_config(config_path: str = "") -> dict:
    """加载 YAML 配置并与内置 cycle 默认值合并。"""
    merged = {"cycle": dict(DEFAULT_CYCLE_CONFIG)}
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists() or not yaml:
        return merged
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            return merged
        if isinstance(raw.get("cycle"), dict):
            merged["cycle"].update(raw["cycle"])
        for key, value in raw.items():
            if key != "cycle":
                merged[key] = value
        return merged
    except (yaml.YAMLError, OSError):
        return merged


def _script(path: str) -> str:
    return str(SKILLS / path)


def _run_script(script: str, *args, timeout: int = SUBPROCESS_TIMEOUT) -> tuple[int, str, str]:
    cmd = [sys.executable, script] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _notify_agent(event: str, agent_id: str, project_id: str, task_id: str = "", payload: dict = None, ack_timeout: int = None) -> bool:
    script = _script("agent-notify/scripts/notify_agent.py")
    args = [event, project_id]
    if event in ("cycle_review", "cycle_plan"):
        args.append(str(task_id))
        args.append(agent_id)
    else:
        if task_id:
            args.append(task_id)
        args.append(agent_id)
    if ack_timeout is not None:
        args.extend(["--ack-timeout", str(ack_timeout)])
    timeout = ack_timeout + 30 if ack_timeout is not None else NOTIFY_AGENT_TIMEOUT
    rc, stdout, stderr = _run_script(script, *args, timeout=timeout)
    return rc == 0


def _notify_event(event_type: str, agent_id: str, project_id: str, task_id: str, *extra_args):
    notify_script = str(SKILLS / "notify-telegram" / "scripts" / "notify.py")
    if not Path(notify_script).exists():
        return
    safe_agent = agent_id or ""
    safe_extra = tuple(str(a) for a in extra_args if a is not None)
    try:
        subprocess.run(
            [sys.executable, notify_script, project_id, event_type, safe_agent, task_id, *safe_extra],
            capture_output=True, text=True, timeout=NOTIFY_EVENT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


# ── 持续任务专用数据管理 ──


def continuous_data_path(project_id: str) -> Path:
    return project_dir(project_id) / "continuous_data.json"


def read_continuous_data(project_id: str) -> dict:
    path = continuous_data_path(project_id)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return normalize_continuous_data(json.load(f))
    except (json.JSONDecodeError, OSError):
        return {}


def write_continuous_data(project_id: str, data: dict):
    atomic_write_json(continuous_data_path(project_id), normalize_continuous_data(data))


VALID_EFFECTIVENESS = frozenset({"met", "partial", "missed", "inconclusive"})


def collect_needs_review_tasks(project_id: str, cycle_id: int = 0) -> list[dict]:
    """F1: 收集 task_data.json 中 needs_review 状态的任务清单。

    供 Deputy cycle_review 与 Main cycle_plan 提示，避免它们漏看未通过质量门禁/评审的任务。
    cycle_id>0 时仅匹配该轮（task_id 以 _NNN 结尾）。
    """
    try:
        td = read_task_data(project_id) or {}
    except Exception:
        return []
    out = []
    suffix = f"_{cycle_id:03d}" if cycle_id else ""
    for t in td.get("tasks", []):
        if t.get("status") != "needs_review":
            continue
        tid = str(t.get("id", ""))
        if suffix and not tid.endswith(suffix):
            continue
        out.append({
            "id": tid,
            "name": t.get("name", ""),
            "agent": t.get("agent", ""),
            "task_type": t.get("task_type", ""),
            "quality_gate_exhausted": bool(t.get("quality_gate_exhausted")),
            "quality_gate_issues": t.get("quality_gate_issues", []),
            "failure_reason": t.get("failure_reason", ""),
        })
    return out


def archive_overflow_summaries(
    project_id: str, cdata: dict, max_inmemory: int
) -> int:
    """F3: cycle_summaries 超阈值时将最旧的若干条落盘 archive/cycle_summaries.jsonl。

    返回归档条数。修改 cdata 中的 cycle_summaries（截断）但不写盘——由调用方写。
    """
    summaries = cdata.get("cycle_summaries", [])
    if len(summaries) <= max_inmemory:
        return 0
    overflow_count = len(summaries) - max_inmemory
    overflow = summaries[:overflow_count]
    cdata["cycle_summaries"] = summaries[overflow_count:]
    archive_dir = project_dir(project_id) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = archive_dir / "cycle_summaries.jsonl"
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for entry in overflow:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return overflow_count


def archive_cycle_files(project_id: str, cycle_id: int) -> dict:
    """F4: 将本轮 cycle 级 .request/.response 归档到各 agent workspace 的 archive/cycle-NNN/。

    覆盖 main / deputy / 等 agent workspace 下 .response 目录里的：
      - {project_id}_cycle_{NNN}_plan.{request,response}
      - {project_id}_cycle_{NNN}_review.{request,response}
    任务级 .request/.response 由 task-executor 体系管理，本函数不动。
    返回 {agent_id: count}。
    """
    suffix_token = f"cycle_{cycle_id:03d}_"
    moved = {}
    workspaces_root = HOME / ".openclaw"
    if not workspaces_root.exists():
        return moved
    for ws in workspaces_root.iterdir():
        if not ws.is_dir() or not ws.name.startswith("workspace-"):
            continue
        agent_id = ws.name.replace("workspace-", "", 1)
        for sub in (".response", ".trigger"):
            src_dir = ws / sub
            if not src_dir.exists():
                continue
            candidates = [
                p for p in src_dir.iterdir()
                if p.is_file()
                and p.name.startswith(f"{project_id}_")
                and suffix_token in p.name
            ]
            if not candidates:
                continue
            dst_dir = ws / "archive" / f"cycle-{cycle_id:03d}" / sub.lstrip(".")
            dst_dir.mkdir(parents=True, exist_ok=True)
            for src in candidates:
                try:
                    src.rename(dst_dir / src.name)
                    moved[agent_id] = moved.get(agent_id, 0) + 1
                except OSError:
                    pass
    return moved


def acquire_cycle_lock(project_id: str):
    """F6: 取项目 cycle 锁；同一项目并发 trigger-now 互斥。

    返回打开的 fd（成功）或 None（已被持有）。调用方负责 close 释放。
    """
    pdir = project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    lock_path = pdir / "continuous-cycle.lock"
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        os.close(fd)
        return None
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
    except OSError:
        pass
    return fd


def release_cycle_lock(fd: Optional[int]) -> None:
    """F6: 释放 cycle 锁。"""
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def normalize_continuous_data(cdata: dict) -> dict:
    """迁移旧 schema（last_cycle）→ last_closed_cycle / pending_review / last_review。"""
    if not cdata:
        return cdata
    cdata.setdefault("last_review", {})
    cdata.setdefault("pending_review", None)
    cdata.setdefault("last_closed_cycle", {})
    # F2: 保留最近 N 轮 Deputy 评审摘要（最旧在前、最新在后）
    cdata.setdefault("recent_reviews", [])

    legacy = cdata.get("last_cycle")
    if legacy and isinstance(legacy, dict) and legacy.get("cycle_id"):
        if not cdata.get("last_closed_cycle", {}).get("cycle_id"):
            period = legacy.get("period", [])
            closed_at = period[-1] if isinstance(period, list) and period else ""
            cdata["last_closed_cycle"] = {
                "cycle_id": legacy.get("cycle_id"),
                "closed_at": closed_at,
                "tasks": legacy.get("tasks", []),
                "deliverable_refs": legacy.get("deliverable_refs", []),
                "hypotheses": legacy.get("hypotheses", ""),
                "baseline_metrics": legacy.get("baseline_metrics", ""),
                "outcome_metrics": legacy.get("outcome_metrics", ""),
            }
        eff = legacy.get("effectiveness", "")
        if (
            eff in ("待评估", "", None)
            and not cdata.get("last_review", {}).get("cycle_id")
            and not cdata.get("pending_review")
        ):
            cdata["pending_review"] = {
                "cycle_id": legacy["cycle_id"],
                "requested_at": datetime.now().isoformat(),
            }
        del cdata["last_cycle"]
    return cdata


def extract_hypotheses_text(text: str) -> str:
    """从交付物提取本轮假设章节。"""
    if not text:
        return ""
    for heading in (r"假设", r"Hypotheses", r"待验证"):
        m = re.search(rf"##\s*(?:{heading})\s*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
        if m:
            return m.group(1).strip()[:500]
    return ""


def collect_cycle_deliverable_refs(project_id: str, task_ids: list) -> list:
    refs = []
    for tid in task_ids:
        ti = get_task_info(project_id, tid)
        if ti and ti.get("deliverable_path"):
            refs.append(ti["deliverable_path"])
    return refs


# ── Phase 工具函数 ──


def is_phase_due(phase: dict, now: datetime = None) -> bool:
    """检查循环阶段是否到期。"""
    if now is None:
        now = datetime.now()
    if phase.get("type") != "recurring":
        return False
    if phase.get("status") != "active":
        return False
    next_at_str = phase.get("next_cycle_at")
    if not next_at_str:
        return True  # 从未触发过
    try:
        next_at = datetime.fromisoformat(next_at_str)
        return now >= next_at
    except ValueError:
        return True


def get_cycle_number(phase: dict) -> int:
    return phase.get("cycle_count", 0) + 1


def generate_instance_id(template_id: str, cycle_number: int) -> str:
    return f"{template_id}_{cycle_number:03d}"


def build_trigger_context(
    project_name: str,
    project_summary: dict,
    last_review: dict,
    cycle_id: int,
    task: dict,
    required_skills: Optional[list] = None,
) -> dict:
    """为 dispatch 构建轮次继承上下文（精简，不含完整历史）。"""
    context = {
        "project_name": project_name,
        "project_goal": project_summary.get("goal", ""),
        "current_state": project_summary.get("current_state", ""),
        "accumulated_learnings": project_summary.get("accumulated_learnings", ""),
        "cycle_id": cycle_id,
    }
    if last_review and last_review.get("cycle_id"):
        hints = last_review.get("planning_hints", [])
        if isinstance(hints, str):
            hints = [hints] if hints else []
        context["last_review"] = {
            "cycle_id": last_review["cycle_id"],
            "effectiveness": last_review.get("effectiveness", ""),
            "planning_hints": hints,
            "evidence_summary": (last_review.get("evidence_summary") or "")[:300],
        }
    skills = required_skills or task.get("required_skills") or []
    if skills:
        context["required_skills"] = skills
    return context


def extract_adjustments(deliverable_text: str) -> dict:
    """从 agent 交付物中提取调整建议。"""
    adjustments = {}
    if not deliverable_text:
        return adjustments

    # 查找 ## 调整建议 章节
    section_match = re.search(r'##\s*调整建议\s*\n(.*?)(?=\n##\s|\Z)', deliverable_text, re.DOTALL)
    if not section_match:
        return adjustments

    section = section_match.group(1)

    # cycle_interval: N
    m = re.search(r'cycle_interval:\s*(\d+)', section)
    if m:
        adjustments["cycle_interval"] = int(m.group(1))

    # add_task: {json}
    m = re.search(r'add_task:\s*(\{.*\})', section, re.DOTALL)
    if m:
        try:
            adjustments["add_task"] = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # remove_task: task_id
    m = re.search(r'remove_task:\s*(\S+)', section)
    if m:
        adjustments["remove_task"] = m.group(1)

    # pause_phase: phase_name
    m = re.search(r'pause_phase:\s*(.+?)$', section, re.MULTILINE)
    if m:
        adjustments["pause_phase"] = m.group(1).strip()

    # resume_phase: phase_name
    m = re.search(r'resume_phase:\s*(.+?)$', section, re.MULTILINE)
    if m:
        adjustments["resume_phase"] = m.group(1).strip()

    # modify_task: {json}
    m = re.search(r'modify_task:\s*(\{.*\})', section, re.DOTALL)
    if m:
        try:
            adjustments["modify_task"] = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return adjustments


def apply_adjustments(phases: list[dict], adjustments: dict) -> list[str]:
    """应用调整建议到 phase 配置。返回变更日志。"""
    changes = []
    if not adjustments:
        return changes

    if "cycle_interval" in adjustments:
        for phase in phases:
            if phase.get("type") == "recurring" and phase.get("status") == "active":
                old = phase.get("interval_days", "?")
                phase["interval_days"] = adjustments["cycle_interval"]
                changes.append(f"循环间隔 {old}→{adjustments['cycle_interval']} 天")

    if "add_task" in adjustments and "phase" in adjustments["add_task"]:
        new_task = adjustments["add_task"]
        phase_name = new_task.pop("phase", "")
        for phase in phases:
            if phase["name"] == phase_name:
                tid = new_task.get("id", "unknown")
                phase.setdefault("tasks", []).append(new_task)
                changes.append(f"新增任务 {tid} 到阶段「{phase_name}」")

    if "remove_task" in adjustments:
        tid = adjustments["remove_task"]
        for phase in phases:
            phase["tasks"] = [t for t in phase.get("tasks", []) if t.get("id") != tid]
        changes.append(f"移除任务 {tid}")

    if "pause_phase" in adjustments:
        pname = adjustments["pause_phase"]
        for phase in phases:
            if phase["name"] == pname:
                phase["status"] = "paused"
                changes.append(f"暂停阶段「{pname}」")

    if "resume_phase" in adjustments:
        pname = adjustments["resume_phase"]
        for phase in phases:
            if phase["name"] == pname:
                phase["status"] = "active"
                changes.append(f"恢复阶段「{pname}」")

    if "modify_task" in adjustments:
        mod = adjustments["modify_task"]
        tid = mod.get("id", "")
        for phase in phases:
            for t in phase.get("tasks", []):
                if t.get("id") == tid:
                    for k, v in mod.items():
                        if k != "id":
                            t[k] = v
                    changes.append(f"修改任务 {tid}")
                    break

    return changes


# ============================================================================
# 主引擎
# ============================================================================


class ContinuousExecutor:
    """持续任务引擎 - 管理持续性项目的标准执行流程。"""

    def __init__(self, project_id: str = "", config_path: str = ""):
        self.project_id = project_id
        self.logger = None
        self.state = "INIT"
        self.team: list[str] = []
        self.phases: list[dict] = []
        self.retry_counts: dict[str, int] = {}
        self.quality_gate_retries: dict[str, int] = {}
        self.project_description = ""
        self.config = load_merged_config(config_path)
        self.cycle_config = self.config.get("cycle", dict(DEFAULT_CYCLE_CONFIG))

    def _init_logger(self):
        if not self.logger:
            self.logger = get_skill_logger(self.project_id or "continuous")

    def log(self, msg: str, level: str = "info"):
        self._init_logger()
        getattr(self.logger, level)(f"[CONTINUOUS] {msg}", extra={"skill_name": "CONTINUOUS"})

    def log_fail(self, step: str, detail: str, extra_text: str = ""):
        self.log(f"[{step}] {detail}", "error")
        log_skill_step_failure(self.project_id, "CONTINUOUS", step, detail, extra_text)

    # ════════════════════════════════════════════════════════════════
    # CRASH_RECOVERY
    # ════════════════════════════════════════════════════════════════

    def state_crash_recovery(self) -> bool:
        self.log(f"[CRASH_RECOVERY] project_id={self.project_id}")
        # 连续项目没有复杂的 journal 恢复。检测 pid 文件是否存在且进程存活。
        if not self.project_id:
            return True
        pid_file = project_dir(self.project_id) / "continuous-pid"
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                if is_pid_alive(old_pid):
                    self.log_fail(
                        "CRASH_RECOVERY_ALIVE",
                        f"已有实例运行 (PID={old_pid})，拒绝并发启动",
                        self.project_id,
                    )
                    return False
                self.log(f"[CRASH_RECOVERY] 检测到上次异常退出 (PID={old_pid})，已清理")
            except (ValueError, OSError):
                pass
            pid_file.unlink(missing_ok=True)
        return True

    # ════════════════════════════════════════════════════════════════
    # INIT
    # ════════════════════════════════════════════════════════════════

    def state_init(self, project_name: str, description: str) -> bool:
        self.project_description = description
        self.log(f"[INIT] project_name={project_name}")

        script = _script("project-init/scripts/init.py")
        rc, stdout, stderr = _run_script(script, project_name, description)

        if rc != 0:
            self.log_fail("INIT_FAIL", f"项目创建失败：{stderr}", project_name)
            return False

        lines = stdout.strip().split("\n")
        pid = lines[-1].strip() if lines else ""
        if not pid.startswith("pro_"):
            self.log_fail("INIT_FAIL", f"无法解析 project_id：{stdout}", project_name)
            return False

        self.project_id = pid
        self.logger = get_skill_logger(pid)
        self.log(f"[INIT_OK] project_id={self.project_id}")

        # 初始化 continuous_data.json
        cdata = {
            "project": {
                "id": pid,
                "name": project_name,
                "goal": description,
                "type": "continuous",
                "status": "running",
                "created_at": datetime.now().isoformat(),
            },
            "project_summary": {
                "current_state": "项目初始化中",
                "accumulated_learnings": "",
                "goal": description,
            },
            "last_closed_cycle": {},
            "pending_review": None,
            "last_review": {},
            "cycle_summaries": [],
            "phases": [],
            "executor_pid": os.getpid(),
            "journal": [],
        }
        write_continuous_data(pid, cdata)

        # 写入 PID 文件
        pid_file = project_dir(pid) / "continuous-pid"
        pid_file.write_text(str(os.getpid()), encoding="utf-8")

        return True

    # ════════════════════════════════════════════════════════════════
    # TEAM_CONFIG
    # ════════════════════════════════════════════════════════════════

    def state_team_config(self) -> bool:
        self.log(f"[TEAM_CONFIG] project_id={self.project_id}")

        req_dir = response_dir("main")
        req_dir.mkdir(parents=True, exist_ok=True)
        req_file = req_dir / f"{self.project_id}_team_config.request"

        request = {
            "event": "request_team_config",
            "project_id": self.project_id,
            "message": (
                "请根据以下持续项目描述，返回参与项目的 agent 列表。\n\n"
                "这是一个持续性项目（非一次性），请考虑需要长期参与的角色。\n"
                "可用角色：researcher(调研)、product(产品)、developer(开发)、designer(设计)、\n"
                "ops(运维)、seo(SEO)、content(内容)、social(社交)、email(邮件)、docs(文档)、\n"
                "consultation(咨询)、coordinator(合规)、tester(测试)、analyst(分析)\n\n"
                "规则：严格按照下方 JSON 格式返回，不要包含其他文字。\n"
                "agent 名称必须是英文小写。\n\n"
                "项目描述：\n" + self.project_description
            ),
            "expected_format": {"agents": ["agent_1", "agent_2"]},
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        self.log(f"[TEAM_CONFIG_REQUEST] file={req_file}")

        _notify_agent("team_config", "main", self.project_id, payload=request)

        resp_file = req_dir / f"{self.project_id}_team_config.response"
        deadline = time.time() + TEAM_CONFIG_TIMEOUT
        retry_count = 0

        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    self.log("[TEAM_CONFIG_JSON_FAIL] invalid JSON", "warning")
                    resp_file.unlink()
                    continue

                result = validate_team_config(response)
                if result.passed:
                    self.team = response.get("agents", [])
                    self.log(f"[TEAM_CONFIG_OK] agents={','.join(self.team)}")
                    return True
                else:
                    retry_count += 1
                    self.log(f"[TEAM_CONFIG_VALIDATE_FAIL] retry={retry_count}", "warning")
                    if retry_count >= TEAM_CONFIG_MAX_RETRIES:
                        self.log_fail("TEAM_CONFIG_FAIL", f"验证失败：{result.failures}", self.project_id)
                        return False
                    request["retry_feedback"] = result.failures
                    with open(req_file, "w", encoding="utf-8") as f:
                        json.dump(request, f, ensure_ascii=False, indent=2)
                    _notify_agent("team_config", "main", self.project_id, payload=request)

            time.sleep(POLL_INTERVAL)

        self.log_fail("TEAM_CONFIG_TIMEOUT", "等待团队配置超时", self.project_id)
        return False

    # ════════════════════════════════════════════════════════════════
    # TASK_PLAN
    # ════════════════════════════════════════════════════════════════

    def state_task_plan(self) -> bool:
        self.log(f"[TASK_PLAN] project_id={self.project_id}, team={','.join(self.team)}")

        req_dir = response_dir("main")
        req_file = req_dir / f"{self.project_id}_task_plan.request"

        # 构造阶段设计的 prompt
        agent_list = "、".join(self.team)
        phase_prompt = (
            "请为以下持续性项目设计阶段（phases）和任务模板。\n\n"
            "你的设计将决定这个持续项目未来长期运行的机制。\n\n"
            "## 阶段类型\n"
            "- **one_time**：一次性阶段，所有任务完成后标记完成，不再重复\n"
            "- **recurring**：循环阶段，按 interval_days 间隔反复触发\n\n"
            "## 设计建议\n"
            "1. 先设计一个或多个 one_time 阶段用于前期准备（如基线审计、基础设施搭建）\n"
            "2. 再设计 recurring 阶段用于持续循环（如每周执行、月度评估）\n"
            "3. 每个 recurring 阶段需要指定 interval_days（循环间隔天数）\n"
            "4. 同一个 phase 内的任务按 dependencies 顺序执行\n"
            "5. 不同 phase 之间：one_time 完成后才激活 recurring\n"
            "6. 可以在某些任务上设置 can_output_adjustments: true，\n"
            "   表示该任务的交付物可以包含对整体计划的调整建议（如修改循环间隔、新增任务等）\n\n"
            "## 团队角色\n"
            f"当前团队成员：{agent_list}\n"
            "禁止分配给不在以上列表中的角色。\n\n"
            "## agent 角色 → task_type 映射\n"
            "- seo → strategy（策略建议：问题定义、方案对比、推荐方案）\n"
            "- developer → code-deliverable（代码交付物：方案设计、实现说明、测试）\n"
            "- content → content（内容文案：目标读者、内容框架、正文）\n"
            "- analyst → research（调研报告：调研背景、核心发现、结论建议）\n"
            "- product → prd（需求文档）\n"
            "- tester → test-plan（测试计划）\n"
            "- designer → design-review（设计方案）\n"
            "- ops → strategy（运维方案）\n"
        )

        request = {
            "event": "request_task_plan",
            "project_id": self.project_id,
            "team": self.team,
            "message": phase_prompt,
            "expected_format": {
                "phases": [
                    {
                        "name": "阶段名称",
                        "type": "one_time | recurring",
                        "description": "阶段描述",
                        "interval_days": 7,
                        "tasks": [
                            {
                                "id": "task_001",
                                "name": "任务名称",
                                "agent": "agent_id",
                                "task_type": "research | strategy | prd | code-deliverable | content | test-plan | design-review | docs",
                                "reviewer": "（可省略：引擎按 task_type 自动路由同侪评审；如需指定，填非本人 agent_id）",
                                "description": "任务描述",
                                "dependencies": [],
                                "can_output_adjustments": False,
                            }
                        ],
                    }
                ]
            },
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        self.log(f"[TASK_PLAN_REQUEST] file={req_file}")

        _notify_agent("task_plan", "main", self.project_id, payload=request)

        resp_file = req_dir / f"{self.project_id}_task_plan.response"
        deadline = time.time() + TASK_PLAN_TIMEOUT
        retry_count = 0

        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    self.log("[TASK_PLAN_JSON_FAIL] invalid JSON", "warning")
                    resp_file.unlink()
                    continue

                phases = response.get("phases", [])
                # 验证基础结构
                errors = []
                for i, ph in enumerate(phases):
                    if ph.get("type") not in ("one_time", "recurring"):
                        errors.append(f"phase[{i}] type 必须是 one_time 或 recurring")
                    if ph.get("type") == "recurring":
                        interval = ph.get("interval_days", 0)
                        if not isinstance(interval, (int, float)) or interval < 1:
                            errors.append(f"phase[{i}] recurring 必须有 interval_days>=1")
                    tasks = ph.get("tasks", [])
                    if not tasks:
                        errors.append(f"phase[{i}] 至少有一个 task")
                    for t in tasks:
                        if t.get("agent") not in self.team:
                            errors.append(f"task {t.get('id')} 的 agent 不在团队中")

                if not errors:
                    self.phases = phases
                    task_counts = sum(len(ph.get("tasks", [])) for ph in phases)
                    self.log(f"[TASK_PLAN_OK] phases={len(phases)}, total_tasks={task_counts}")
                    return True
                else:
                    retry_count += 1
                    self.log(f"[TASK_PLAN_VALIDATE_FAIL] retry={retry_count}, errors={errors}", "warning")
                    if retry_count >= TASK_PLAN_MAX_RETRIES:
                        self.log_fail("TASK_PLAN_FAIL", f"验证失败：{errors}", self.project_id)
                        return False
                    request["retry_feedback"] = errors
                    with open(req_file, "w", encoding="utf-8") as f:
                        json.dump(request, f, ensure_ascii=False, indent=2)
                    _notify_agent("task_plan", "main", self.project_id, payload=request)

            time.sleep(POLL_INTERVAL)

        self.log_fail("TASK_PLAN_TIMEOUT", "等待任务规划超时", self.project_id)
        return False

    # ════════════════════════════════════════════════════════════════
    # ADD_TASKS
    # ════════════════════════════════════════════════════════════════

    def state_add_tasks(self) -> bool:
        self.log(f"[ADD_TASKS] project_id={self.project_id}")

        script = _script("project-data/scripts/project_data.py")

        # 添加一次性阶段的初始任务
        for phase in self.phases:
            for task in phase.get("tasks", []):
                deps = ",".join(task.get("dependencies", []))
                task_id = task.get("id", "?")
                task_type = task.get("task_type", "")
                reviewer = route_reviewer(task_type, task.get("agent", ""), task.get("reviewer"))
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
                    self.log_fail("ADD_TASKS_FAIL", f"添加任务失败：{task['name']} - {stderr}", task_id)
                    return False
                self.log(f"[TASK_ADDED] task_id={task_id}")

        # 确认项目
        rc, stdout, stderr = _run_script(script, "confirm", self.project_id)
        if rc != 0:
            self.log_fail("CONFIRM_FAIL", f"确认项目失败：{stderr}", self.project_id)
            return False

        # 写入 phases 配置到 continuous_data.json
        cdata = read_continuous_data(self.project_id)
        now = datetime.now()
        for phase in self.phases:
            if phase.get("type") == "one_time":
                phase["status"] = "active"
            elif phase.get("type") == "recurring":
                phase["status"] = "pending"  # 等 one_time 完成后才 active
                phase["cycle_count"] = 0
                phase["last_cycle_completed_at"] = ""
                # 首次触发时间：等所有 one_time phases 完成后 + interval_days
                phase["next_cycle_at"] = ""
        cdata["phases"] = self.phases
        write_continuous_data(self.project_id, cdata)

        self.log(f"[ADD_TASKS_OK] phases={len(self.phases)}")
        return True

    # ════════════════════════════════════════════════════════════════
    # DISPATCH_LOOP（核心差异）
    # ════════════════════════════════════════════════════════════════

    def state_dispatch_loop(self) -> bool:
        """持续模式的 dispatch_loop：检查到期 → 生成实例 → 执行本周期 → 退出。"""
        self.log(f"[DISPATCH_LOOP] project_id={self.project_id}")

        cdata = read_continuous_data(self.project_id)
        if not cdata:
            self.log_fail("DISPATCH_LOOP_FAIL", "continuous_data.json 为空", self.project_id)
            return False

        self.phases = cdata.get("phases", [])
        if not self.phases:
            self.log_fail("DISPATCH_LOOP_FAIL", "未找到 phase 配置", self.project_id)
            return False

        now = datetime.now()
        cdata = normalize_continuous_data(cdata)
        project_summary = cdata.get("project_summary", {})
        last_review = cdata.get("last_review", {})
        pending_review = cdata.get("pending_review")

        # ─── 第一步：检查 one_time phases 状态 ───
        one_time_incomplete = [p for p in self.phases
                               if p.get("type") == "one_time" and p.get("status") != "completed"]
        if one_time_incomplete:
            self.log(f"[DISPATCH_LOOP] one_time phases 未完成，进入标准 dispatch_loop")
            # 处理一次性任务（同 task-executor 的逻辑）
            return self._run_standard_dispatch_loop()

        # ─── 第二步：检查 recurring phases 是否到期 ───
        due_phases = [p for p in self.phases if is_phase_due(p, now)]

        # 检查是否有 phase 的 pending → active 转换
        for phase in self.phases:
            if phase.get("type") == "recurring" and phase.get("status") == "pending":
                # 检查是否有未完成的 one_time phase
                if not one_time_incomplete:
                    phase["status"] = "active"
                    phase["next_cycle_at"] = now.isoformat()
                    due_phases.append(phase)
                    self.log(f"[PHASE_ACTIVATED] phase={phase['name']}")

        if not due_phases:
            self.log(f"[DISPATCH_LOOP] 没有到期 phase，检查调整建议")
            # 检查最近一次 planning 的交付物是否有调整建议
            self._check_pending_adjustments(cdata)
            return True

        # ─── 第三步：为到期的 phase 生成本轮任务（Main replan 或模板 fallback）───
        cycle_number = None
        for phase in due_phases:
            if phase.get("type") == "recurring":
                cycle_number = get_cycle_number(phase)
                break
        if cycle_number is None:
            cycle_number = 1

        self.log(f"[CYCLE_START] cycle={cycle_number}, phases={[p['name'] for p in due_phases if p.get('type')=='recurring']}")

        # ─── 下轮开始前：Deputy 评审上一轮（若有 pending_review）───
        if pending_review and pending_review.get("cycle_id"):
            if not self.state_cycle_review(cdata):
                self.log_fail(
                    "CYCLE_REVIEW_FAIL",
                    f"第 {pending_review['cycle_id']} 轮评审失败，阻塞本轮规划",
                    self.project_id,
                )
                return False
            cdata = read_continuous_data(self.project_id) or cdata
            last_review = cdata.get("last_review", {})
            pending_review = cdata.get("pending_review")

        if cycle_number > 1 and not last_review.get("effectiveness"):
            self.log_fail(
                "CYCLE_PLAN_BLOCKED",
                f"第 {cycle_number} 轮缺少 Deputy last_review，已阻塞",
                self.project_id,
            )
            return False

        planned_tasks = self.state_cycle_plan(
            due_phases, cycle_number, project_summary, cdata, last_review
        )
        new_tasks = []
        adjustment_sources = []
        instance_now = datetime.now().isoformat()

        if planned_tasks:
            self.log(f"[CYCLE_PLAN_OK] Main 返回 {len(planned_tasks)} 个任务")
            for pt in planned_tasks:
                nt = self._build_cycle_instance_task(pt, due_phases, cycle_number, instance_now)
                if nt:
                    new_tasks.append(nt)
                    if pt.get("can_output_adjustments"):
                        adjustment_sources.append(nt["id"])
        else:
            self.log("[CYCLE_PLAN_FALLBACK] 使用 phase 模板实例化")
            for phase in due_phases:
                if phase.get("type") != "recurring":
                    continue
                cn = get_cycle_number(phase)
                for template in phase.get("tasks", []):
                    nt = self._build_cycle_instance_task(
                        template, [phase], cn, instance_now, from_template=True
                    )
                    if nt:
                        new_tasks.append(nt)
                        if template.get("can_output_adjustments"):
                            adjustment_sources.append(nt["id"])

        if not new_tasks:
            self.log("[DISPATCH_LOOP] 无可生成的任务实例")
            return True

        # ─── 第四步：将新实例添加到 task_data.json ───
        self.log(f"[GENERATE_INSTANCES] 生成本轮 {len(new_tasks)} 个任务实例")
        task_data = read_task_data(self.project_id)
        task_data.setdefault("tasks", [])
        existing_ids = {t["id"] for t in task_data["tasks"]}

        for nt in new_tasks:
            if nt["id"] not in existing_ids:
                nt["priority"] = len(task_data["tasks"]) + 1
                task_data["tasks"].append(nt)
                self.log(f"[INSTANCE] id={nt['id']}, agent={nt['agent']}, deps={nt['dependencies']}")
            else:
                self.log(f"[INSTANCE_SKIP] id={nt['id']} 已存在", "warning")

        # 将老任务标记为 template 保留但不冲突
        write_task_data(self.project_id, task_data)

        # ─── 第五步：执行 dispatch_loop（同 task-executor） ───
        success = self._run_standard_dispatch_loop()

        if not success:
            self.log_fail("CYCLE_FAIL", f"第 {cycle_number} 轮执行失败", self.project_id)
            # 更新 phase 统计数据，让下轮重试
            return False

        # ─── 第六步：提取调整建议 ───
        adjustments = {}
        if adjustment_sources:
            for src_id in adjustment_sources:
                ti = get_task_info(self.project_id, src_id)
                if ti and ti.get("deliverable_path"):
                    dv_path = Path(ti["deliverable_path"])
                    if dv_path.exists():
                        text = dv_path.read_text(encoding="utf-8")
                        adj = extract_adjustments(text)
                        if adj:
                            adjustments.update(adj)
                            self.log(f"[ADJUSTMENTS] from task={src_id}: {adj}")

        # ─── 第七步：更新 cycle 统计和 project_summary ───
        cycle_summary = {
            "cycle_id": cycle_number,
            "period": [
                now.isoformat(),
                datetime.now().isoformat(),
            ],
            "tasks_completed": [nt["id"] for nt in new_tasks],
            "key_outcomes": "",
            "baseline_metrics": "",
            "metrics_delta": "",
        }

        # 从 evaluation task 提取指标
        eval_task_id = generate_instance_id("evaluation", cycle_number)
        eval_info = get_task_info(self.project_id, eval_task_id)
        if eval_info and eval_info.get("deliverable_path"):
            ev_path = Path(eval_info["deliverable_path"])
            if ev_path.exists():
                ev_text = ev_path.read_text(encoding="utf-8")
                # 提取指标（如果 agent 按约定写了关键指标章节）
                m = re.search(r'##\s*(?:关键指标|Metrics|效果评估)\s*\n(.*?)(?=\n##\s|\Z)', ev_text, re.DOTALL)
                if m:
                    cycle_summary["key_outcomes"] = m.group(1).strip()[:200]
                # 提取基线
                m = re.search(r'基线[：:]\s*(.+?)$', ev_text, re.MULTILINE)
                if m:
                    cycle_summary["baseline_metrics"] = m.group(1).strip()
                # 提取变化
                m = re.search(r'(?:变化|delta|效果)[：:]\s*(.+?)$', ev_text, re.MULTILINE)
                if m:
                    cycle_summary["metrics_delta"] = m.group(1).strip()

        # 从 planning task 提取 learnings
        plan_task_id = generate_instance_id("planning", cycle_number)
        plan_info = get_task_info(self.project_id, plan_task_id)
        plan_learnings = ""
        if plan_info and plan_info.get("deliverable_path"):
            pl_path = Path(plan_info["deliverable_path"])
            if pl_path.exists():
                pl_text = pl_path.read_text(encoding="utf-8")
                m = re.search(r'##\s*(?:积累知识|Learnings|经验)\s*\n(.*?)(?=\n##\s|\Z)', pl_text, re.DOTALL)
                if m:
                    plan_learnings = m.group(1).strip()[:200]

        # ─── 应用调整建议 ───
        change_log = apply_adjustments(self.phases, adjustments)
        if change_log:
            self.log(f"[ADJUSTMENTS_APPLIED] changes={','.join(change_log)}")

        # ─── 更新 phase 状态 ───
        for phase in self.phases:
            if phase.get("name") in [p["name"] for p in due_phases]:
                phase["cycle_count"] = phase.get("cycle_count", 0) + 1
                phase["last_cycle_completed_at"] = datetime.now().isoformat()
                # 计算下一周期
                interval = phase.get("interval_days", 7)
                next_at = datetime.now() + timedelta(days=interval)
                phase["next_cycle_at"] = next_at.isoformat()

        # ─── 更新 project_summary ───
        old_state = project_summary.get("current_state", "")
        old_learnings = project_summary.get("accumulated_learnings", "")
        if cycle_summary["metrics_delta"]:
            project_summary["current_state"] = cycle_summary["metrics_delta"]
        if plan_learnings:
            sep = "\n" if old_learnings else ""
            project_summary["accumulated_learnings"] = old_learnings + sep + plan_learnings

        # ─── 写入 continuous_data.json（轮末归档，不写 effectiveness）───
        task_ids = [nt["id"] for nt in new_tasks]
        hypotheses = ""
        plan_task_id = generate_instance_id("planning", cycle_number)
        plan_info = get_task_info(self.project_id, plan_task_id)
        if plan_info and plan_info.get("deliverable_path"):
            pl_path = Path(plan_info["deliverable_path"])
            if pl_path.exists():
                hypotheses = extract_hypotheses_text(pl_path.read_text(encoding="utf-8"))

        cdata["project_summary"] = project_summary
        cdata["last_closed_cycle"] = {
            "cycle_id": cycle_number,
            "closed_at": datetime.now().isoformat(),
            "tasks": [nt["name"] for nt in new_tasks],
            "task_ids": task_ids,
            "deliverable_refs": collect_cycle_deliverable_refs(self.project_id, task_ids),
            "hypotheses": hypotheses,
            "baseline_metrics": cycle_summary.get("baseline_metrics", ""),
            "outcome_metrics": cycle_summary.get("metrics_delta", ""),
        }
        cdata["pending_review"] = {
            "cycle_id": cycle_number,
            "requested_at": datetime.now().isoformat(),
        }
        cdata["cycle_summaries"].append(cycle_summary)
        cdata["phases"] = self.phases
        # F3: cycle_summaries 超阈值时归档老条目，避免 continuous_data.json 无限膨胀
        max_inmemory = int(self.cycle_config.get("max_inmemory_summaries", 50) or 50)
        archived_n = archive_overflow_summaries(self.project_id, cdata, max_inmemory)
        if archived_n:
            self.log(f"[ARCHIVE_SUMMARIES] cycle={cycle_number}, archived={archived_n}")
        write_continuous_data(self.project_id, cdata)
        # F4: 归档本轮 cycle 级 .request/.response 到各 agent workspace
        if self.cycle_config.get("archive_cycle_files", True):
            moved = archive_cycle_files(self.project_id, cycle_number)
            if moved:
                self.log(f"[ARCHIVE_FILES] cycle={cycle_number}, moved={moved}")

        # 清理 PID 文件（本周期完成）
        pid_file = project_dir(self.project_id) / "continuous-pid"
        pid_file.unlink(missing_ok=True)

        self.log(f"[CYCLE_COMPLETE] cycle={cycle_number}, tasks={len(new_tasks)}")
        if change_log:
            self.log(f"[ADJUSTMENTS] {','.join(change_log)}")

        print(f"\n✅ 第 {cycle_number} 轮完成")
        print(f"   阶段：{', '.join(p['name'] for p in due_phases)}")
        print(f"   任务：{len(new_tasks)} 个")
        if change_log:
            print(f"   调整：{', '.join(change_log)}")
        print(f"   下轮预计：{', '.join(p.get('next_cycle_at','?')[:10] for p in self.phases if p.get('type')=='recurring' and p.get('status')=='active')}")
        return True

    def build_execute_trigger_extras(self, task_info: dict) -> dict:
        """为 execute trigger 注入 continuous_context（持续项目轮次继承）。"""
        cdata = read_continuous_data(self.project_id) or {}
        ps = cdata.get("project_summary", {})
        lr = cdata.get("last_review", {})
        cycle_id = task_info.get("cycle_number", 0)
        if not cycle_id:
            tid = task_info.get("id", "")
            m = re.search(r"_(\d+)$", tid)
            if m:
                cycle_id = int(m.group(1))
        ctx = build_trigger_context(
            cdata.get("project", {}).get("name", self.project_id),
            ps,
            lr,
            cycle_id,
            task_info,
            required_skills=task_info.get("required_skills"),
        )
        return {"continuous_context": ctx}

    def _build_cycle_instance_task(
        self,
        spec: dict,
        due_phases: list,
        cycle_number: int,
        instance_now: str,
        from_template: bool = False,
    ) -> Optional[dict]:
        """将 Main replan 条目或 phase 模板转为可入队的任务实例。"""
        template_id = spec.get("template_id") or spec.get("id", "")
        if not template_id:
            return None

        phase_name = spec.get("phase_name", "")
        if not phase_name:
            for phase in due_phases:
                if phase.get("type") != "recurring":
                    continue
                for t in phase.get("tasks", []):
                    if t.get("id") == template_id or t.get("id") == spec.get("template_id"):
                        phase_name = phase.get("name", "")
                        break

        instance_id = spec.get("id")
        if from_template or not re.search(r"_\d{3}$", str(instance_id or "")):
            instance_id = generate_instance_id(template_id, cycle_number)

        name = spec.get("name", template_id)
        if from_template:
            name = f"{spec.get('name', template_id)}（第{cycle_number}轮）"

        dep_ids = []
        for dep in spec.get("dependencies", []):
            dep_s = str(dep)
            # 实例 ID 形如 task_005_001（至少两段 _）；task_005 仅模板 id，勿误判
            if re.search(r"_\d{3}$", dep_s) and dep_s.count("_") >= 2:
                dep_ids.append(dep_s)
            else:
                dep_ids.append(generate_instance_id(dep_s, cycle_number))

        return {
            "id": instance_id,
            "name": name,
            "agent": spec.get("agent", ""),
            "task_type": spec.get("task_type", ""),
            "reviewer": route_reviewer(
                spec.get("task_type", ""), spec.get("agent", ""), spec.get("reviewer")
            ),
            "description": spec.get("description", ""),
            "dependencies": dep_ids,
            "template_id": template_id,
            "cycle_number": cycle_number,
            "phase_name": phase_name,
            "status": "pending",
            "priority": 0,
            "preemptible": True,
            "timeout_minutes": spec.get("timeout_minutes", 10),
            "max_retries": 0,
            "retry_count": 0,
            "failed_at": None,
            "failure_reason": None,
            "required_skills": spec.get("required_skills", []),
            "subtasks": [],
            "created_at": instance_now,
            "updated_at": instance_now,
            "triggered_at": None,
            "started_at": None,
            "completed_at": None,
        }

    def state_cycle_review(self, cdata: dict) -> bool:
        """请 Deputy 评审 pending_review 对应轮次的业务效果。"""
        pending = cdata.get("pending_review") or {}
        cycle_id = pending.get("cycle_id")
        if not cycle_id:
            return True

        self.log(f"[CYCLE_REVIEW] cycle={cycle_id}")

        req_dir = response_dir("deputy")
        req_dir.mkdir(parents=True, exist_ok=True)
        req_file = req_dir / f"{self.project_id}_cycle_{cycle_id:03d}_review.request"
        resp_file = req_dir / f"{self.project_id}_cycle_{cycle_id:03d}_review.response"

        last_closed = cdata.get("last_closed_cycle", {})
        digest_paths = last_closed.get("deliverable_refs", [])[:10]
        # F1: 把本轮 needs_review 任务清单交给 Deputy，让评审有判罚依据
        needs_review_tasks = collect_needs_review_tasks(self.project_id, cycle_id)

        request = {
            "event": "request_cycle_review",
            "project_id": self.project_id,
            "cycle_id": cycle_id,
            "project_summary": cdata.get("project_summary", {}),
            "last_closed_cycle": last_closed,
            "deliverable_digest_paths": digest_paths,
            "needs_review_tasks": needs_review_tasks,
            "skill_path": str(BASE / "workspace-deputy" / "skills" / "cycle-review" / "SKILL.md"),
            "message": (
                f"请评审第 {cycle_id} 轮持续项目的**业务效果**（非任务交付物质量）。\n\n"
                "阅读 last_closed_cycle 中的假设、交付物路径与自报指标。\n"
                f"本轮 needs_review 任务 {len(needs_review_tasks)} 个，请在 planning_hints 中明确下轮如何处理。\n"
                "按 workspace-deputy/skills/cycle-review/SKILL.md 输出 JSON 与 review 交付物。\n\n"
                "返回 JSON：\n"
                '{"cycle_id": N, "effectiveness": "met|partial|missed|inconclusive", '
                '"evidence_summary": "...", "planning_hints": ["..."], '
                '"deliverable_path": "deliverables/cycle-NNN/cycle-NNN-review.md"}\n'
            ),
            "expected_format": {
                "cycle_id": cycle_id,
                "effectiveness": "partial",
                "planning_hints": [],
            },
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)

        _notify_agent("cycle_review", "deputy", self.project_id, task_id=cycle_id)

        deadline = time.time() + TASK_PLAN_TIMEOUT
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    resp_file.unlink(missing_ok=True)
                    time.sleep(POLL_INTERVAL)
                    continue

                eff = response.get("effectiveness", "")
                if eff not in VALID_EFFECTIVENESS:
                    self.log(f"[CYCLE_REVIEW_VALIDATE_FAIL] effectiveness={eff}", "warning")
                    return False

                if int(response.get("cycle_id", 0) or 0) != int(cycle_id):
                    self.log("[CYCLE_REVIEW_VALIDATE_FAIL] cycle_id mismatch", "warning")
                    return False

                hints = response.get("planning_hints", [])
                if isinstance(hints, str):
                    hints = [hints] if hints else []

                review_entry = {
                    "cycle_id": cycle_id,
                    "reviewed_at": datetime.now().isoformat(),
                    "effectiveness": eff,
                    "evidence_summary": response.get("evidence_summary", ""),
                    "planning_hints": hints,
                    "deliverable_path": response.get("deliverable_path", ""),
                }
                cdata["last_review"] = review_entry
                # F2: 维护最近 N 轮评审滚动窗口（去重 cycle_id，保留最新）
                window = int(self.cycle_config.get("recent_reviews_window", 3) or 3)
                recent = [
                    r for r in cdata.get("recent_reviews", [])
                    if int(r.get("cycle_id", -1)) != cycle_id
                ]
                recent.append(review_entry)
                cdata["recent_reviews"] = recent[-window:]
                cdata["pending_review"] = None
                write_continuous_data(self.project_id, cdata)
                self.log(f"[CYCLE_REVIEW_OK] cycle={cycle_id}, effectiveness={eff}")
                return True

            time.sleep(POLL_INTERVAL)

        self.log("[CYCLE_REVIEW_TIMEOUT]", "warning")
        return False

    def state_cycle_plan(
        self,
        due_phases: list,
        cycle_number: int,
        project_summary: dict,
        cdata: dict,
        last_review: dict,
    ) -> Optional[list]:
        """请 Main 规划本轮任务；第 2 轮起必须参考 Deputy 的 last_review。"""
        self.log(f"[CYCLE_PLAN] cycle={cycle_number}")

        is_first_recurring = cycle_number == 1
        templates_hint = []
        for phase in due_phases:
            if phase.get("type") != "recurring":
                continue
            for t in phase.get("tasks", []):
                entry = {
                    "template_id": t.get("id"),
                    "name": t.get("name"),
                    "agent": t.get("agent"),
                    "task_type": t.get("task_type"),
                    "description": t.get("description"),
                    "dependencies": t.get("dependencies", []),
                    "phase_name": phase.get("name"),
                }
                if t.get("required_skills"):
                    entry["required_skills"] = t.get("required_skills")
                templates_hint.append(entry)

        req_dir = response_dir("main")
        req_dir.mkdir(parents=True, exist_ok=True)
        req_file = req_dir / f"{self.project_id}_cycle_{cycle_number:03d}_plan.request"
        resp_file = req_dir / f"{self.project_id}_cycle_{cycle_number:03d}_plan.response"

        if is_first_recurring:
            plan_hint = (
                "这是 recurring 的**第 1 轮**，尚无 last_review；请按项目目标与模板直接规划。\n"
                "周期性例行运维/健康检查类任务请分配给 **ops**，不要分配给 deputy。\n"
                "领域 skill 用 agent 工作区路径写入 required_skills（非公共 skill 目录）。\n"
            )
        else:
            plan_hint = (
                f"这是第 {cycle_number} 轮，**必须**依据 last_review 的 effectiveness 与 planning_hints 调整本轮任务。\n"
                "勿忽略 Deputy 评审结论。例行运维仍用 ops。\n"
            )

        # F1: 把上一轮 needs_review 任务交给 Main，便于安排补救任务
        last_review_cycle_id = int((last_review or {}).get("cycle_id") or 0)
        prev_needs_review = (
            collect_needs_review_tasks(self.project_id, last_review_cycle_id)
            if last_review_cycle_id
            else []
        )
        # F2: 提供最近 N 轮评审，让 Main 看趋势而非孤立单轮
        recent_reviews = cdata.get("recent_reviews", []) if not is_first_recurring else []

        request = {
            "event": "request_cycle_plan",
            "project_id": self.project_id,
            "cycle_number": cycle_number,
            "is_first_recurring_cycle": is_first_recurring,
            "project_summary": project_summary,
            "last_closed_cycle": cdata.get("last_closed_cycle", {}),
            "last_review": last_review if not is_first_recurring else {},
            "recent_reviews": recent_reviews,
            "previous_needs_review_tasks": prev_needs_review,
            "due_phases": [p.get("name") for p in due_phases if p.get("type") == "recurring"],
            "templates": templates_hint,
            "message": (
                f"请为第 {cycle_number} 轮持续项目制定本轮任务列表。\n\n"
                f"{plan_hint}\n"
                f"上一轮 needs_review 任务 {len(prev_needs_review)} 个；"
                f"recent_reviews 含最近 {len(recent_reviews)} 轮评审，请综合趋势规划。\n"
                "返回 JSON：{\"tasks\": [{\"template_id\": \"...\", \"name\": \"...\", "
                "\"agent\": \"...\", \"task_type\": \"...\", "
                "\"description\": \"...\", \"dependencies\": [], "
                "\"required_skills\": [\"/path/to/workspace-agent/skills/.../SKILL.md\"], "
                "\"can_output_adjustments\": false}]}\n"
                "（reviewer 字段可省略：引擎按 task_type 自动路由同侪评审）\n"
            ),
            "expected_format": {"tasks": templates_hint},
            "created_at": datetime.now().isoformat(),
        }

        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)

        _notify_agent("cycle_plan", "main", self.project_id, task_id=cycle_number)

        deadline = time.time() + TASK_PLAN_TIMEOUT
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    with open(resp_file, "r", encoding="utf-8") as f:
                        response = json.load(f)
                except json.JSONDecodeError:
                    resp_file.unlink(missing_ok=True)
                    time.sleep(POLL_INTERVAL)
                    continue

                tasks = response.get("tasks")
                if isinstance(tasks, list) and tasks:
                    valid = [t for t in tasks if isinstance(t, dict) and (t.get("template_id") or t.get("id"))]
                    if valid:
                        self.log(f"[CYCLE_PLAN_RESPONSE] tasks={len(valid)}")
                        return valid
                self.log("[CYCLE_PLAN_VALIDATE_FAIL] 响应无有效 tasks", "warning")
                return None

            time.sleep(POLL_INTERVAL)

        self.log("[CYCLE_PLAN_TIMEOUT] 使用模板 fallback", "warning")
        return None

    def _run_standard_dispatch_loop(self) -> bool:
        """标准 dispatch：evaluate → execute → QG → review（移植自 task-executor）。"""
        from task_dispatch import TaskDispatchRunner

        return TaskDispatchRunner(self, send_project_complete=False).run()

    def _check_pending_adjustments(self, cdata: dict):
        """检查是否有已完成任务带了调整建议（非周期触发时运行）。"""
        self.log("[CHECK_ADJUSTMENTS] 检查待处理的调整建议")

        task_data = read_task_data(self.project_id)
        for task in task_data.get("tasks", []):
            if task.get("status") != "completed":
                continue
            if task.get("can_output_adjustments") or task.get("template_id", "").startswith("planning"):
                if task.get("deliverable_path"):
                    dv_path = Path(task["deliverable_path"])
                    if dv_path.exists():
                        text = dv_path.read_text(encoding="utf-8")
                        adj = extract_adjustments(text)
                        if adj:
                            self.log(f"[PENDING_ADJUSTMENT] from task={task['id']}: {adj}")
                            phases = cdata.get("phases", [])
                            change_log = apply_adjustments(phases, adj)
                            if change_log:
                                cdata["phases"] = phases
                                write_continuous_data(self.project_id, cdata)
                                self.log(f"[ADJUSTMENTS_APPLIED] {','.join(change_log)}")
                                print(f"   调整：{', '.join(change_log)}")

    def _notify_task_event(self, event_type: str, agent_id: str, task_id: str, *extra_args, **kwargs):
        """发送任务级 Telegram 通知（含重试 feedback）。"""
        feedback = kwargs.get("feedback", "")
        extra = list(extra_args)
        if feedback and feedback not in extra:
            extra.append(feedback)
        _notify_event(event_type, agent_id or "", self.project_id, task_id, *extra)

    def state_quality_gate(self, task_id: str, task_type: str,
                           deliverable_path: str, content: str = "") -> bool:
        """对任务执行质量门禁（同 task-executor）。"""
        self.log(f"[QUALITY_GATE_START] task_id={task_id}, type={task_type}")

        retry_key = task_id
        current_retries = self.quality_gate_retries.get(retry_key, 0)

        if current_retries >= 3:
            self.log_fail(
                "QUALITY_GATE_MAX_RETRIES",
                f"质量门禁重试超过 3 次：{task_id}",
                self.project_id,
            )
            task_data = read_task_data(self.project_id)
            for t in task_data.get("tasks", []):
                if t["id"] == task_id:
                    t["status"] = "needs_review"
                    t["quality_gate_exhausted"] = True
                    break
            write_task_data(self.project_id, task_data)
            self._notify_task_event("quality_gate_failed", None, task_id)
            return True

        actual_deliverable_path = deliverable_path
        if not actual_deliverable_path:
            merged = merge_subtask_deliverables(self.project_id, task_id)
            if merged:
                actual_deliverable_path = merged
                self.log(f"[QUALITY_GATE_MERGE] task_id={task_id}, path={merged}")

        result = run_quality_gate(
            self.project_id, task_type, actual_deliverable_path, content,
        )

        if result.skipped:
            self.log(f"[QUALITY_GATE_SKIPPED] task_id={task_id}")
            return True

        if result.passed:
            self.log(f"[QUALITY_GATE_PASSED] task_id={task_id}")
            return True

        self.quality_gate_retries[retry_key] = current_retries + 1
        self.log(
            f"[QUALITY_GATE_FAILED] task_id={task_id}, "
            f"retry={current_retries + 1}/3, failures={len(result.failures)}"
        )

        task_data = read_task_data(self.project_id)
        has_subtasks = False
        notify_agent_id = None
        for t in task_data.get("tasks", []):
            if t["id"] == task_id:
                has_subtasks = bool(t.get("subtasks"))
                notify_agent_id = t.get("agent")
                break

        if has_subtasks:
            for t in task_data.get("tasks", []):
                if t["id"] == task_id:
                    t["status"] = "needs_review"
                    t["quality_gate_issues"] = result.failures
                    t["quality_gate_exhausted"] = True
                    break
            write_task_data(self.project_id, task_data)
            self._notify_task_event(
                "quality_gate_failed", notify_agent_id, task_id, feedback=result.feedback,
            )
        else:
            reset_task(self.project_id, task_id)
            queue_script = _script("task-queue/scripts/task_queue.py")
            _run_script(queue_script, "enqueue", self.project_id, task_id)
            self._notify_task_event(
                "task_retry", notify_agent_id, task_id, feedback=result.feedback,
            )

        return False

    def state_review(self, task_id: str, reviewer: str,
                     deliverable_path: str, summary: str) -> bool:
        """交叉审核（同 task-executor）。"""
        self.log(f"[REVIEW_START] task_id={task_id}, reviewer={reviewer}")

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
            self.log(f"[REVIEW_PASSED] task_id={task_id}")
            return True

        if result.timed_out:
            self.log(f"[REVIEW_TIMEOUT] task_id={task_id}, reviewer={reviewer}")
            task_data = read_task_data(self.project_id)
            for task in task_data.get("tasks", []):
                if task["id"] == task_id:
                    task["status"] = "needs_review"
                    break
            write_task_data(self.project_id, task_data)
            return True

        if result.skipped:
            self.log(f"[REVIEW_SKIPPED] task_id={task_id}")
            return True

        self.log(f"[REVIEW_FAILED] task_id={task_id}")
        update_task_status(self.project_id, task_id, "pending")
        queue_script = _script("task-queue/scripts/task_queue.py")
        _run_script(queue_script, "enqueue", self.project_id, task_id)
        self._notify_task_event("task_retry", None, task_id, feedback=result.feedback)
        return False

    # ════════════════════════════════════════════════════════════════
    # COMPLETE
    # ════════════════════════════════════════════════════════════════

    def state_complete(self) -> bool:
        self.log(f"[COMPLETE] project_id={self.project_id}")

        cdata = read_continuous_data(self.project_id)
        if cdata:
            cdata["project"]["status"] = "stopped"
            write_continuous_data(self.project_id, cdata)

        pid_file = project_dir(self.project_id) / "continuous-pid"
        pid_file.unlink(missing_ok=True)

        # 更新 project-data 状态
        script = _script("project-data/scripts/project_data.py")
        _run_script(script, "update-project", self.project_id, "stopped")

        # 统计总 cycle
        total_cycles = len(cdata.get("cycle_summaries", [])) if cdata else 0
        print(f"\n✅ 持续项目已停止")
        print(f"   共运行 {total_cycles} 个周期")
        return True

    # ════════════════════════════════════════════════════════════════
    # 状态机驱动
    # ════════════════════════════════════════════════════════════════

    # 新建项目完整流程（不含 complete；停止仅 via --stop → run_complete_only）
    STATE_ORDER = [
        "crash_recovery", "init", "team_config", "task_plan", "add_tasks",
        "dispatch_loop",
    ]

    def _run_states(self, states_to_run: list[str], init_args: tuple = ()) -> bool:
        for state_name in states_to_run:
            try:
                method = getattr(self, f"state_{state_name}", None)
                if not method:
                    self.log_fail("UNKNOWN_STATE", f"未知状态：{state_name}", self.project_id)
                    return False
                self.state = state_name.upper()
                self.log(f"[ENTER] state={self.state}")
                success = method(*init_args) if state_name == "init" else method()
                if not success:
                    self.log_fail("STATE_FAIL", f"状态 {self.state} 执行失败", self.project_id)
                    return False
                self.log(f"[EXIT] state={self.state}")
            except Exception as e:
                self.log_fail("STATE_EXCEPTION", f"状态 {self.state} 异常: {e}", self.project_id)
                return False
        return True

    def run(self, project_name: str, description: str) -> bool:
        self.project_description = description
        self.log(f"[RUN] project_name={project_name}")
        return self._run_states(self.STATE_ORDER, init_args=(project_name, description))

    def run_cycle(self) -> bool:
        """已存在项目的周期执行：crash_recovery → dispatch_loop（不含 complete）。

        F6: 全程持项目级文件锁，避免并发 trigger-now 重入导致 INSTANCE_SKIP。
        """
        lock_fd = acquire_cycle_lock(self.project_id)
        if lock_fd is None:
            self.log("[CYCLE_LOCK_BUSY] 已有周期在执行，跳过本次 trigger-now")
            print("⏭️  已有周期在执行（锁被占用），跳过本次触发")
            return False
        try:
            return self._run_states(["crash_recovery", "dispatch_loop"])
        finally:
            release_cycle_lock(lock_fd)

    def run_complete_only(self) -> bool:
        """仅执行 COMPLETE（停止项目）。"""
        self.log("[STOP] 正在停止项目")
        return self.state_complete()


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Continuous Executor — 持续任务引擎"
    )
    parser.add_argument("project_name", nargs="?", default="", help="项目名称（新建项目时使用）")
    parser.add_argument("description", nargs="?", default="", help="项目描述（可选）")
    parser.add_argument("--project-id", help="现有项目 ID")
    parser.add_argument("--config", help="配置文件路径（新建项目时使用）")
    parser.add_argument("--trigger-now", action="store_true", help="手动触发一轮周期检查")
    parser.add_argument("--stop", action="store_true", help="停止持续项目")
    parser.add_argument("--status", action="store_true", help="查看项目状态")
    parser.add_argument("--pause-phase", help="暂停指定 phase")
    parser.add_argument("--resume-phase", help="恢复指定 phase")
    parser.add_argument("--adjust-interval", nargs=2, metavar=("PHASE", "DAYS"), help="调整 phase 循环间隔")

    args = parser.parse_args()

    executor = ContinuousExecutor(args.project_id or "", config_path=args.config or "")

    # ─── 状态查询 ───
    if args.status and args.project_id:
        cdata = read_continuous_data(args.project_id)
        if not cdata:
            print(f"❌ 项目数据不存在：{args.project_id}", file=sys.stderr)
            sys.exit(1)
        p = cdata.get("project", {})
        ps = cdata.get("project_summary", {})
        lc = cdata.get("last_closed_cycle", {})
        lr = cdata.get("last_review", {})
        pr = cdata.get("pending_review")
        print(f"\n📊 持续项目状态")
        print(f"   名称：{p.get('name', '?')}")
        print(f"   状态：{p.get('status', '?')}")
        print(f"   目标：{ps.get('goal', '?')}")
        print(f"   当前：{ps.get('current_state', '?')}")
        print(f"   总周期：{len(cdata.get('cycle_summaries', []))}")
        print(f"\n   ── 阶段 ──")
        for phase in cdata.get("phases", []):
            extra = ""
            if phase.get("type") == "recurring":
                extra = f" | 间隔 {phase.get('interval_days', '?')}天"
                if phase.get("next_cycle_at"):
                    extra += f" | 下轮 {phase['next_cycle_at'][:10]}"
            print(f"   {phase.get('name', '?')} [{phase.get('type', '?')}] {phase.get('status')}{extra}")
        if pr and pr.get("cycle_id"):
            print(f"\n   ── 待评审 ──")
            print(f"   第 {pr['cycle_id']} 轮（下轮 trigger 时由 Deputy cycle_review）")
        if lr.get("cycle_id"):
            print(f"\n   ── 最近评审 ──")
            print(f"   第 {lr['cycle_id']} 轮 | {lr.get('effectiveness', '?')}")
            if lr.get("planning_hints"):
                print(f"   规划提示：{'; '.join(lr['planning_hints'][:3])}")
        if lc.get("cycle_id"):
            print(f"\n   ── 最近关闭轮次 ──")
            print(f"   第 {lc['cycle_id']} 轮")
            print(f"   基线：{lc.get('baseline_metrics', '?')}")
            print(f"   自报效果：{lc.get('outcome_metrics', '?')}")
        print()
        sys.exit(0)

    # ─── Phase 管理 ───
    if args.pause_phase and args.project_id:
        cdata = read_continuous_data(args.project_id)
        for phase in cdata.get("phases", []):
            if phase["name"] == args.pause_phase:
                phase["status"] = "paused"
                write_continuous_data(args.project_id, cdata)
                print(f"✅ 阶段「{args.pause_phase}」已暂停")
                sys.exit(0)
        print(f"❌ 未找到阶段：{args.pause_phase}", file=sys.stderr)
        sys.exit(1)

    if args.resume_phase and args.project_id:
        cdata = read_continuous_data(args.project_id)
        for phase in cdata.get("phases", []):
            if phase["name"] == args.resume_phase:
                phase["status"] = "active"
                write_continuous_data(args.project_id, cdata)
                print(f"✅ 阶段「{args.resume_phase}」已恢复")
                sys.exit(0)
        print(f"❌ 未找到阶段：{args.resume_phase}", file=sys.stderr)
        sys.exit(1)

    if args.adjust_interval and args.project_id:
        phase_name, days_str = args.adjust_interval
        try:
            days = int(days_str)
        except ValueError:
            print(f"❌ 天数必须为整数", file=sys.stderr)
            sys.exit(1)
        cdata = read_continuous_data(args.project_id)
        for phase in cdata.get("phases", []):
            if phase["name"] == phase_name:
                phase["interval_days"] = days
                write_continuous_data(args.project_id, cdata)
                print(f"✅ 阶段「{phase_name}」间隔已调整为 {days} 天")
                sys.exit(0)
        print(f"❌ 未找到阶段：{phase_name}", file=sys.stderr)
        sys.exit(1)

    # ─── 停止项目 ───
    if args.stop and args.project_id:
        executor.project_id = args.project_id
        executor.logger = get_skill_logger(args.project_id)
        success = executor.run_complete_only()
        sys.exit(0 if success else 1)

    # ─── 触发周期检查 ───
    if args.trigger_now and args.project_id:
        executor.project_id = args.project_id
        executor.logger = get_skill_logger(args.project_id)
        print(f"🔁 触发周期检查：{args.project_id}")
        success = executor.run_cycle()
        sys.exit(0 if success else 1)

    # ─── 新建项目 ───
    if args.project_name:
        desc = args.description or f"持续项目：{args.project_name}"
        success = executor.run(args.project_name, desc)
        if success:
            print(f"\n🔁 持续项目已创建")
            print(f"   Project ID: {executor.project_id}")
            total_phases = len(executor.phases)
            recurring = sum(1 for p in executor.phases if p.get("type") == "recurring")
            print(f"   阶段：{total_phases} 个（{recurring} 个循环）")
            print(f"\n   下次触发：设置 cron 或运行：")
            print(f"   {sys.executable} {__file__} --project-id {executor.project_id} --trigger-now")
            sys.exit(0)
        else:
            sys.exit(1)

    # ─── 已存在的项目，有 project-id → 执行周期 ───
    if args.project_id:
        success = executor.run_cycle()
        sys.exit(0 if success else 1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()