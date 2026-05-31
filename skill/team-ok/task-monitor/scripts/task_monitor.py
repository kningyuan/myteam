#!/usr/bin/env python3
"""
Task Monitor - 检查任务队列状态、Agent 存活情况、执行统计
"""
import os
import re
import sys
import ast
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

# 导入日志模块
sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.logger import get_skill_logger, log_skill_step_failure

_MONITOR_NO_PROJECT = "_MONITOR_NO_PROJECT_"


def _exit_monitor_usage(usage_line: str, command_name: str = "") -> None:
    log_skill_step_failure(
        _MONITOR_NO_PROJECT,
        "MONITOR",
        "missing_project_arg",
        usage_line,
        command_name or "",
    )
    print(usage_line, file=sys.stderr)
    sys.exit(1)

TASK_QUEUE_DIR = Path.home() / ".openclaw"
PROJECT_DATA_PY = (
    Path.home()
    / ".openclaw"
    / "skills"
    / "team-ok"
    / "project-data"
    / "scripts"
    / "project_data.py"
)

DEFAULT_TIMEOUT_MINUTES = 10  # 默认超时时间（分钟）



def validate_task_graph(project_id: str) -> int:
    """委托 `project-data check-cycle`：整图 DAG 与依赖存在性（非 LLM 硬门槛）。"""
    corrected_id = normalize_project_id(project_id)
    r = subprocess.run(
        [str(PROJECT_DATA_PY), "check-cycle", corrected_id],
        capture_output=True,
        text=True,
    )
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    code = int(r.returncode)
    if code != 0:
        msg = (r.stderr or r.stdout or "").strip()
        log_skill_step_failure(
            corrected_id,
            "MONITOR",
            "validate_graph_check_cycle_failed",
            msg[:500] if msg else "check-cycle non-zero",
            "",
        )
    return code


SESSION_MAP_FILE = TASK_QUEUE_DIR / "opencode_session_map.json"
PROJECTS_DIR = TASK_QUEUE_DIR / "tasks" / "projects"


def check_graph_validation(project_id: str) -> dict:
    """委托 `project-data check-cycle`；供 `health` JSON 使用（不向 stdout 打印）。"""
    corrected_id = normalize_project_id(project_id)
    tdf = PROJECTS_DIR / corrected_id / "task_data.json"
    if not tdf.is_file():
        return {"ok": True, "skipped": True, "reason": "no_task_data"}
    r = subprocess.run(
        [str(PROJECT_DATA_PY), "check-cycle", corrected_id],
        capture_output=True,
        text=True,
    )
    ok = r.returncode == 0
    return {
        "ok": ok,
        "exit_code": r.returncode,
        "stdout": (r.stdout or "").strip(),
        "stderr": (r.stderr or "").strip(),
    }


def check_orphaned_completed_tasks(project_id: str) -> list:
    """检测已完成但未调用task-complete的任务（孤立任务）"""
    orphaned = []
    try:
        corrected_id = normalize_project_id(project_id)
        task_data_file = PROJECTS_DIR / corrected_id / "task_data.json"
        if not task_data_file.exists():
            return orphaned

        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for task in data.get("tasks", []):
            if task.get("status") == "completed" and task.get("completed_at"):
                agent = task.get("agent", "")
                task_id = task.get("id", "")
                trigger_dir = Path.home() / f".openclaw/workspace-{agent}/.trigger"
                candidates = []
                for pid in (corrected_id, project_id):
                    if pid:
                        p = trigger_dir / f"{pid}_{task_id}.trigger"
                        if p not in candidates:
                            candidates.append(p)
                for trigger_file in candidates:
                    if trigger_file.exists():
                        orphaned.append(
                            {
                                "task_id": task_id,
                                "agent": agent,
                                "completed_at": task.get("completed_at"),
                                "trigger_exists": True,
                                "trigger_path": str(trigger_file),
                            }
                        )
                        try:
                            trigger_file.unlink()
                            print(f"🧹 清理残留trigger: {trigger_file}")
                        except OSError:
                            pass

        return orphaned
    except Exception as e:
        print(f"Error checking orphaned tasks: {e}")
        return orphaned

def _parse_queue_task_id(content: str) -> Optional[str]:
    """解析 .task_queue 文件内容，提取任务 ID（兼容 v1 纯文本和 v2 JSON 格式）。"""
    content = content.strip()
    if not content or content == "[]":
        return None
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data.get("task_id")
        if isinstance(data, list) and data:
            return data[-1]
    except (json.JSONDecodeError, ValueError):
        pass
    return content.split("\n")[0] if content else None


def get_all_project_queues():
    """获取所有项目的任务队列状态（扫描 ~/.openclaw/tasks/projects/<id>/.task_queue）。"""
    queues = []
    if not PROJECTS_DIR.is_dir():
        return queues
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        qf = project_dir / ".task_queue"
        if not qf.is_file():
            continue
        try:
            content = qf.read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"Error reading {qf}: {e}", file=sys.stderr)
            continue
        task_id = _parse_queue_task_id(content)
        if task_id:
            queues.append(
                {
                    "project": project_dir.name,
                    "status": f"running:{task_id}",
                    "file": str(qf),
                }
            )
    return queues

def get_task_timeout(project_id, task_id):
    """获取任务的超时配置"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return DEFAULT_TIMEOUT_MINUTES
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for task in data.get("tasks", []):
            if task["id"] == task_id:
                return task.get("timeout_minutes", DEFAULT_TIMEOUT_MINUTES)
        
        return DEFAULT_TIMEOUT_MINUTES
    except Exception:
        return DEFAULT_TIMEOUT_MINUTES

def check_agent_alive(project_id: str) -> dict:
    """检查 Agent 是否存活"""
    try:
        session_file = SESSION_MAP_FILE
        if not session_file.exists():
            return {"alive": None, "reason": "no_session_file"}
        
        sessions = json.loads(session_file.read_text(encoding="utf-8"))
        
        # 查找该项目的 session
        for key, session_id in sessions.items():
            if project_id in key:
                # session 存在，假设存活
                return {
                    "alive": True,
                    "session_id": session_id,
                    "reason": "session_exists"
                }
        
        return {"alive": False, "reason": "no_session"}
    except Exception as e:
        return {"alive": None, "reason": str(e)}

def check_task_timeout(task_file: str, project_id: str = None, task_id: str = None) -> dict:
    """检查任务是否超时（支持动态超时配置）"""
    try:
        f = Path(task_file)
        if not f.exists():
            return {"timeout": False, "reason": "file_not_found"}
        
        # 获取任务配置的超时时间
        timeout_minutes = DEFAULT_TIMEOUT_MINUTES
        if project_id and task_id:
            timeout_minutes = get_task_timeout(project_id, task_id)
        
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = datetime.now() - mtime
        
        is_timeout = age > timedelta(minutes=timeout_minutes)
        
        return {
            "timeout": is_timeout,
            "age_minutes": int(age.total_seconds() / 60),
            "threshold_minutes": timeout_minutes
        }
    except Exception as e:
        return {"timeout": False, "reason": str(e)}



def check_stuck(project_id: str) -> dict:
    """检查假死：队列有任务但 Agent 从未执行（与 resume.py detect_stuck_task 逻辑对齐）"""
    import subprocess
    import json as _json
    from datetime import datetime, timedelta
    try:
        qr = subprocess.run([str(Path.home() / ".openclaw" / "skills" / "team-ok" / "task-queue" / "scripts" / "task_queue.py"), 'status', project_id], capture_output=True, text=True)
        queue = qr.stdout.strip()
        if not queue or queue == "idle":
            return {"project": project_id, "is_zombie": False, "reason": "not_running"}

        task_id = queue.replace("running:", "").strip()
        tdf = PROJECTS_DIR / project_id / "task_data.json"
        if not tdf.exists():
            return {"project": project_id, "is_zombie": False, "reason": "no_data"}

        with open(tdf, "r", encoding="utf-8") as f:
            data = _json.load(f)

        agent = next((t.get("agent") for t in data.get("tasks", []) if t.get("id") == task_id), None)
        if not agent:
            return {"project": project_id, "is_zombie": False, "reason": "no_task"}

        # 检测维度 1：skills.log 是否有 DISPATCH_START 但无 task_start
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        has_start = has_task_start = False
        if lf.exists():
            with open(lf, "r", encoding="utf-8") as f:
                for line in f:
                    if task_id in line and agent in line:
                        if "DISPATCH_START" in line or "AGENT_NOTIFY_START" in line: has_start = True
                        if "task_start" in line: has_task_start = True

        # 检测维度 2：触发文件存在且超过 10 分钟
        trigger_file = Path.home() / f".openclaw/workspace-{agent}/.trigger/{project_id}_{task_id}.trigger"
        trigger_stale = False
        if trigger_file.exists():
            trigger_age = datetime.now() - datetime.fromtimestamp(trigger_file.stat().st_mtime)
            if trigger_age > timedelta(minutes=10):
                trigger_stale = True

        # 检测维度 3：ACK 文件缺失且触发文件超过 5 分钟
        ack_file = Path.home() / f".openclaw/workspace-{agent}/.trigger/{project_id}_{task_id}.ack"
        ack_missing = not ack_file.exists() and trigger_file.exists() and \
            (datetime.now() - datetime.fromtimestamp(trigger_file.stat().st_mtime)) > timedelta(minutes=5)

        reasons = []
        if has_start and not has_task_start:
            reasons.append("skills.log 有派发记录但无 task_start")
        if trigger_stale:
            reasons.append("触发文件超过 10 分钟")
        if ack_missing:
            reasons.append("Agent 未确认执行（无 ACK 文件）")

        is_zombie = bool(reasons)
        result = {
            "project": project_id, "queue": queue, "task_id": task_id, "agent": agent,
            "is_zombie": is_zombie, "reasons": reasons,
            "recommendation": "force_resume" if is_zombie else "wait",
        }

        logger = get_skill_logger(project_id)
        if is_zombie:
            logger.warning(f"[ZOMBIE_DETECTED] task={task_id}, agent={agent}, reasons={'; '.join(reasons)}", extra={'skill_name': 'MONITOR'})
        logger.info(f"[CHECK_STUCK] is_zombie={is_zombie}", extra={'skill_name': 'MONITOR'})
        return result
    except Exception as e:
        return {"project": project_id, "is_zombie": False, "error": str(e)}

def status():
    """检查所有项目任务状态"""
    queues = get_all_project_queues()
    
    if not queues:
        print("no_active_tasks")
        return
    
    for q in queues:
        project = q["project"]
        status = q["status"]
        
        # 检查是否在运行
        if status.startswith("running:"):
            task_id = status.split(":")[1]
            timeout_info = check_task_timeout(q["file"], project, task_id)
            
            print(f"{project}: {status}")
            if timeout_info.get("timeout"):
                print(f"  ⚠️ 超时: {timeout_info['age_minutes']}分钟 (阈值: {timeout_info['threshold_minutes']}分钟)")
        else:
            print(f"{project}: {status}")

def check_failed_and_retry(project_id: str) -> list:
    """检查失败任务并触发重试（任务1）"""
    import fcntl
    retried = []
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return retried

        lock_path = PROJECTS_DIR / project_id / ".task.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        with open(lock_path, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                with open(task_data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                tasks = data.get("tasks", [])
                modified = False

                for task in tasks:
                    if task.get("status") == "failed":
                        max_retries = task.get("max_retries", 0)
                        retry_count = task.get("retry_count", 0)

                        if retry_count < max_retries:
                            # 重置任务状态为 pending
                            task["status"] = "pending"
                            task["retry_count"] = retry_count + 1
                            task["failed_at"] = None
                            task["failure_reason"] = None
                            modified = True
                            retried.append({
                                "task_id": task["id"],
                                "task_name": task.get("name", ""),
                                "retry_number": retry_count + 1
                            })

                if modified:
                    with open(task_data_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    except Exception as e:
        print(f"Error in retry check: {e}", file=sys.stderr)

    return retried


def detect_deadlock(project_id: str) -> dict:
    """检测死锁任务（任务2）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"deadlock": False}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        task_map = {t["id"]: t for t in tasks}
        
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        
        deadlock_tasks = []
        blocked_tasks = []
        
        for task in pending_tasks:
            deps = task.get("dependencies", [])
            if not deps:
                continue  # 无依赖，不可能是死锁
            
            # 兼容两种格式：list 或 comma-separated string
            if isinstance(deps, str):
                dep_list = [d.strip() for d in deps.split(",") if d.strip()]
            else:
                dep_list = [str(d).strip() for d in deps if str(d).strip()]
            
            # 检查所有依赖是否完成
            all_deps_completed = all(
                task_map.get(dep, {}).get("status") == "completed"
                for dep in dep_list if dep in task_map
            )
            
            # 检查是否有依赖失败（无法继续）
            any_dep_failed = any(
                task_map.get(dep, {}).get("status") == "failed"
                for dep in dep_list if dep in task_map
            )
            
            if any_dep_failed:
                blocked_tasks.append({
                    "task_id": task["id"],
                    "task_name": task.get("name", ""),
                    "failed_dependency": [dep for dep in dep_list if task_map.get(dep, {}).get("status") == "failed"]
                })
            elif all_deps_completed and task.get("status") == "pending":
                # 依赖已完成但任务仍pending，可能是死锁
                deadlock_tasks.append({
                    "task_id": task["id"],
                    "task_name": task.get("name", "")
                })
        
        return {
            "deadlock": len(deadlock_tasks) > 0 or len(blocked_tasks) > 0,
            "deadlock_tasks": deadlock_tasks,
            "blocked_tasks": blocked_tasks
        }
    
    except Exception as e:
        return {"deadlock": False, "error": str(e)}


def calculate_progress(project_id: str) -> dict:
    """计算进度预测（任务4）- 简单平均"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"error": "Project not found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        
        completed = [t for t in tasks if t.get("status") == "completed"]
        in_progress = [t for t in tasks if t.get("status") == "in_progress"]
        pending = [t for t in tasks if t.get("status") == "pending"]
        
        # 计算已完成任务的平均耗时
        durations = []
        for task in completed:
            started = task.get("started_at")
            finished = task.get("completed_at")
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started)
                    end_dt = datetime.fromisoformat(finished)
                    duration = (end_dt - start_dt).total_seconds() / 60
                    durations.append(duration)
                except Exception:
                    pass
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # 预估剩余时间
        remaining_tasks = len(pending) + (1 if in_progress else 0)
        eta_minutes = avg_duration * remaining_tasks if avg_duration > 0 else None
        
        return {
            "total": len(tasks),
            "completed": len(completed),
            "in_progress": len(in_progress),
            "pending": len(pending),
            "avg_duration_minutes": round(avg_duration, 2) if avg_duration else 0,
            "eta_minutes": round(eta_minutes, 2) if eta_minutes else None,
            "progress_percent": round(len(completed) / len(tasks) * 100, 1) if tasks else 0
        }
    
    except Exception as e:
        return {"error": str(e)}


def check(project_keyword: str = None, auto_retry: bool = True):
    """检查特定项目或所有项目"""
    queues = get_all_project_queues()
    
    # 记录日志：开始监控
    logger = get_skill_logger("pro_global")
    logger.info(f"[MONITOR_CHECK_START] keyword={project_keyword}, projects_count={len(queues)}", extra={'skill_name': 'MONITOR'})
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "projects": []
    }
    
    for q in queues:
        if project_keyword and project_keyword not in q["project"]:
            continue
        
        project_id = q["project"]
        
        project = q["project"]
        status = q["status"]
        
        project_info = {
            "project": project,
            "status": status,
            "running_task": None,
            "timeout": False,
            "retried_tasks": [],
            "deadlock": None,
            "progress": None
        }
        
        # 任务1: 自动重试
        if auto_retry:
            retried = check_failed_and_retry(project)
            if retried:
                project_info["retried_tasks"] = retried
        
        # 任务2: 死锁检测
        deadlock_info = detect_deadlock(project)
        if deadlock_info.get("deadlock"):
            project_info["deadlock"] = deadlock_info
        
        # 任务4: 进度预测
        progress_info = calculate_progress(project)
        if progress_info and "error" not in progress_info:
            project_info["progress"] = progress_info
        
        # 任务5: 检测已完成但未调用task-complete的孤立任务
        orphaned = check_orphaned_completed_tasks(project)
        if orphaned:
            project_info["orphaned_tasks"] = orphaned
        
        if status.startswith("running:"):
            task_id = status.split(":")[1]
            project_info["running_task"] = task_id
            
            timeout_info = check_task_timeout(q["file"], project, task_id)
            project_info["timeout"] = timeout_info.get("timeout", False)
            project_info["age_minutes"] = timeout_info.get("age_minutes", 0)
            project_info["threshold_minutes"] = timeout_info.get("threshold_minutes", DEFAULT_TIMEOUT_MINUTES)
        
        result["projects"].append(project_info)
    
    # 记录日志：监控完成
    logger.info(f"[MONITOR_CHECK_END] projects_checked={len(result['projects'])}", extra={'skill_name': 'MONITOR'})
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


def get_project_stats(project_id: str) -> dict:
    """获取项目执行统计"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"error": "Project not found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        
        stats = {
            "project": project_id,
            "total_tasks": len(tasks),
            "completed": 0,
            "pending": 0,
            "in_progress": 0,
            "failed": 0,
            "total_duration_minutes": 0,
            "task_stats": []
        }
        
        for task in tasks:
            status = task.get("status", "pending")
            
            if status == "completed":
                stats["completed"] += 1
                # 计算执行时间
                started = task.get("started_at")
                completed = task.get("completed_at")
                if started and completed:
                    try:
                        start_dt = datetime.fromisoformat(started)
                        end_dt = datetime.fromisoformat(completed)
                        duration = (end_dt - start_dt).total_seconds() / 60
                        stats["total_duration_minutes"] += duration
                        stats["task_stats"].append({
                            "task_id": task["id"],
                            "task_name": task.get("name", ""),
                            "agent": task.get("agent", ""),
                            "duration_minutes": round(duration, 2),
                            "retry_count": task.get("retry_count", 0)
                        })
                    except Exception:
                        pass
            elif status == "pending":
                stats["pending"] += 1
            elif status == "in_progress":
                stats["in_progress"] += 1
            elif status == "failed":
                stats["failed"] += 1
        
        # 计算平均执行时间
        if stats["completed"] > 0:
            stats["avg_duration_minutes"] = round(stats["total_duration_minutes"] / stats["completed"], 2)
        else:
            stats["avg_duration_minutes"] = 0
        
        return stats
    except Exception as e:
        return {"error": str(e)}


def stats(project_keyword: str = None):
    """获取项目执行统计"""
    if project_keyword:
        # 查找匹配的项目
        matching_projects = []
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir() and project_keyword in project_dir.name:
                matching_projects.append(project_dir.name)
        
        if not matching_projects:
            print(f"未找到匹配的项目: {project_keyword}")
            return
        
        for proj in matching_projects:
            result = get_project_stats(proj)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 列出所有项目统计
        results = []
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                stat = get_project_stats(project_dir.name)
                if "error" not in stat:
                    results.append({
                        "project": stat["project"],
                        "total": stat["total_tasks"],
                        "completed": stat["completed"],
                        "in_progress": stat["in_progress"],
                        "failed": stat["failed"],
                        "avg_duration": stat.get("avg_duration_minutes", 0)
                    })
        
        if results:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("没有已完成的统计")


def check_task_stuck(project_id: str, task_id: str, threshold_minutes: int = 5) -> dict:
    """检测任务执行停滞（有进展但长时间无新活动）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"stuck": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        last_activity = None
        activity_count = 0
        
        for line in lines:
            if task_id in line:
                activity_count += 1
                try:
                    ts = line.split(']')[0].replace('[', '')
                    last_activity = ts
                except:
                    pass
        
        if not last_activity:
            return {"stuck": False, "reason": "no_activity"}
        
        from datetime import datetime
        try:
            last_dt = datetime.fromisoformat(last_activity)
            now = datetime.now()
            stuck_minutes = (now - last_dt).total_seconds() / 60
        except:
            return {"stuck": False, "reason": "parse_error"}
        
        is_stuck = stuck_minutes > threshold_minutes
        
        result = {
            "stuck": is_stuck,
            "task_id": task_id,
            "last_activity": last_activity,
            "stuck_minutes": round(stuck_minutes, 1),
            "threshold_minutes": threshold_minutes,
            "activity_count": activity_count,
            "recommendation": "investigate" if is_stuck else "normal"
        }
        
        logger = get_skill_logger(project_id)
        if is_stuck:
            logger.warning(f"[TASK_STUCK] task={task_id}, stuck={stuck_minutes}min", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"stuck": False, "error": str(e)}


def check_state_mismatch(project_id: str) -> dict:
    """检测状态不一致（队列状态 vs task_data 状态）"""
    try:
        queue_file = PROJECTS_DIR / project_id / ".task_queue"
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        
        if not queue_file.exists() or not task_data_file.exists():
            return {"mismatch": False, "reason": "file_not_found"}
        
        with open(queue_file, "r", encoding="utf-8") as f:
            queue_content = f.read().strip()
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        task_id = _parse_queue_task_id(queue_content)
        queue_status = "running"

        task_map = {t["id"]: t for t in task_data.get("tasks", [])}

        if not task_id or task_id not in task_map:
            return {"mismatch": False, "reason": "task_not_found"}
        
        task_status = task_map[task_id].get("status", "pending")
        
        status_map = {
            "running": "in_progress",
            "pending": "pending",
            "completed": "completed"
        }
        
        expected_task_status = status_map.get(queue_status, queue_status)
        is_mismatch = task_status != expected_task_status and not (queue_status == "running" and task_status == "pending")
        
        result = {
            "mismatch": is_mismatch or (queue_status == "running" and task_status == "pending"),
            "queue_status": queue_status,
            "task_status": task_status,
            "task_id": task_id,
            "severity": "warning" if (queue_status == "running" and task_status == "pending") else "info"
        }
        
        if result["mismatch"]:
            logger = get_skill_logger(project_id)
            logger.warning(f"[STATE_MISMATCH] queue={queue_status}, task={task_status}, task_id={task_id}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"mismatch": False, "error": str(e)}


def check_async_failure(project_id: str, task_id: str, agent_id: str = None) -> dict:
    """检测异步线程失败（有 DISPATCH_START 无 DISPATCH_END）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"failed": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        has_start = False
        has_end = False
        start_time = None
        end_time = None
        
        for line in lines:
            if task_id in line and "DISPATCH_START" in line:
                has_start = True
                try:
                    start_time = line.split(']')[0].replace('[', '')
                except:
                    pass
            if task_id in line and "DISPATCH_END" in line:
                has_end = True
                try:
                    end_time = line.split(']')[0].replace('[', '')
                except:
                    pass
        
        is_failed = has_start and not has_end
        
        result = {
            "failed": is_failed,
            "has_start": has_start,
            "has_end": has_end,
            "task_id": task_id,
            "agent_id": agent_id,
            "start_time": start_time,
            "end_time": end_time,
            "recommendation": "rescue_dispatch" if is_failed else "normal"
        }
        
        if is_failed:
            logger = get_skill_logger(project_id)
            logger.error(f"[ASYNC_FAILURE] task={task_id}, agent={agent_id}, thread_died", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"failed": False, "error": str(e)}


def detect_circular_dependency(project_id: str) -> dict:
    """检测循环依赖（任务依赖形成环）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"has_cycle": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        task_map = {t["id"]: t for t in tasks}
        
        # 构建依赖图（邻接表）
        graph = {}
        for task in tasks:
            task_id = task["id"]
            deps = task.get("dependencies", [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(",") if d.strip()]
            graph[task_id] = deps
        
        # DFS 检测环（三色标记法）
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {task_id: WHITE for task_id in graph}
        cycles = []
        
        def dfs(node, path):
            if node not in graph:
                return False
            if color[node] == GRAY:
                # 发现环
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return True
            if color[node] == BLACK:
                return False
            
            color[node] = GRAY
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if dfs(neighbor, path):
                    pass  # 继续检测其他环
            
            path.pop()
            color[node] = BLACK
            return False
        
        for task_id in graph:
            if color[task_id] == WHITE:
                dfs(task_id, [])
        
        result = {
            "has_cycle": len(cycles) > 0,
            "cycles": cycles,
            "cycle_count": len(cycles)
        }
        
        if result["has_cycle"]:
            logger = get_skill_logger(project_id)
            for cycle in cycles:
                logger.error(f"[CIRCULAR_DEPENDENCY] cycle={' -> '.join(cycle)}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"has_cycle": False, "error": str(e)}


def check_notification_missing(project_id: str, task_id: str) -> dict:
    """检测通知缺失（任务完成但未触发下游）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"missing": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        has_complete = False
        has_notify = False
        complete_time = None
        
        for line in lines:
            if task_id in line and "TASK_COMPLETE" in line:
                has_complete = True
                try:
                    complete_time = line.split(']')[0].replace('[', '')
                except:
                    pass
            if task_id in line and ("NOTIFY_SENT" in line or "NOTIFY_DEPENDENCY" in line):
                has_notify = True
        
        is_missing = has_complete and not has_notify
        
        result = {
            "missing": is_missing,
            "has_complete": has_complete,
            "has_notify": has_notify,
            "task_id": task_id,
            "complete_time": complete_time,
            "missing_type": "downstream_not_triggered" if is_missing else None
        }
        
        if is_missing:
            logger = get_skill_logger(project_id)
            logger.warning(f"[NOTIFICATION_MISSING] task={task_id}, complete but no notify", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"missing": False, "error": str(e)}


def detect_cascading_failure(project_id: str) -> dict:
    """检测级联失败（3 个 + 相关任务连续失败）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"cascading": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        failed_tasks = [t for t in tasks if t.get("status") == "failed"]
        
        if len(failed_tasks) < 3:
            return {"cascading": False, "reason": "insufficient_failures"}
        
        # 构建失败依赖链
        task_map = {t["id"]: t for t in tasks}
        failed_ids = {t["id"] for t in failed_tasks}
        
        # 检查是否有任务依赖多个失败任务
        cascading_chains = []
        for task in failed_tasks:
            deps = task.get("dependencies", [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(",") if d.strip()]
            
            failed_deps = [d for d in deps if d in failed_ids]
            if len(failed_deps) >= 2:
                cascading_chains.append({
                    "task_id": task["id"],
                    "failed_dependencies": failed_deps
                })
        
        result = {
            "cascading": len(cascading_chains) > 0,
            "failed_chain": cascading_chains,
            "chain_count": len(cascading_chains),
            "total_failed": len(failed_tasks)
        }
        
        if result["cascading"]:
            logger = get_skill_logger(project_id)
            logger.error(f"[CASCADING_FAILURE] {len(cascading_chains)} tasks affected by cascading failure", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"cascading": False, "error": str(e)}


def check_resource_exhaustion(project_id: str, threshold_pending: int = 5) -> dict:
    """检测资源耗尽（pending 任务过多且无空闲 Agent）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"exhausted": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        in_progress_tasks = [t for t in tasks if t.get("status") == "in_progress"]
        
        # 检查 session_map 获取 Agent 状态（与 notify_handshake.py 路径一致）
        session_map_file = Path.home() / ".openclaw" / "opencode_opencode_session_map.json"
        busy_agents = []
        if session_map_file.exists():
            with open(session_map_file, "r", encoding="utf-8") as f:
                session_map = json.load(f)
                busy_agents = list(session_map.keys())
        
        pending_count = len(pending_tasks)
        is_exhausted = pending_count >= threshold_pending and len(busy_agents) > 0
        
        result = {
            "exhausted": is_exhausted,
            "pending_count": pending_count,
            "pending_tasks": [t["id"] for t in pending_tasks],
            "busy_agents": busy_agents,
            "threshold": threshold_pending
        }
        
        if is_exhausted:
            logger = get_skill_logger(project_id)
            logger.warning(f"[RESOURCE_EXHAUSTION] pending={pending_count}, busy_agents={len(busy_agents)}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"exhausted": False, "error": str(e)}


def check_priority_conflict(project_id: str) -> dict:
    """检测任务优先级冲突（高优先级任务被低优先级阻塞）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"conflict": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        task_map = {t["id"]: t for t in tasks}
        
        # 定义优先级映射（数字越小优先级越高）
        priority_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        
        conflicts = []
        for task in tasks:
            task_priority = task.get("priority", "medium")
            task_priority_num = priority_map.get(task_priority, 3)
            
            if task.get("status") != "pending":
                continue
            
            deps = task.get("dependencies", [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(",") if d.strip()]
            
            for dep_id in deps:
                if dep_id not in task_map:
                    continue
                dep_task = task_map[dep_id]
                if dep_task.get("status") == "pending":
                    dep_priority = dep_task.get("priority", "medium")
                    dep_priority_num = priority_map.get(dep_priority, 3)
                    
                    # 如果当前任务优先级更高，但被低优先级依赖阻塞
                    if task_priority_num < dep_priority_num:
                        conflicts.append({
                            "high_priority_task": task["id"],
                            "high_priority": task_priority,
                            "blocked_by": dep_id,
                            "blocked_by_priority": dep_priority
                        })
        
        result = {
            "conflict": len(conflicts) > 0,
            "conflicts": conflicts,
            "conflict_count": len(conflicts)
        }
        
        if result["conflict"]:
            logger = get_skill_logger(project_id)
            for c in conflicts:
                logger.warning(f"[PRIORITY_CONFLICT] {c['high_priority_task']}({c['high_priority']}) blocked by {c['blocked_by']}({c['blocked_by_priority']})", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"conflict": False, "error": str(e)}


def check_agent_load_balance(project_id: str) -> dict:
    """检测 Agent 负载均衡（某些 Agent 过载而其他空闲）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"unbalanced": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        
        # 统计每个 Agent 的任务数
        agent_tasks = {}
        for task in tasks:
            agent = task.get("agent", "unknown")
            if agent not in agent_tasks:
                agent_tasks[agent] = {"total": 0, "in_progress": 0, "pending": 0, "completed": 0, "failed": 0}
            
            agent_tasks[agent]["total"] += 1
            status = task.get("status", "pending")
            if status in agent_tasks[agent]:
                agent_tasks[agent][status] += 1
        
        if len(agent_tasks) < 2:
            return {"unbalanced": False, "reason": "insufficient_agents"}
        
        # 计算负载差异
        total_tasks = sum(a["total"] for a in agent_tasks.values())
        avg_tasks = total_tasks / len(agent_tasks) if agent_tasks else 0
        
        unbalanced_agents = []
        for agent, stats in agent_tasks.items():
            # 如果 Agent 任务数偏离平均值超过 50%，视为不均衡
            if avg_tasks > 0:
                deviation = abs(stats["total"] - avg_tasks) / avg_tasks
                if deviation > 0.5:
                    unbalanced_agents.append({
                        "agent": agent,
                        "total_tasks": stats["total"],
                        "deviation_percent": round(deviation * 100, 1),
                        "status": "overloaded" if stats["total"] > avg_tasks else "underutilized"
                    })
        
        result = {
            "unbalanced": len(unbalanced_agents) > 0,
            "agent_stats": agent_tasks,
            "unbalanced_agents": unbalanced_agents,
            "avg_tasks_per_agent": round(avg_tasks, 2),
            "total_agents": len(agent_tasks)
        }
        
        if result["unbalanced"]:
            logger = get_skill_logger(project_id)
            for agent in unbalanced_agents:
                logger.warning(f"[LOAD_IMBALANCE] {agent['agent']}: {agent['total_tasks']} tasks ({agent['status']}, {agent['deviation_percent']}% deviation)", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"unbalanced": False, "error": str(e)}


def check_missing_dependencies(project_id: str) -> dict:
    """检测依赖缺失（任务依赖不存在的任务 ID）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"missing": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        task_ids = {t["id"] for t in tasks}
        
        missing_deps = []
        for task in tasks:
            deps = task.get("dependencies", [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(",") if d.strip()]
            
            for dep_id in deps:
                if dep_id and dep_id not in task_ids:
                    missing_deps.append({
                        "task_id": task["id"],
                        "task_name": task.get("name", ""),
                        "missing_dependency": dep_id
                    })
        
        result = {
            "missing": len(missing_deps) > 0,
            "missing_dependencies": missing_deps,
            "missing_count": len(missing_deps)
        }
        
        if result["missing"]:
            logger = get_skill_logger(project_id)
            for item in missing_deps:
                logger.error(f"[MISSING_DEPENDENCY] task={item['task_id']} depends on non-existent {item['missing_dependency']}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"missing": False, "error": str(e)}


def check_queue_lock_failure(project_id: str) -> dict:
    """检测队列锁定失败（队列文件存在但任务未执行）"""
    try:
        queue_file = PROJECTS_DIR / project_id / ".task_queue"
        if not queue_file.exists():
            return {"failed": False, "reason": "no_queue"}
        
        with open(queue_file, "r", encoding="utf-8") as f:
            queue_content = f.read().strip()

        task_id = _parse_queue_task_id(queue_content)
        if not task_id:
            return {"failed": False, "reason": "queue_empty"}
        
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"failed": True, "reason": "data_file_missing"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        task_map = {t["id"]: t for t in task_data.get("tasks", [])}
        
        if task_id not in task_map:
            return {"failed": True, "reason": "task_not_in_data", "task_id": task_id}
        
        task = task_map[task_id]
        task_status = task.get("status", "pending")
        
        if task_status == "failed":
            return {"failed": True, "reason": "task_failed", "task_id": task_id}
        
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"failed": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        has_lock = any("QUEUE_LOCK" in line and task_id in line for line in lines)
        has_release = any("QUEUE_RELEASE" in line and task_id in line for line in lines)
        
        if has_lock and not has_release and task_status != "in_progress":
            return {"failed": True, "reason": "lock_stale", "task_id": task_id}
        
        return {"failed": False, "task_id": task_id, "status": task_status}
    except Exception as e:
        return {"failed": False, "error": str(e)}


def check_data_integrity(project_id: str) -> dict:
    """检测 task_data.json 结构是否与 project-init / project-data 约定一致。"""
    try:
        pid = normalize_project_id(project_id)
        task_data_file = PROJECTS_DIR / pid / "task_data.json"
        if not task_data_file.exists():
            return {"corrupted": True, "reason": "file_not_found"}

        try:
            with open(task_data_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
        except json.JSONDecodeError as e:
            return {"corrupted": True, "reason": "json_parse_error", "error": str(e)}

        required_top = ["version", "project", "tasks"]
        missing_top = [k for k in required_top if k not in task_data]
        if missing_top:
            return {
                "corrupted": True,
                "reason": "missing_top_level_keys",
                "fields": missing_top,
            }

        if not isinstance(task_data.get("tasks"), list):
            return {"corrupted": True, "reason": "tasks_not_list"}

        proj = task_data.get("project")
        if not isinstance(proj, dict):
            return {"corrupted": True, "reason": "project_not_object"}

        missing_proj = [k for k in ("id", "status") if k not in proj]
        if missing_proj:
            return {
                "corrupted": True,
                "reason": "project_missing_keys",
                "fields": missing_proj,
            }

        tasks = task_data.get("tasks", [])
        invalid_tasks = []

        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                invalid_tasks.append({"index": i, "reason": "not_dict"})
                continue

            if "id" not in task:
                invalid_tasks.append({"index": i, "reason": "missing_id"})

            if "status" not in task:
                invalid_tasks.append({"index": i, "reason": "missing_status"})

            if "agent" not in task:
                invalid_tasks.append({"index": i, "reason": "missing_agent"})

        result = {
            "corrupted": len(invalid_tasks) > 0,
            "invalid_tasks": invalid_tasks,
            "total_tasks": len(tasks),
            "valid_tasks": len(tasks) - len(invalid_tasks),
        }

        if result["corrupted"]:
            logger = get_skill_logger(pid)
            logger.error(
                f"[DATA_INTEGRITY] {len(invalid_tasks)} invalid tasks found",
                extra={"skill_name": "MONITOR"},
            )

        return result
    except Exception as e:
        return {"corrupted": True, "error": str(e)}


def check_subtask_status(project_id: str) -> dict:
    """检测子任务状态（主任务完成但子任务未完成）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"mismatch": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        tasks = task_data.get("tasks", [])
        
        completed_parents = [t for t in tasks if t.get("status") == "completed"]
        
        issues = []
        for parent in completed_parents:
            parent_id = parent["id"]
            subtasks = [t for t in tasks if t.get("parent_task_id") == parent_id or t.get("id", "").startswith(f"{parent_id}_sub")]
            
            if not subtasks:
                continue
            
            incomplete_subtasks = [t for t in subtasks if t.get("status") != "completed"]
            
            if incomplete_subtasks:
                issues.append({
                    "parent_task_id": parent_id,
                    "parent_name": parent.get("name", ""),
                    "incomplete_subtasks": [
                        {"task_id": t["id"], "status": t.get("status", "unknown")}
                        for t in incomplete_subtasks
                    ]
                })
        
        result = {
            "mismatch": len(issues) > 0,
            "issues": issues,
            "issue_count": len(issues)
        }
        
        if result["mismatch"]:
            logger = get_skill_logger(project_id)
            for issue in issues:
                logger.warning(f"[SUBTASK_STATUS] parent={issue['parent_task_id']} has {len(issue['incomplete_subtasks'])} incomplete subtasks", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"mismatch": False, "error": str(e)}


def _glob_trigger_files(task_id: str) -> list:
    """
    列出 ~/.openclaw/workspace-*/.trigger/*{task_id}*.trigger。
    注意：Path('.openclaw/workspace-*') 会把 * 当成字面目录名，永远不存在；
    必须在 .openclaw 上对 workspace-* 做 glob，再进入各 .trigger 目录。
    """
    root = Path.home() / ".openclaw"
    out: list = []
    try:
        for ws in sorted(root.glob("workspace-*")):
            if not ws.is_dir():
                continue
            trig_dir = ws / ".trigger"
            if not trig_dir.is_dir():
                continue
            out.extend(trig_dir.glob(f"*{task_id}*.trigger"))
    except OSError:
        pass
    return out


def check_trigger_creation(project_id: str) -> dict:
    """检测 Trigger 文件创建失败（队列锁定但无 trigger 文件）"""
    try:
        queue_file = PROJECTS_DIR / project_id / ".task_queue"
        if not queue_file.exists():
            return {"failed": False, "reason": "no_queue"}
        
        with open(queue_file, "r", encoding="utf-8") as f:
            queue_content = f.read().strip()

        task_id = _parse_queue_task_id(queue_content)
        if not task_id:
            return {"failed": False, "reason": "queue_empty"}
        
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"failed": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        has_dispatch_start = any("DISPATCH_START" in line and task_id in line for line in lines)
        has_trigger_created = any("TRIGGER_CREATED" in line and task_id in line for line in lines)
        
        if has_dispatch_start and not has_trigger_created:
            return {"failed": True, "reason": "trigger_not_created", "task_id": task_id}
        
        trigger_files = _glob_trigger_files(task_id)
        if has_dispatch_start and not trigger_files:
            return {"failed": True, "reason": "trigger_file_missing", "task_id": task_id}
        
        return {"failed": False, "task_id": task_id}
    except Exception as e:
        return {"failed": False, "error": str(e)}


def check_trigger_cleanup(project_id: str) -> dict:
    """检测 Trigger 文件未清理（任务完成但 trigger 文件仍存在）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"uncleaned": False, "reason": "file_not_found"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        completed_tasks = [t for t in task_data.get("tasks", []) if t.get("status") == "completed"]
        
        uncleared = []
        for task in completed_tasks:
            task_id = task["id"]
            
            lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
            if not lf.exists():
                continue
            
            with open(lf, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            has_trigger_cleaned = any("TRIGGER_CLEANED" in line and task_id in line for line in lines)
            
            if not has_trigger_cleaned:
                trigger_files = _glob_trigger_files(task_id)
                if trigger_files:
                    uncleared.append({
                        "task_id": task_id,
                        "trigger_files": [str(f) for f in trigger_files]
                    })
        
        result = {
            "uncleaned": len(uncleared) > 0,
            "uncleared_tasks": uncleared,
            "uncleared_count": len(uncleared)
        }
        
        if result["uncleaned"]:
            logger = get_skill_logger(project_id)
            for item in uncleared:
                logger.warning(f"[TRIGGER_UNCLEANED] task={item['task_id']}, files={len(item['trigger_files'])}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"uncleaned": False, "error": str(e)}


def check_queue_stale(project_id: str) -> dict:
    """检测队列未释放（任务完成但队列仍锁定）"""
    try:
        queue_file = PROJECTS_DIR / project_id / ".task_queue"
        if not queue_file.exists():
            return {"stale": False, "reason": "no_queue"}
        
        with open(queue_file, "r", encoding="utf-8") as f:
            queue_content = f.read().strip()
        
        if not queue_content:
            return {"stale": False, "reason": "queue_empty"}
        
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"stale": False, "reason": "data_file_missing"}
        
        with open(task_data_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        task_id = queue_content.split(":")[-1] if ":" in queue_content else queue_content
        task_map = {t["id"]: t for t in task_data.get("tasks", [])}
        
        if task_id not in task_map:
            return {"stale": True, "reason": "task_not_found", "task_id": task_id}
        
        task_status = task_map[task_id].get("status", "pending")
        
        if task_status == "completed":
            return {"stale": True, "reason": "task_completed_queue_locked", "task_id": task_id}
        
        if task_status == "failed":
            return {"stale": True, "reason": "task_failed_queue_locked", "task_id": task_id}
        
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if lf.exists():
            with open(lf, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            has_release = any("QUEUE_RELEASE" in line for line in lines)
            if not has_release and task_status in ["completed", "failed"]:
                return {"stale": True, "reason": "no_release_log", "task_id": task_id}
        
        return {"stale": False, "task_id": task_id, "status": task_status}
    except Exception as e:
        return {"stale": False, "error": str(e)}


def check_notification_delivery(project_id: str) -> dict:
    """检测通知发送失败（有通知意图但无送达确认）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"failed": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        notify_starts = []
        notify_sents = []
        
        for line in lines:
            if "AGENT_NOTIFY_START" in line or "NOTIFY_START" in line:
                try:
                    ts = line.split(']')[0].replace('[', '')
                    notify_starts.append({"timestamp": ts, "line": line})
                except:
                    pass
            if "NOTIFY_SENT" in line or "AGENT_MSG_SUCCESS" in line:
                try:
                    ts = line.split(']')[0].replace('[', '')
                    notify_sents.append({"timestamp": ts, "line": line})
                except:
                    pass
        
        if len(notify_starts) > len(notify_sents):
            return {
                "failed": True,
                "reason": "missing_delivery_confirmation",
                "notify_count": len(notify_starts),
                "sent_count": len(notify_sents),
                "missing_count": len(notify_starts) - len(notify_sents)
            }
        
        return {"failed": False, "notify_count": len(notify_starts), "sent_count": len(notify_sents)}
    except Exception as e:
        return {"failed": False, "error": str(e)}


def check_subtask_creation(project_id: str) -> dict:
    """检测子任务创建失败（主任务有 subtask_start 但无 subtask_created）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"failed": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        subtask_starts = []
        subtask_createds = []
        
        for line in lines:
            if "subtask_start" in line.lower():
                try:
                    parts = line.split("args=")
                    if len(parts) > 1:
                        args = ast.literal_eval(parts[1].strip())
                        if len(args) >= 3:
                            subtask_id = args[2]
                            subtask_starts.append({"subtask_id": subtask_id, "line": line})
                except:
                    pass
            if "subtask_created" in line.lower():
                try:
                    parts = line.split("args=")
                    if len(parts) > 1:
                        args = ast.literal_eval(parts[1].strip())
                        if len(args) >= 3:
                            subtask_id = args[2]
                            subtask_createds.append({"subtask_id": subtask_id, "line": line})
                except:
                    pass
        
        start_ids = {s["subtask_id"] for s in subtask_starts}
        created_ids = {c["subtask_id"] for c in subtask_createds}
        
        missing_created = start_ids - created_ids
        
        if missing_created:
            return {
                "failed": True,
                "reason": "subtask_created_missing",
                "missing_subtasks": list(missing_created),
                "missing_count": len(missing_created)
            }
        
        return {"failed": False, "total_subtasks": len(start_ids)}
    except Exception as e:
        return {"failed": False, "error": str(e)}


def check_subtask_stuck(project_id: str) -> dict:
    """检测子任务执行卡住（subtask_start 后长时间无 subtask_complete）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"stuck": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        subtask_events = {}
        
        for line in lines:
            if "subtask_start" in line.lower() or "subtask_complete" in line.lower():
                try:
                    ts = line.split(']')[0].replace('[', '')
                    parts = line.split("args=")
                    if len(parts) > 1:
                        args = ast.literal_eval(parts[1].strip())
                        if len(args) >= 3:
                            subtask_id = args[2]
                            event_type = "start" if "start" in line.lower() else "complete"
                            
                            if subtask_id not in subtask_events:
                                subtask_events[subtask_id] = {}
                            
                            if event_type == "start":
                                subtask_events[subtask_id]["start"] = ts
                            else:
                                subtask_events[subtask_id]["complete"] = ts
                except:
                    pass
        
        from datetime import datetime
        stuck_subtasks = []
        
        for subtask_id, events in subtask_events.items():
            if "start" in events and "complete" not in events:
                try:
                    start_dt = datetime.fromisoformat(events["start"])
                    now = datetime.now()
                    stuck_minutes = (now - start_dt).total_seconds() / 60
                    
                    if stuck_minutes > 10:
                        stuck_subtasks.append({
                            "subtask_id": subtask_id,
                            "start_time": events["start"],
                            "stuck_minutes": round(stuck_minutes, 1)
                        })
                except:
                    pass
        
        result = {
            "stuck": len(stuck_subtasks) > 0,
            "stuck_subtasks": stuck_subtasks,
            "stuck_count": len(stuck_subtasks)
        }
        
        if result["stuck"]:
            logger = get_skill_logger(project_id)
            for subtask in stuck_subtasks:
                logger.warning(f"[SUBTASK_STUCK] {subtask['subtask_id']} stuck for {subtask['stuck_minutes']}min", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"stuck": False, "error": str(e)}


def check_status_transition(project_id: str) -> dict:
    """检测任务状态跳跃（如 pending → completed 跳过 in_progress）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"jumped": False, "reason": "no_log"}
        
        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        task_transitions = {}
        
        for line in lines:
            if "TASK_STATUS_UPDATED" in line or "status=" in line:
                try:
                    if "task=" in line or "task_id=" in line:
                        parts = line.split("task=")
                        if len(parts) > 1:
                            task_id = parts[1].split(",")[0].split()[0]
                            
                            if "status=pending" in line:
                                task_transitions[task_id] = task_transitions.get(task_id, []) + ["pending"]
                            elif "status=in_progress" in line or "status=in_progress" in line.lower():
                                task_transitions[task_id] = task_transitions.get(task_id, []) + ["in_progress"]
                            elif "status=completed" in line:
                                task_transitions[task_id] = task_transitions.get(task_id, []) + ["completed"]
                except:
                    pass
        
        jumps = []
        for task_id, transitions in task_transitions.items():
            if len(transitions) >= 2:
                for i in range(len(transitions) - 1):
                    curr = transitions[i]
                    next_status = transitions[i + 1]
                    
                    if curr == "pending" and next_status == "completed":
                        jumps.append({
                            "task_id": task_id,
                            "from": curr,
                            "to": next_status,
                            "expected": "pending -> in_progress -> completed"
                        })
        
        result = {
            "jumped": len(jumps) > 0,
            "jumps": jumps,
            "jump_count": len(jumps)
        }
        
        if result["jumped"]:
            logger = get_skill_logger(project_id)
            for jump in jumps:
                logger.warning(f"[STATUS_JUMP] {jump['task_id']}: {jump['from']} -> {jump['to']} (skipped in_progress)", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"jumped": False, "error": str(e)}


def check_agent_comm_timeout(project_id: str) -> dict:
    """检测 Agent 通信超时：以 [AGENT_NOTIFY] NOTIFY_DISPATCH_START 为起点，以 NOTIFY_DISPATCH_END / AGENT_MSG_SUCCESS 为终点。"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        if not lf.exists():
            return {"timeout": False, "reason": "no_log"}

        with open(lf, "r", encoding="utf-8") as f:
            lines = f.readlines()

        from datetime import datetime

        def _parse_ts(line: str):
            ts_str = line.split("]")[0].replace("[", "")
            return datetime.fromisoformat(ts_str)

        def _field(line: str, key: str) -> str | None:
            token = f"{key}="
            if token not in line:
                return None
            return line.split(token, 1)[1].split(",")[0].split()[0]

        # key: (agent, task_id) -> {start, end}
        notify_events: dict[tuple[str, str], dict] = {}

        for line in lines:
            try:
                if "[NOTIFY_DISPATCH_START]" in line and "[AGENT_NOTIFY]" in line:
                    agent = _field(line, "agent")
                    task_id = _field(line, "task")
                    if agent and task_id:
                        notify_events[(agent, task_id)] = {
                            "start": _parse_ts(line),
                            "end": None,
                        }
                elif "[NOTIFY_DISPATCH_END]" in line and "[AGENT_NOTIFY]" in line:
                    agent = _field(line, "agent")
                    task_id = _field(line, "task")
                    if agent and task_id and (agent, task_id) in notify_events:
                        notify_events[(agent, task_id)]["end"] = _parse_ts(line)
                elif "[AGENT_MSG_SUCCESS]" in line and "[AGENT_NOTIFY]" in line:
                    agent = _field(line, "agent")
                    if not agent:
                        continue
                    for key, events in notify_events.items():
                        if key[0] == agent and events["end"] is None:
                            events["end"] = _parse_ts(line)
                elif "[AGENT_NOTIFY_NEVER_STARTED]" in line:
                    agent = _field(line, "agent")
                    task_id = _field(line, "task")
                    if agent and task_id:
                        notify_events[(agent, task_id)] = {
                            "start": _parse_ts(line),
                            "end": _parse_ts(line),
                            "never_started": True,
                        }
            except Exception:
                pass

        timeouts = []
        now = datetime.now()
        threshold_min = 5

        for (agent, task_id), events in notify_events.items():
            if events.get("never_started"):
                timeouts.append(
                    {
                        "agent": agent,
                        "task_id": task_id,
                        "start_time": events["start"].isoformat(),
                        "duration_minutes": 0,
                        "reason": "never_started",
                    }
                )
                continue
            if events["start"] and not events["end"]:
                duration = (now - events["start"]).total_seconds() / 60
                if duration > threshold_min:
                    timeouts.append(
                        {
                            "agent": agent,
                            "task_id": task_id,
                            "start_time": events["start"].isoformat(),
                            "duration_minutes": round(duration, 1),
                        }
                    )

        result = {
            "timeout": len(timeouts) > 0,
            "timeouts": timeouts,
            "timeout_count": len(timeouts),
        }

        if result["timeout"]:
            logger = get_skill_logger(project_id)
            for t in timeouts:
                tid = t.get("task_id", "?")
                logger.warning(
                    f"[AGENT_COMM_TIMEOUT] agent={t['agent']}, task={tid}, "
                    f"duration={t.get('duration_minutes', 0)}min, reason={t.get('reason', 'in_flight')}",
                    extra={"skill_name": "MONITOR"},
                )

        return result
    except Exception as e:
        return {"timeout": False, "error": str(e)}


def check_project_init(project_id: str) -> dict:
    """检测项目初始化失败（无 PROJECT_INIT 日志或 task_data.json 为空）"""
    try:
        lf = PROJECTS_DIR / project_id / "skill-logs" / "skills.log"
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        
        issues = []
        
        if lf.exists():
            with open(lf, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            has_init = any("PROJECT_INIT" in line for line in lines)
            if not has_init:
                issues.append({
                    "type": "missing_init_log",
                    "description": "No PROJECT_INIT log found"
                })
        else:
            issues.append({
                "type": "no_log_file",
                "description": "skills.log file not found"
            })
        
        if task_data_file.exists():
            try:
                with open(task_data_file, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                
                tasks = task_data.get("tasks", [])
                if not tasks:
                    issues.append({
                        "type": "no_tasks",
                        "description": "task_data.json has no tasks"
                    })
            except json.JSONDecodeError:
                issues.append({
                    "type": "invalid_json",
                    "description": "task_data.json is not valid JSON"
                })
        else:
            issues.append({
                "type": "no_task_data",
                "description": "task_data.json file not found"
            })
        
        result = {
            "failed": len(issues) > 0,
            "issues": issues,
            "issue_count": len(issues)
        }
        
        if result["failed"]:
            logger = get_skill_logger(project_id)
            for issue in issues:
                logger.error(f"[PROJECT_INIT_FAILED] {issue['type']}: {issue['description']}", extra={'skill_name': 'MONITOR'})
        
        return result
    except Exception as e:
        return {"failed": False, "error": str(e)}


def check_waiting_for_input_timeout(project_id: str, threshold_minutes: int = 30) -> dict:
    """检测 waiting_for_input 超时（任务等待用户输入超过阈值）"""
    try:
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if not task_data_file.exists():
            return {"timeout": False, "reason": "file_not_found"}

        with open(task_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        timed_out_tasks = []
        for task in data.get("tasks", []):
            if task.get("status") != "waiting_for_input":
                continue
            waiting_since = task.get("waiting_since")
            if not waiting_since:
                continue
            try:
                waiting_dt = datetime.fromisoformat(waiting_since)
                age_minutes = (datetime.now() - waiting_dt).total_seconds() / 60
                if age_minutes > threshold_minutes:
                    timed_out_tasks.append({
                        "task_id": task["id"],
                        "task_name": task.get("name", ""),
                        "agent": task.get("agent", ""),
                        "waiting_since": waiting_since,
                        "age_minutes": round(age_minutes, 1),
                        "threshold_minutes": threshold_minutes,
                    })
            except Exception:
                continue

        result = {
            "timeout": len(timed_out_tasks) > 0,
            "timed_out_tasks": timed_out_tasks,
            "timeout_count": len(timed_out_tasks),
        }

        if result["timeout"]:
            logger = get_skill_logger(project_id)
            for t in timed_out_tasks:
                logger.warning(
                    f"[WAITING_INPUT_TIMEOUT] task={t['task_id']}, agent={t['agent']}, "
                    f"waiting={t['age_minutes']}min (threshold={threshold_minutes}min)",
                    extra={"skill_name": "MONITOR"},
                )

        return result
    except Exception as e:
        return {"timeout": False, "error": str(e)}


def check_agent_session_stuck(project_id: str) -> dict:
    """检测 Agent 会话是否假死

    检查所有 in_progress 任务的 Agent 会话状态：
    - 如果 trigger 文件存在 > 30 分钟且无 ACK 文件，判定为假死
    - 不依赖 session_map 的 last_used（该字段不会被更新）
    """
    try:
        project_file = PROJECTS_DIR / project_id / "task_data.json"
        if not project_file.exists():
            return {"stuck": False, "reason": "no_project_data"}

        with open(project_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        stuck_sessions = []
        now = time.time()

        for task in task_data.get("tasks", []):
            if task.get("status") != "in_progress":
                continue
            agent_id = task.get("agent", "")
            task_id = task.get("id", "")
            if not agent_id:
                continue

            trigger_file = Path.home() / ".openclaw" / f"workspace-{agent_id}" / ".trigger" / f"{project_id}_{task_id}.trigger"
            ack_file = Path.home() / ".openclaw" / f"workspace-{agent_id}" / ".trigger" / f"{project_id}_{task_id}.ack"

            if not trigger_file.exists():
                # No trigger file — task might have been started manually
                # Check if any subtask has made progress recently
                subtasks = task.get("subtasks", [])
                has_recent_activity = any(
                    s.get("status") == "in_progress" or s.get("completed_at")
                    for s in subtasks
                )
                if not has_recent_activity:
                    stuck_sessions.append({
                        "agent": agent_id,
                        "task_id": task_id,
                        "reason": "任务 in_progress 但无 trigger 文件且无子任务进展",
                    })
                continue

            # Trigger file exists — check age and ACK
            age_minutes = (now - trigger_file.stat().st_mtime) / 60
            if age_minutes > 30 and not ack_file.exists():
                stuck_sessions.append({
                    "agent": agent_id,
                    "task_id": task_id,
                    "reason": f"trigger 存在 {age_minutes:.0f} 分钟且无 ACK",
                    "age_minutes": round(age_minutes, 1),
                })
                continue

            # Trigger exists, ACK exists, but no subtask progress
            if ack_file.exists():
                subtasks = task.get("subtasks", [])
                has_progress = any(
                    s.get("status") == "completed" or
                    (s.get("status") == "in_progress" and s.get("started_at"))
                    for s in subtasks
                )
                if not has_progress and age_minutes > 30:
                    stuck_sessions.append({
                        "agent": agent_id,
                        "task_id": task_id,
                        "reason": f"有 ACK 但 {age_minutes:.0f} 分钟无子任务进展",
                        "age_minutes": round(age_minutes, 1),
                    })

        result = {
            "stuck": len(stuck_sessions) > 0,
            "stuck_sessions": stuck_sessions,
            "stuck_count": len(stuck_sessions),
        }

        if result["stuck"]:
            logger = get_skill_logger(project_id)
            for s in stuck_sessions:
                logger.warning(
                    f"[AGENT_SESSION_STUCK] agent={s['agent']}, task={s['task_id']}, reason={s['reason']}",
                    extra={"skill_name": "MONITOR"},
                )

        return result
    except Exception as e:
        return {"stuck": False, "error": str(e)}


def check_trigger_not_consumed(project_id: str) -> dict:
    """检测 trigger 文件未被 Agent 消费

    检查所有 in_progress 任务的 trigger 文件是否存在。
    如果 trigger 文件存在超过 5 分钟且无对应 .ack 文件，视为未被消费。
    """
    try:
        project_file = PROJECTS_DIR / project_id / "task_data.json"
        if not project_file.exists():
            return {"unconsumed": False, "reason": "no_project_data"}

        with open(project_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        unconsumed_triggers = []
        now = time.time()

        for task in task_data.get("tasks", []):
            if task.get("status") != "in_progress":
                continue
            agent_id = task.get("agent", "")
            task_id = task.get("id", "")
            if not agent_id:
                continue

            trigger_file = Path.home() / ".openclaw" / f"workspace-{agent_id}" / ".trigger" / f"{project_id}_{task_id}.trigger"
            ack_file = Path.home() / ".openclaw" / f"workspace-{agent_id}" / ".trigger" / f"{project_id}_{task_id}.ack"

            if not trigger_file.exists():
                continue

            # Trigger file exists — check age
            age_minutes = (now - trigger_file.stat().st_mtime) / 60
            if age_minutes < 5:
                continue  # Too young, give agent time to process

            # Check if ACK file exists
            if ack_file.exists():
                continue  # Agent has confirmed, trigger just wasn't cleaned

            unconsumed_triggers.append({
                "agent": agent_id,
                "task_id": task_id,
                "age_minutes": round(age_minutes, 1),
                "trigger_file": str(trigger_file),
            })

        result = {
            "unconsumed": len(unconsumed_triggers) > 0,
            "unconsumed_triggers": unconsumed_triggers,
            "unconsumed_count": len(unconsumed_triggers),
        }

        if result["unconsumed"]:
            logger = get_skill_logger(project_id)
            for t in unconsumed_triggers:
                logger.warning(
                    f"[TRIGGER_NOT_CONSUMED] agent={t['agent']}, task={t['task_id']}, "
                    f"age={t['age_minutes']}min",
                    extra={"skill_name": "MONITOR"},
                )

        return result
    except Exception as e:
        return {"unconsumed": False, "error": str(e)}


def check_deputy_health() -> dict:
    """检查 Deputy Agent 自身是否健康运行

    通过读取 Deputy 的 heartbeat.json 检查心跳是否过期。
    如果心跳超过 15 分钟未更新，视为 Deputy 可能掉线。
    """
    try:
        heartbeat_file = Path.home() / ".openclaw" / "workspace-deputy" / "state" / "heartbeat.json"
        if not heartbeat_file.exists():
            return {"healthy": False, "reason": "心跳文件不存在"}

        with open(heartbeat_file, "r", encoding="utf-8") as f:
            hb = json.load(f)

        last_heartbeat_str = hb.get("timestamp", "")
        if not last_heartbeat_str:
            return {"healthy": False, "reason": "心跳文件无时间戳"}

        # Handle 'Z' suffix for UTC
        normalized_ts = last_heartbeat_str.replace("Z", "+00:00")
        last_dt = datetime.fromisoformat(normalized_ts)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if last_dt.tzinfo is not None:
            last_dt = last_dt.replace(tzinfo=None)

        minutes_since = (now - last_dt).total_seconds() / 60
        is_healthy = minutes_since <= 15

        return {
            "healthy": is_healthy,
            "last_heartbeat": last_heartbeat_str,
            "minutes_since_heartbeat": round(minutes_since, 1),
            "reason": "" if is_healthy else f"心跳已过期 {minutes_since:.0f} 分钟",
        }
    except Exception as e:
        return {"healthy": False, "reason": f"检查异常: {e}"}


def health(project_id: str) -> dict:
    """全面健康检查（集成所有检测）"""
    project_id = normalize_project_id(project_id)
    result = {
        "project_id": project_id,
        "timestamp": datetime.now().isoformat(),
        "healthy": True,
        "summary": {
            "zombie_count": 0,
            "timeout_count": 0,
            "stuck_count": 0,
            "mismatch_count": 0,
            "async_failure_count": 0,
            "deadlock_count": 0,
            "orphan_count": 0,
            "circular_count": 0,
            "notification_missing_count": 0,
            "cascading_count": 0,
            "resource_exhaustion_count": 0,
            "priority_conflict_count": 0,
            "load_imbalance_count": 0,
            "missing_dependency_count": 0,
            "queue_lock_failure_count": 0,
            "data_integrity_count": 0,
            "subtask_status_count": 0,
            "trigger_creation_count": 0,
            "trigger_cleanup_count": 0,
            "queue_stale_count": 0,
            "notification_delivery_count": 0,
            "subtask_creation_count": 0,
            "subtask_stuck_count": 0,
            "status_jump_count": 0,
            "agent_comm_timeout_count": 0,
            "project_init_count": 0,
            "graph_invalid_count": 0,
            "waiting_input_timeout_count": 0,
            "agent_session_stuck_count": 0,
            "trigger_not_consumed_count": 0,
            "deputy_healthy": True,
        },
        "issues": [],
        "recommendations": [],
        "paths": {
            "project_dir": str(PROJECTS_DIR / project_id),
            "task_data_json": str(PROJECTS_DIR / project_id / "task_data.json"),
            "skill_logs": str(PROJECTS_DIR / project_id / "skill-logs" / "skills.log"),
        },
    }

    try:
        graph_info = check_graph_validation(project_id)
        result["graph_validation"] = graph_info
        if not graph_info.get("ok"):
            result["healthy"] = False
            result["summary"]["graph_invalid_count"] = 1
            result["issues"].append(
                {
                    "type": "graph_invalid",
                    "severity": "critical",
                    "description": graph_info.get("stderr")
                    or graph_info.get("stdout")
                    or "task graph failed project-data check-cycle",
                    "details": graph_info,
                }
            )
            result["recommendations"].append(
                "fix_dependencies_or_run_project_data_check_cycle"
            )

        queue_file = PROJECTS_DIR / project_id / ".task_queue"
        if not queue_file.exists():
            result["message"] = "No active queue"
            return result

        with open(queue_file, "r", encoding="utf-8") as f:
            queue_content = f.read().strip()

        task_id = _parse_queue_task_id(queue_content)
        is_running = bool(task_id)
        
        if is_running and task_id:
            stuck_result = check_task_stuck(project_id, task_id, threshold_minutes=5)
            if stuck_result.get("stuck"):
                result["healthy"] = False
                result["summary"]["stuck_count"] = 1
                result["issues"].append({
                    "type": "stuck",
                    "severity": "warning",
                    "task_id": task_id,
                    "description": f"任务 {task_id} 执行停滞 - 最后活动{stuck_result.get('stuck_minutes')}分钟前",
                    "details": stuck_result
                })
                result["recommendations"].append("investigate")
            
            mismatch_result = check_state_mismatch(project_id)
            if mismatch_result.get("mismatch"):
                result["healthy"] = False
                result["summary"]["mismatch_count"] = 1
                result["issues"].append({
                    "type": "state_mismatch",
                    "severity": mismatch_result.get("severity", "warning"),
                    "task_id": task_id,
                    "description": f"状态不一致 - 队列={mismatch_result.get('queue_status')}, 任务={mismatch_result.get('task_status')}",
                    "details": mismatch_result
                })
                result["recommendations"].append("sync_state")
            
            task_data_file = PROJECTS_DIR / project_id / "task_data.json"
            if task_data_file.exists():
                with open(task_data_file, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                task_map = {t["id"]: t for t in task_data.get("tasks", [])}
                if task_id in task_map:
                    agent = task_map[task_id].get("agent", "")
                    async_result = check_async_failure(project_id, task_id, agent)
                    if async_result.get("failed"):
                        result["healthy"] = False
                        result["summary"]["async_failure_count"] = 1
                        result["issues"].append({
                            "type": "async_failure",
                            "severity": "critical",
                            "task_id": task_id,
                            "agent_id": agent,
                            "description": f"异步线程失败 - 任务 {task_id} 有 DISPATCH_START 无 DISPATCH_END",
                            "details": async_result
                        })
                        result["recommendations"].append("rescue_dispatch")
        
        deadlock_result = detect_deadlock(project_id)
        if deadlock_result.get("deadlock"):
            result["healthy"] = False
            deadlock_tasks = deadlock_result.get("deadlock_tasks", [])
            blocked_tasks = deadlock_result.get("blocked_tasks", [])
            result["summary"]["deadlock_count"] = len(deadlock_tasks) + len(blocked_tasks)
            for task in deadlock_tasks:
                result["issues"].append({
                    "type": "deadlock",
                    "severity": "critical",
                    "task_id": task["task_id"],
                    "description": f"死锁 - 任务 {task['task_id']} 依赖已完成但仍 pending",
                    "details": task
                })
            for task in blocked_tasks:
                result["issues"].append({
                    "type": "blocked",
                    "severity": "warning",
                    "task_id": task["task_id"],
                    "description": f"阻塞 - 任务 {task['task_id']} 有依赖失败",
                    "details": task
                })
            result["recommendations"].append("manual_check")
        
        orphaned = check_orphaned_completed_tasks(project_id)
        if orphaned:
            result["healthy"] = False
            result["summary"]["orphan_count"] = len(orphaned)
            for task in orphaned:
                result["issues"].append({
                    "type": "orphaned",
                    "severity": "warning",
                    "task_id": task["task_id"],
                    "description": f"孤立任务 - 任务 {task['task_id']} 已执行但 missing task-complete",
                    "details": task
                })
            result["recommendations"].append("call_task_complete")

        # 循环依赖：已由 health 开头的 graph_validation（project-data check-cycle / Kahn）统一覆盖，避免与 graph_invalid 重复告警

        # P1-2: 通知缺失检测（检测已完成任务）
        task_data_file = PROJECTS_DIR / project_id / "task_data.json"
        if task_data_file.exists():
            with open(task_data_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
            completed_tasks = [t for t in task_data.get("tasks", []) if t.get("status") == "completed"]
            for task in completed_tasks[:10]:  # 限制检查最近 10 个
                notify_result = check_notification_missing(project_id, task["id"])
                if notify_result.get("missing"):
                    result["healthy"] = False
                    result["summary"]["notification_missing_count"] += 1
                    result["issues"].append({
                        "type": "notification_missing",
                        "severity": "warning",
                        "task_id": task["id"],
                        "description": f"通知缺失 - 任务 {task['id']} 完成但未触发下游",
                        "details": notify_result
                    })
                    result["recommendations"].append("trigger_downstream")
        
        # P1-3: 级联失败检测
        cascading = detect_cascading_failure(project_id)
        if cascading.get("cascading"):
            result["healthy"] = False
            result["summary"]["cascading_count"] = cascading.get("chain_count", 0)
            for chain in cascading.get("failed_chain", []):
                result["issues"].append({
                    "type": "cascading_failure",
                    "severity": "critical",
                    "task_id": chain["task_id"],
                    "failed_deps": chain["failed_dependencies"],
                    "description": f"级联失败 - 任务 {chain['task_id']} 受 {len(chain['failed_dependencies'])} 个失败依赖影响"
                })
            result["recommendations"].append("recover_upstream")
        
        # P2-1: 资源耗尽检测
        resource = check_resource_exhaustion(project_id, threshold_pending=5)
        if resource.get("exhausted"):
            result["healthy"] = False
            result["summary"]["resource_exhaustion_count"] += 1
            result["issues"].append({
                "type": "resource_exhaustion",
                "severity": "warning",
                "pending_count": resource["pending_count"],
                "busy_agents": resource["busy_agents"],
                "description": f"资源耗尽 - {resource['pending_count']}个 pending 任务，{len(resource['busy_agents'])}个 Agent 忙碌"
            })
            result["recommendations"].append("scale_agents")
        
        # 新增：优先级冲突检测
        priority = check_priority_conflict(project_id)
        if priority.get("conflict"):
            result["healthy"] = False
            result["summary"]["priority_conflict_count"] = priority.get("conflict_count", 0)
            for c in priority.get("conflicts", []):
                result["issues"].append({
                    "type": "priority_conflict",
                    "severity": "warning",
                    "high_priority_task": c["high_priority_task"],
                    "blocked_by": c["blocked_by"],
                    "description": f"优先级冲突 - {c['high_priority_task']}({c['high_priority']}) 被 {c['blocked_by']}({c['blocked_by_priority']}) 阻塞"
                })
            result["recommendations"].append("reorder_tasks")
        
        # 新增：负载均衡检测
        load_balance = check_agent_load_balance(project_id)
        if load_balance.get("unbalanced"):
            result["healthy"] = False
            result["summary"]["load_imbalance_count"] = len(load_balance.get("unbalanced_agents", []))
            for agent in load_balance.get("unbalanced_agents", []):
                result["issues"].append({
                    "type": "load_imbalance",
                    "severity": "info",
                    "agent": agent["agent"],
                    "status": agent["status"],
                    "description": f"负载不均衡 - Agent {agent['agent']} {agent['status']} ({agent['deviation_percent']}% 偏离)"
                })
            result["recommendations"].append("redistribute_tasks")
        
        # 新增：依赖缺失检测
        missing = check_missing_dependencies(project_id)
        if missing.get("missing"):
            result["healthy"] = False
            result["summary"]["missing_dependency_count"] = missing.get("missing_count", 0)
            for item in missing.get("missing_dependencies", []):
                result["issues"].append({
                    "type": "missing_dependency",
                    "severity": "critical",
                    "task_id": item["task_id"],
                    "missing_dep": item["missing_dependency"],
                    "description": f"依赖缺失 - 任务 {item['task_id']} 依赖不存在的 {item['missing_dependency']}"
                })
            result["recommendations"].append("fix_dependencies")
        
        # P0 新增：队列锁定失败检测
        queue_lock = check_queue_lock_failure(project_id)
        if queue_lock.get("failed"):
            result["healthy"] = False
            result["summary"]["queue_lock_failure_count"] += 1
            result["issues"].append({
                "type": "queue_lock_failure",
                "severity": "critical",
                "task_id": queue_lock.get("task_id"),
                "reason": queue_lock.get("reason"),
                "description": f"队列锁定失败 - {queue_lock.get('reason')}"
            })
            result["recommendations"].append("force_release_queue")
        
        # P0 新增：数据完整性检测
        data_integrity = check_data_integrity(project_id)
        if data_integrity.get("corrupted"):
            result["healthy"] = False
            result["summary"]["data_integrity_count"] += 1
            result["issues"].append({
                "type": "data_integrity",
                "severity": "critical",
                "reason": data_integrity.get("reason"),
                "invalid_count": len(data_integrity.get("invalid_tasks", [])),
                "description": f"数据完整性问题 - {data_integrity.get('reason')}"
            })
            result["recommendations"].append("restore_from_backup")
        
        # P0 新增：子任务状态检测
        subtask = check_subtask_status(project_id)
        if subtask.get("mismatch"):
            result["healthy"] = False
            result["summary"]["subtask_status_count"] = subtask.get("issue_count", 0)
            for issue in subtask.get("issues", []):
                result["issues"].append({
                    "type": "subtask_status_mismatch",
                    "severity": "warning",
                    "parent_task_id": issue["parent_task_id"],
                    "incomplete_count": len(issue["incomplete_subtasks"]),
                    "description": f"子任务状态不匹配 - 主任务 {issue['parent_task_id']} 有 {len(issue['incomplete_subtasks'])} 个子任务未完成"
                })
            result["recommendations"].append("complete_subtasks")
        
        # P2 新增：子任务创建失败检测
        subtask_create = check_subtask_creation(project_id)
        if subtask_create.get("failed"):
            result["healthy"] = False
            result["summary"]["subtask_creation_count"] = subtask_create.get("missing_count", 0)
            result["issues"].append({
                "type": "subtask_creation_failed",
                "severity": "critical",
                "missing_subtasks": subtask_create.get("missing_subtasks", []),
                "missing_count": subtask_create.get("missing_count"),
                "description": f"子任务创建失败 - {subtask_create.get('missing_count')} 个子任务缺少 subtask_created 日志"
            })
            result["recommendations"].append("check_agent_subtask_logic")
        
        # P2 新增：子任务执行卡住检测
        subtask_stuck = check_subtask_stuck(project_id)
        if subtask_stuck.get("stuck"):
            result["healthy"] = False
            result["summary"]["subtask_stuck_count"] = subtask_stuck.get("stuck_count", 0)
            for stuck in subtask_stuck.get("stuck_subtasks", []):
                result["issues"].append({
                    "type": "subtask_stuck",
                    "severity": "warning",
                    "subtask_id": stuck["subtask_id"],
                    "stuck_minutes": stuck["stuck_minutes"],
                    "description": f"子任务卡住 - {stuck['subtask_id']} 已停滞 {stuck['stuck_minutes']}分钟"
                })
            result["recommendations"].append("investigate_subtask")
        
        # P1 新增：Trigger 文件创建失败检测
        trigger_create = check_trigger_creation(project_id)
        if trigger_create.get("failed"):
            result["healthy"] = False
            result["summary"]["trigger_creation_count"] += 1
            result["issues"].append({
                "type": "trigger_creation_failed",
                "severity": "critical",
                "task_id": trigger_create.get("task_id"),
                "reason": trigger_create.get("reason"),
                "description": f"Trigger 创建失败 - {trigger_create.get('reason')}"
            })
            result["recommendations"].append("manual_dispatch")
        
        # P1 新增：Trigger 文件未清理检测
        trigger_clean = check_trigger_cleanup(project_id)
        if trigger_clean.get("uncleaned"):
            result["healthy"] = False
            result["summary"]["trigger_cleanup_count"] = trigger_clean.get("uncleaned_count", 0)
            for item in trigger_clean.get("uncleared_tasks", []):
                result["issues"].append({
                    "type": "trigger_not_cleaned",
                    "severity": "warning",
                    "task_id": item["task_id"],
                    "file_count": len(item["trigger_files"]),
                    "description": f"Trigger 未清理 - 任务 {item['task_id']} 有 {len(item['trigger_files'])} 个残留文件"
                })
            result["recommendations"].append("cleanup_triggers")
        
        # P1 新增：队列未释放检测
        queue_stale = check_queue_stale(project_id)
        if queue_stale.get("stale"):
            result["healthy"] = False
            result["summary"]["queue_stale_count"] += 1
            result["issues"].append({
                "type": "queue_stale",
                "severity": "critical",
                "task_id": queue_stale.get("task_id"),
                "reason": queue_stale.get("reason"),
                "description": f"队列未释放 - {queue_stale.get('reason')}"
            })
            result["recommendations"].append("force_release_queue")
        
        # P1 新增：通知送达检测
        notify_delivery = check_notification_delivery(project_id)
        if notify_delivery.get("failed"):
            result["healthy"] = False
            result["summary"]["notification_delivery_count"] += 1
            result["issues"].append({
                "type": "notification_delivery_failed",
                "severity": "warning",
                "notify_count": notify_delivery.get("notify_count"),
                "sent_count": notify_delivery.get("sent_count"),
                "missing_count": notify_delivery.get("missing_count"),
                "description": f"通知送达失败 - {notify_delivery.get('missing_count')} 个通知未确认送达"
            })
            result["recommendations"].append("check_telegram_api")
        
        # P3 新增：任务状态跳跃检测
        status_jump = check_status_transition(project_id)
        if status_jump.get("jumped"):
            result["healthy"] = False
            result["summary"]["status_jump_count"] = status_jump.get("jump_count", 0)
            for jump in status_jump.get("jumps", []):
                result["issues"].append({
                    "type": "status_jump",
                    "severity": "warning",
                    "task_id": jump["task_id"],
                    "from": jump["from"],
                    "to": jump["to"],
                    "description": f"状态跳跃 - 任务 {jump['task_id']} 从 {jump['from']} 直接到 {jump['to']}"
                })
            result["recommendations"].append("check_task_complete_logic")
        
        # P3 新增：Agent 通信超时检测
        agent_timeout = check_agent_comm_timeout(project_id)
        if agent_timeout.get("timeout"):
            result["healthy"] = False
            result["summary"]["agent_comm_timeout_count"] = agent_timeout.get("timeout_count", 0)
            for t in agent_timeout.get("timeouts", []):
                desc = f"Agent 通信超时 - {t['agent']}"
                if t.get("task_id"):
                    desc += f" / {t['task_id']}"
                if t.get("reason") == "never_started":
                    desc += " 通知子进程未启动"
                else:
                    desc += f" 已超时 {t.get('duration_minutes', 0)}分钟"
                issue = {
                    "type": "agent_comm_timeout",
                    "severity": "warning",
                    "agent": t["agent"],
                    "duration_minutes": t.get("duration_minutes", 0),
                    "description": desc,
                }
                if t.get("task_id"):
                    issue["task_id"] = t["task_id"]
                result["issues"].append(issue)
            result["recommendations"].append("rescue_dispatch")
        
        # P3 新增：项目初始化检测
        proj_init = check_project_init(project_id)
        if proj_init.get("failed"):
            result["healthy"] = False
            result["summary"]["project_init_count"] = proj_init.get("issue_count", 0)
            for issue in proj_init.get("issues", []):
                result["issues"].append({
                    "type": "project_init_failed",
                    "severity": "critical",
                    "issue_type": issue["type"],
                    "description": f"项目初始化失败 - {issue['description']}"
                })
            result["recommendations"].append("reinit_project")

        # waiting_for_input 超时检测
        waiting_input = check_waiting_for_input_timeout(project_id)
        if waiting_input.get("timeout"):
            result["healthy"] = False
            result["summary"]["waiting_input_timeout_count"] = waiting_input.get("timeout_count", 0)
            for t in waiting_input.get("timed_out_tasks", []):
                result["issues"].append({
                    "type": "waiting_input_timeout",
                    "severity": "warning",
                    "task_id": t["task_id"],
                    "agent": t["agent"],
                    "age_minutes": t["age_minutes"],
                    "description": f"等待用户输入超时 - 任务 {t['task_id']}({t['agent']}) 已等待 {t['age_minutes']}分钟"
                })
            result["recommendations"].append("check_with_user_or_force_resume")

        # 新增：Agent 会话假死检测
        session_stuck = check_agent_session_stuck(project_id)
        if session_stuck.get("stuck"):
            result["healthy"] = False
            result["summary"]["agent_session_stuck_count"] = session_stuck.get("stuck_count", 0)
            for s in session_stuck.get("stuck_sessions", []):
                result["issues"].append({
                    "type": "agent_session_stuck",
                    "severity": "critical",
                    "agent": s["agent"],
                    "task_id": s["task_id"],
                    "reason": s["reason"],
                    "description": f"Agent 会话假死 - {s['agent']}({s['task_id']}): {s['reason']}"
                })
            result["recommendations"].append("force_recover_session")

        # 新增：Trigger 文件未被消费检测
        unconsumed = check_trigger_not_consumed(project_id)
        if unconsumed.get("unconsumed"):
            result["healthy"] = False
            result["summary"]["trigger_not_consumed_count"] = unconsumed.get("unconsumed_count", 0)
            for t in unconsumed.get("unconsumed_triggers", []):
                result["issues"].append({
                    "type": "trigger_not_consumed",
                    "severity": "warning",
                    "agent": t["agent"],
                    "task_id": t["task_id"],
                    "age_minutes": t["age_minutes"],
                    "description": f"Trigger 未被消费 - {t['agent']}({t['task_id']}) 已存在 {t['age_minutes']}分钟"
                })
            result["recommendations"].append("investigate_trigger")

        # 新增：Deputy 健康检查
        deputy_health = check_deputy_health()
        result["summary"]["deputy_healthy"] = deputy_health.get("healthy", False)
        if not deputy_health.get("healthy"):
            result["healthy"] = False
            result["issues"].append({
                "type": "deputy_heartbeat_expired",
                "severity": "critical",
                "minutes_since_heartbeat": deputy_health.get("minutes_since_heartbeat", 0),
                "description": f"Deputy 心跳过期 - {deputy_health.get('reason', '未知原因')}"
            })
            result["recommendations"].append("restart_deputy")

        return result
    except Exception as e:
        result["healthy"] = False
        result["error"] = str(e)
        return result


def main():
    parser = argparse.ArgumentParser(description="Task Monitor")
    parser.add_argument("command", nargs="?", default="status")
    parser.add_argument("project", nargs="?", default=None)
    parser.add_argument("--no-retry", action="store_true", help="Disable auto retry")
    parser.add_argument("extra_args", nargs="*", default=[])
    
    args = parser.parse_args()
    
    if args.command == "status":
        status()
    elif args.command == "check":
        check(args.project, auto_retry=not args.no_retry)
    elif args.command == "check-stuck":
        if not args.project:
            _exit_monitor_usage("Usage: check-stuck <project_id>", "check-stuck")
        print(json.dumps(check_stuck(args.project), ensure_ascii=False, indent=2))
    elif args.command == "health":
        if not args.project:
            _exit_monitor_usage("Usage: health <project_id>", "health")
        print(json.dumps(health(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-state":
        if not args.project:
            _exit_monitor_usage("Usage: check-state <project_id>", "check-state")
        print(json.dumps(check_state_mismatch(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-async":
        if not args.project:
            _exit_monitor_usage(
                "Usage: check-async <project_id> <task_id> [agent_id]",
                "check-async",
            )
        task_id = args.extra_args[0] if args.extra_args else None
        agent_id = args.extra_args[1] if len(args.extra_args) > 1 else None
        if task_id:
            print(json.dumps(check_async_failure(args.project, task_id, agent_id), ensure_ascii=False, indent=2))
        else:
            _exit_monitor_usage(
                "Usage: check-async <project_id> <task_id> [agent_id]",
                "check-async-missing-task",
            )
    elif args.command == "check-circular":
        if not args.project:
            _exit_monitor_usage("Usage: check-circular <project_id>", "check-circular")
        print(json.dumps(detect_circular_dependency(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-cascading":
        if not args.project:
            _exit_monitor_usage("Usage: check-cascading <project_id>", "check-cascading")
        print(json.dumps(detect_cascading_failure(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-resource":
        if not args.project:
            _exit_monitor_usage("Usage: check-resource <project_id>", "check-resource")
        print(json.dumps(check_resource_exhaustion(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-queue-lock":
        if not args.project:
            _exit_monitor_usage("Usage: check-queue-lock <project_id>", "check-queue-lock")
        print(json.dumps(check_queue_lock_failure(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-data":
        if not args.project:
            _exit_monitor_usage("Usage: check-data <project_id>", "check-data")
        print(json.dumps(check_data_integrity(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-subtasks":
        if not args.project:
            _exit_monitor_usage("Usage: check-subtasks <project_id>", "check-subtasks")
        print(json.dumps(check_subtask_status(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-trigger":
        if not args.project:
            _exit_monitor_usage("Usage: check-trigger <project_id>", "check-trigger")
        result = {
            "creation": check_trigger_creation(args.project),
            "cleanup": check_trigger_cleanup(args.project)
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "check-queue-stale":
        if not args.project:
            _exit_monitor_usage("Usage: check-queue-stale <project_id>", "check-queue-stale")
        print(json.dumps(check_queue_stale(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-notify":
        if not args.project:
            _exit_monitor_usage("Usage: check-notify <project_id>", "check-notify")
        print(json.dumps(check_notification_delivery(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-subtask-create":
        if not args.project:
            _exit_monitor_usage("Usage: check-subtask-create <project_id>", "check-subtask-create")
        print(json.dumps(check_subtask_creation(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-subtask-stuck":
        if not args.project:
            _exit_monitor_usage("Usage: check-subtask-stuck <project_id>", "check-subtask-stuck")
        print(json.dumps(check_subtask_stuck(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-status-jump":
        if not args.project:
            _exit_monitor_usage("Usage: check-status-jump <project_id>", "check-status-jump")
        print(json.dumps(check_status_transition(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-agent-timeout":
        if not args.project:
            _exit_monitor_usage("Usage: check-agent-timeout <project_id>", "check-agent-timeout")
        print(json.dumps(check_agent_comm_timeout(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-init":
        if not args.project:
            _exit_monitor_usage("Usage: check-init <project_id>", "check-init")
        print(json.dumps(check_project_init(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-priority":
        if not args.project:
            _exit_monitor_usage("Usage: check-priority <project_id>", "check-priority")
        print(json.dumps(check_priority_conflict(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-load":
        if not args.project:
            _exit_monitor_usage("Usage: check-load <project_id>", "check-load")
        print(json.dumps(check_agent_load_balance(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-deps":
        if not args.project:
            _exit_monitor_usage("Usage: check-deps <project_id>", "check-deps")
        print(json.dumps(check_missing_dependencies(args.project), ensure_ascii=False, indent=2))
    elif args.command == "check-waiting-input":
        if not args.project:
            _exit_monitor_usage("Usage: check-waiting-input <project_id>", "check-waiting-input")
        print(json.dumps(check_waiting_for_input_timeout(args.project), ensure_ascii=False, indent=2))
    elif args.command == "validate-graph":
        if not args.project:
            _exit_monitor_usage("Usage: validate-graph <project_id>", "validate-graph")
        sys.exit(validate_task_graph(args.project))
    elif args.command == "stats":
        stats(args.project)
    elif args.command == "progress":
        if args.project:
            result = calculate_progress(args.project)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _exit_monitor_usage("Usage: progress <project_id>", "progress")
    else:
        log_skill_step_failure(
            _MONITOR_NO_PROJECT,
            "MONITOR",
            "unknown_command",
            args.command or "",
            "",
        )
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
