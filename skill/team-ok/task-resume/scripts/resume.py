#!/usr/bin/env python3
"""Task Resume Skill - 恢复并继续执行项目任务

功能升级（方案 A）：
1. 根据用户输入的项目名称查找匹配的项目
2. 自动检测所有 29 种问题（集成 task-monitor 检测逻辑）
3. 根据问题类型自动选择恢复策略
4. 检查重试次数，避免无限循环（最多 3 次）
5. 记录日志到 skill-logs 和 memory
6. 支持批量处理（--all 参数）
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.logger import get_skill_logger, log_skill_step_failure
from common.notify_handshake import ACK_TIMEOUT_SEC
import json
import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher


# ============================================================================
# 恢复策略映射表
# ============================================================================
RECOVERY_STRATEGIES = {
    'zombie_detected': '重新调度任务',
    'stuck': '重置并重新调度',
    'state_mismatch': '同步状态',
    'timeout': '重试任务',
    'agent_comm_timeout': '重新分派给 Agent',
    'deadlock': '标记人工介入',
    'queue_lock_failure': '释放队列锁',
    'data_integrity': '标记人工介入',
    'circular_dependency': '标记人工介入',
    'async_failure': '救援分派',
    'orphaned': '调用 task-complete',
    'trigger_creation_failed': '重新创建 trigger',
    'trigger_cleanup_failed': '清理残留 trigger',
    'notification_missing': '补发通知',
    'subtask_status': '同步子任务状态',
}

# 需要人工介入的问题类型（可自动恢复的 deadlock 见 recover_dispatch_stall）
MANUAL_INTERVENTION_ISSUES = [
    'data_integrity',
    'circular_dependency',
    'resource_exhaustion',
    'priority_conflict',
    'graph_invalid',
    'blocked',
    'cascading_failure',
]

# 自动恢复的问题类型
AUTO_RECOVERY_ISSUES = [
    'zombie_detected',
    'stuck',
    'state_mismatch',
    'timeout',
    'agent_comm_timeout',
    'queue_lock_failure',
    'async_failure',
    'orphaned',
    'trigger_creation_failed',
    'trigger_cleanup_failed',
    'notification_missing',
    'subtask_status',
    'deadlock',
]


def get_projects_dir():
    """获取项目目录"""
    return Path.home() / ".openclaw" / "tasks" / "projects"


def get_skills_dir():
    """获取 skills 目录"""
    return Path.home() / ".openclaw" / "skills"


def fuzzy_match_ratio(a, b):
    """计算两个字符串的相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_projects():
    """查找所有项目"""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []
    
    projects = []
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            task_data_file = project_dir / "task_data.json"
            if task_data_file.exists():
                try:
                    with open(task_data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        projects.append({
                            'id': data['project']['id'],
                            'name': data['project']['name'],
                            'status': data['project']['status'],
                            'path': project_dir,
                            'task_count': len(data.get('tasks', []))
                        })
                except Exception:
                    continue
    return projects


def find_project_by_query(query):
    """根据查询字符串查找项目
    
    返回：
        (project_id, project_name) - 找到唯一匹配
        (None, [list_of_matches]) - 多个匹配
        (None, None) - 无匹配
    """
    projects = find_projects()
    if not projects:
        return None, None
    
    query = query.strip().lower()
    
    # 1. 精确匹配项目 ID
    for p in projects:
        if query == p['id'].lower():
            return p['id'], p['name']
    
    # 2. 精确匹配项目名称
    for p in projects:
        if query == p['name'].lower():
            return p['id'], p['name']
    
    # 3. 包含匹配
    matches = []
    for p in projects:
        if query in p['id'].lower() or query in p['name'].lower():
            matches.append(p)
    
    if len(matches) == 1:
        return matches[0]['id'], matches[0]['name']
    elif len(matches) > 1:
        return None, matches
    
    # 4. 模糊匹配
    fuzzy_matches = []
    for p in projects:
        score = max(
            fuzzy_match_ratio(query, p['id']),
            fuzzy_match_ratio(query, p['name'])
        )
        if score > 0.5:  # 阈值 0.5
            fuzzy_matches.append((score, p))
    
    fuzzy_matches.sort(reverse=True)
    
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0][1]['id'], fuzzy_matches[0][1]['name']
    elif len(fuzzy_matches) > 1:
        return None, [m[1] for m in fuzzy_matches]
    
    return None, None


def read_project_data(project_id):
    """读取项目数据"""
    projects_dir = get_projects_dir()
    task_data_file = projects_dir / project_id / "task_data.json"
    
    if not task_data_file.exists():
        return None
    
    with open(task_data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_queue_status(project_id):
    """检查队列状态"""
    result = subprocess.run(
        [str(get_skills_dir() / "team-ok" / "task-queue" / "scripts" / "task_queue.py"),
         'status', project_id],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def get_next_task(project_id):
    """获取下一个可执行任务"""
    result = subprocess.run(
        [str(get_skills_dir() / "team-ok" / "task-queue" / "scripts" / "task_queue.py"),
         'next', project_id],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def detect_stuck_task(project_id, task_id, agent_id):
    """检测任务是否卡住（增强版）

    新增检测维度：
    - 检查 Agent 是否写入 ACK 文件（确认开始执行）
    - 检查 Agent 会话是否活跃（通过 opencode session_map）
    - 触发文件阈值从 1 小时缩短为 10 分钟

    返回：
        (is_stuck, reason)
    """
    import json
    reasons = []

    # 1. 检查触发文件是否存在
    trigger_file = Path.home() / f".openclaw/workspace-{agent_id}/.trigger/{project_id}_{task_id}.trigger"

    if not trigger_file.exists():
        return True, "无触发文件，任务可能未成功调度"

    # 2. 检查触发文件时间（阈值从 1 小时改为 10 分钟）
    trigger_time = datetime.fromtimestamp(trigger_file.stat().st_mtime)
    time_diff = datetime.now() - trigger_time

    if time_diff > timedelta(minutes=10):
        reasons.append(f"触发文件已存在 {time_diff.total_seconds()/60:.0f} 分钟")

    # 3. 检查 ACK 文件是否存在
    ack_file = Path.home() / f".openclaw/workspace-{agent_id}/.trigger/{project_id}_{task_id}.ack"
    if not ack_file.exists() and time_diff > timedelta(minutes=5):
        reasons.append("Agent 未确认执行（无 ACK 文件）")

    # 4. 检查 Agent 会话是否活跃
    # 注意：session_map 的 last_used 字段不会被更新，不能依赖
    session_map_path = Path.home() / ".openclaw" / "opencode_session_map.json"
    if session_map_path.exists():
        try:
            sessions = json.loads(session_map_path.read_text(encoding="utf-8"))
            key = f"{agent_id}:{agent_id}:workspace-{agent_id}"
            session = sessions.get(key)
            if not session and time_diff > timedelta(minutes=5):
                reasons.append("Agent 无活跃会话")
        except (OSError, json.JSONDecodeError):
            pass

    if reasons:
        return True, "; ".join(reasons)
    return False, "正常"


def detect_zombie_task(project_id, task_id, agent_id):
    """检测假死任务（已派遣但从未执行）
    
    返回：
        (is_zombie, reason)
    """
    project_data = read_project_data(project_id)
    if not project_data:
        return False, "无法读取项目数据"
    
    task = get_task_info(project_data, task_id)
    if not task:
        return False, "任务不存在"
    
    # 检查 started_at 是否为 null
    if task.get('started_at') is None:
        # 检查 dispatched_at
        triggered_at = task.get('triggered_at')
        if triggered_at:
            dispatch_time = datetime.fromisoformat(triggered_at.replace('Z', '+00:00'))
            if dispatch_time.tzinfo:
                dispatch_time = dispatch_time.replace(tzinfo=None)
            time_diff = datetime.now() - dispatch_time
            if time_diff.total_seconds() > 300:  # 5 分钟未启动
                return True, f"任务已派遣 {time_diff.total_seconds()/60:.1f} 分钟但从未启动"

    # 队列 running 但 dispatch 进程已死且无 ACK → stale queue lock
    if task.get('started_at') and agent_id:
        ack_path = Path.home() / f".openclaw/workspace-{agent_id}/.trigger/{project_id}_{task_id}.ack"
        if not ack_path.exists():
            import subprocess as _sp
            try:
                ps = _sp.run(
                    ["pgrep", "-f", f"dispatch.py.*{project_id}.*{task_id}"],
                    capture_output=True, text=True, timeout=RESUME_CMD_SHORT_TIMEOUT,
                )
                if ps.returncode != 0:
                    return True, "队列锁定但 dispatch 进程已死且 Agent 未确认执行"
            except Exception:
                pass
    
    return False, "正常"


def detect_state_mismatch(project_id, task_id):
    """检测状态不一致
    
    返回：
        (is_mismatch, queue_status, task_status)
    """
    queue_status = check_queue_status(project_id)
    
    project_data = read_project_data(project_id)
    if not project_data:
        return False, None, None
    
    task = get_task_info(project_data, task_id)
    if not task:
        return False, None, None
    
    task_status = task.get('status', '')
    
    # 队列显示 running 但任务显示 pending
    if queue_status.startswith('running:') and task_status == 'pending':
        return True, 'running', 'pending'
    
    return False, queue_status, task_status


def reset_task_to_pending(project_id, task_id):
    """将任务重置为 pending 状态"""
    result = subprocess.run(
        [str(get_skills_dir() / "team-ok" / "project-data" / "scripts" / "project_data.py"),
         'update-task', project_id, task_id, 'pending'],
        capture_output=True, text=True
    )
    return result.returncode == 0


def dispatch_task(project_id, task_id, agent_id):
    """调度任务给 Agent（dispatch.py 内置整图 DAG 闸门）。"""
    cmd = [
        str(get_skills_dir() / "team-ok" / "task-dispatch" / "scripts" / "dispatch.py"),
        project_id,
        task_id,
        agent_id,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def get_task_info(project_data, task_id):
    """获取任务信息"""
    for task in project_data.get('tasks', []):
        if task['id'] == task_id:
            return task
    return None


def check_retry_count(project_data, task_id):
    """检查重试次数
    
    返回：
        (retry_count, max_retries, can_retry)
    """
    task = get_task_info(project_data, task_id)
    if not task:
        return 0, 3, False
    
    retry_count = task.get('retry_count', 0)
    max_retries = task.get('max_retries', 3)
    
    return retry_count, max_retries, retry_count < max_retries


def release_queue_lock(project_id):
    """释放队列锁（走 task-queue release，与 monitor 建议一致）。"""
    result = subprocess.run(
        [
            str(get_skills_dir() / "team-ok" / "task-queue" / "scripts" / "task_queue.py"),
            "release",
            project_id,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "队列锁已释放"
    return False, (result.stderr or result.stdout or "release failed")[:300]


def run_project_health(project_id):
    """调用 task_monitor health，返回 JSON dict 或 None。"""
    script = get_skills_dir() / "team-ok" / "task-monitor" / "scripts" / "task_monitor.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "health", project_id],
            capture_output=True,
            text=True,
            timeout=RESUME_CMD_TIMEOUT,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return None


def _agent_id_for_task(project_data, task_id):
    task = get_task_info(project_data, task_id)
    return task.get("agent", "") if task else ""


def health_issues_to_resume(project_id, health_report, project_data):
    """将 task_monitor health issues 转为 resume 可处理条目。"""
    if not health_report or health_report.get("healthy"):
        return []
    out = []
    for issue in health_report.get("issues", []):
        itype = issue.get("type")
        task_id = issue.get("task_id")
        agent_id = issue.get("agent_id") or issue.get("agent", "")
        if not agent_id and task_id:
            agent_id = _agent_id_for_task(project_data, task_id)
        if itype == "agent_comm_timeout" and not task_id:
            agent = issue.get("agent", "")
            for t in project_data.get("tasks", []):
                if t.get("status") == "pending" and t.get("agent") == agent:
                    task_id = t["id"]
                    break
        if not task_id and itype in (
            "deadlock",
            "queue_lock_failure",
            "state_mismatch",
            "stuck",
            "async_failure",
        ):
            qs = check_queue_status(project_id)
            if qs.startswith("running:"):
                task_id = qs.split(":", 1)[1]
                agent_id = agent_id or _agent_id_for_task(project_data, task_id)
        if not task_id:
            continue
        out.append(
            {
                "type": itype,
                "task_id": task_id,
                "agent_id": agent_id,
                "severity": issue.get("severity", "warning"),
                "description": issue.get("description", ""),
            }
        )
    return out


def is_fake_running_queue(project_id, project_data):
    """队列 running 但 Worker 未真正执行（可恢复）。"""
    qs = check_queue_status(project_id)
    if not qs.startswith("running:"):
        return False, None
    task_id = qs.split(":", 1)[1]
    task = get_task_info(project_data, task_id)
    if not task:
        return True, task_id
    if task.get("status") == "pending":
        return True, task_id
    if task.get("status") == "in_progress" and task.get("started_at") is None:
        return True, task_id
    # 队列 running 但 dispatch 进程已死且无 ACK → stale queue lock
    if task.get("status") == "in_progress" and task.get("started_at"):
        agent_id = task.get("agent", "")
        ack_path = Path.home() / f".openclaw/workspace-{agent_id}/.trigger/{project_id}_{task_id}.ack"
        if not ack_path.exists():
            # 检查 dispatch.py 进程是否还活着
            import subprocess as _sp
            try:
                ps = _sp.run(
                    ["pgrep", "-f", f"dispatch.py.*{project_id}.*{task_id}"],
                    capture_output=True, text=True, timeout=RESUME_CMD_SHORT_TIMEOUT,
                )
                if ps.returncode != 0:
                    return True, task_id
            except Exception:
                pass
    health = run_project_health(project_id)
    if health:
        for issue in health.get("issues", []):
            if issue.get("task_id") == task_id and issue.get("type") in (
                "queue_lock_failure",
                "deadlock",
                "agent_comm_timeout",
                "state_mismatch",
                "async_failure",
            ):
                return True, task_id
    return False, task_id


def recover_dispatch_stall(
    project_id, task_id, agent_id, project_data, logger
):
    """释放 stale 锁并重新派发（deadlock / comm timeout / notify 未启动）。"""
    retry_count, max_retries, can_retry = check_retry_count(project_data, task_id)
    if not can_retry:
        return False, f"任务 {task_id} 已达到最大重试次数 ({max_retries})，需要人工介入"

    logger.info(
        f"[RECOVER_DISPATCH_STALL] task={task_id}, agent={agent_id}, retry={retry_count + 1}",
        extra={"skill_name": "RESUME"},
    )
    release_queue_lock(project_id)
    if not reset_task_to_pending(project_id, task_id):
        return False, f"重置任务失败：{task_id}"
    success, stdout, stderr = dispatch_task(
        project_id, task_id, agent_id
    )
    if success:
        return True, f"任务 {task_id} 已重新派发至 {agent_id} (重试 {retry_count + 1}/{max_retries})"
    return False, f"重新派发失败：{stderr or stdout}"


def recover_zombie_task(project_id, task_id, agent_id, logger):
    """恢复假死任务（增强版）

    新增：
    - 强制释放队列锁（解决队列锁死锁）
    - 清理旧的 trigger 和 ack 文件
    - 可指定不同 Agent 重新调度
    - 最多 3 次自动重试（每次间隔 30 秒）
    """
    logger.info(f"[RECOVER_ZOMBIE] project={project_id}, task={task_id}, agent={agent_id}", extra={'skill_name': 'RESUME'})

    # 1. 强制释放队列锁
    logger.info(f"[FORCE_QUEUE_RELEASE] project={project_id}, task={task_id}", extra={'skill_name': 'RESUME'})
    try:
        subprocess.run(
            [str(get_skills_dir() / "team-ok" / "task-queue" / "scripts" / "task_queue.py"),
             "release", project_id],
            capture_output=True, text=True, timeout=RESUME_RELEASE_TIMEOUT,
        )
    except Exception as e:
        logger.warning(f"[FORCE_QUEUE_RELEASE_WARN] project={project_id}, error={e}", extra={'skill_name': 'RESUME'})

    # 2. 清理旧的 trigger 和 ack 文件
    for fname in [f"{project_id}_{task_id}.trigger", f"{project_id}_{task_id}.ack"]:
        fpath = Path.home() / f".openclaw/workspace-{agent_id}/.trigger/{fname}"
        if fpath.exists():
            try:
                fpath.unlink()
                logger.info(f"[CLEANUP] removed {fpath}", extra={'skill_name': 'RESUME'})
            except OSError as e:
                logger.warning(f"[CLEANUP_FAIL] {fpath}: {e}", extra={'skill_name': 'RESUME'})

    # 3. 重置状态为 pending
    if not reset_task_to_pending(project_id, task_id):
        return False, "强制释放队列锁成功，但重置任务状态失败"

    # 4. 重新调度（最多 3 次重试）
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        logger.info(f"[RECOVER_RETRY] task={task_id}, attempt={attempt}/{max_attempts}", extra={'skill_name': 'RESUME'})
        success, stdout, stderr = dispatch_task(
            project_id, task_id, agent_id
        )
        if success:
            logger.info(
                f"[RECOVER_ZOMBIE_SUCCESS] task={task_id} 已重新调度 (attempt={attempt})",
                extra={'skill_name': 'RESUME'},
            )
            return True, f"假死任务 {task_id} 已强制释放队列锁并重新调度给 {agent_id} (重试 {attempt}/{max_attempts})"

        logger.warning(
            f"[RECOVER_RETRY_FAIL] task={task_id}, attempt={attempt}/{max_attempts}, error={stderr}",
            extra={'skill_name': 'RESUME'},
        )
        if attempt < max_attempts:
            time.sleep(RESUME_SLEEP_INTERVAL)

    logger.error(f"[RECOVER_ZOMBIE_FAIL] task={task_id} 已重试 {max_attempts} 次均失败", extra={'skill_name': 'RESUME'})
    return False, f"假死任务 {task_id} 已重试 {max_attempts} 次均失败，需要人工介入"


def recover_state_mismatch(project_id, task_id, agent_id, logger):
    """恢复状态不一致"""
    logger.info(f"[RECOVER_MISMATCH] project={project_id}, task={task_id}", extra={'skill_name': 'RESUME'})
    
    # 重置为 pending 以同步状态
    if reset_task_to_pending(project_id, task_id):
        logger.info(f"[RECOVER_MISMATCH_SUCCESS] task={task_id} 状态已同步", extra={'skill_name': 'RESUME'})
        return True, f"任务 {task_id} 状态已同步"
    else:
        logger.error(f"[RECOVER_MISMATCH_FAIL] task={task_id}", extra={'skill_name': 'RESUME'})
        return False, "状态同步失败"


def recover_timeout(project_id, task_id, agent_id, project_data, logger):
    """恢复超时任务"""
    retry_count, max_retries, can_retry = check_retry_count(project_data, task_id)
    
    if not can_retry:
        logger.error(f"[RECOVER_TIMEOUT_FAIL] task={task_id}, retry_count={retry_count}, max_reached", extra={'skill_name': 'RESUME'})
        return False, f"任务 {task_id} 已达到最大重试次数 ({max_retries})，需要人工介入"
    
    logger.info(f"[RECOVER_TIMEOUT] task={task_id}, retry={retry_count+1}/{max_retries}", extra={'skill_name': 'RESUME'})
    
    # 重置并重新调度
    if reset_task_to_pending(project_id, task_id):
        success, stdout, stderr = dispatch_task(
            project_id, task_id, agent_id
        )
        if success:
            logger.info(f"[RECOVER_TIMEOUT_SUCCESS] task={task_id} 已重试 ({retry_count+1}/{max_retries})", extra={'skill_name': 'RESUME'})
            return True, f"超时任务 {task_id} 已重试 ({retry_count+1}/{max_retries})"
    
    return False, "重试失败"


def recover_agent_comm_timeout(project_id, task_id, agent_id, project_data, logger):
    """恢复 Agent 通信超时"""
    retry_count, max_retries, can_retry = check_retry_count(project_data, task_id)
    
    if not can_retry:
        return False, f"任务 {task_id} 已达到最大重试次数，需要人工介入"
    
    logger.info(f"[RECOVER_AGENT_TIMEOUT] task={task_id}, agent={agent_id}, retry={retry_count+1}", extra={'skill_name': 'RESUME'})
    
    # 重置并重新分派
    if reset_task_to_pending(project_id, task_id):
        success, stdout, stderr = dispatch_task(
            project_id, task_id, agent_id
        )
        if success:
            logger.info(f"[RECOVER_AGENT_TIMEOUT_SUCCESS] task={task_id} 已重新分派", extra={'skill_name': 'RESUME'})
            return True, f"Agent 超时，任务 {task_id} 已重新分派给 {agent_id} (重试 {retry_count+1}/{max_retries})"
    
    return False, "重新分派失败"


def detect_all_issues(project_id, logger):
    """检测所有问题（本地启发式 + task_monitor health 全量）。"""
    issues = []
    seen = set()
    project_data = read_project_data(project_id)

    if not project_data:
        return issues

    def _add(issue):
        key = (issue.get("type"), issue.get("task_id"), issue.get("agent_id"))
        if key in seen:
            return
        seen.add(key)
        issues.append(issue)

    queue_status = check_queue_status(project_id)

    if queue_status.startswith("running:"):
        task_id = queue_status.split(":", 1)[1]
        task = get_task_info(project_data, task_id)

        if task:
            agent_id = task.get("agent", "")

            is_zombie, reason = detect_zombie_task(project_id, task_id, agent_id)
            if is_zombie:
                _add(
                    {
                        "type": "zombie_detected",
                        "task_id": task_id,
                        "agent_id": agent_id,
                        "severity": "warning",
                        "description": reason,
                    }
                )

            is_mismatch, queue_st, task_st = detect_state_mismatch(project_id, task_id)
            if is_mismatch:
                _add(
                    {
                        "type": "state_mismatch",
                        "task_id": task_id,
                        "agent_id": agent_id,
                        "severity": "warning",
                        "description": f"队列状态={queue_st}, 任务状态={task_st}",
                    }
                )

            # zombie_detected 已涵盖 stuck，跳过重复检测
            if not is_zombie:
                is_stuck, reason = detect_stuck_task(project_id, task_id, agent_id)
                if is_stuck:
                    _add(
                        {
                            "type": "stuck",
                            "task_id": task_id,
                            "agent_id": agent_id,
                            "severity": "warning",
                            "description": reason,
                        }
                    )

    for task in project_data.get("tasks", []):
        if task.get("status") == "in_progress" and task.get("started_at") is None:
            _add(
                {
                    "type": "zombie_detected",
                    "task_id": task["id"],
                    "agent_id": task.get("agent", ""),
                    "severity": "warning",
                    "description": "任务状态为 in_progress 但从未启动",
                }
            )

    # 队列 idle 但存在 in_progress 任务 → zombie（典型 ACK 超时场景）
    if not queue_status.startswith("running:"):
        for task in project_data.get("tasks", []):
            if task.get("status") == "in_progress":
                key = ("zombie_detected", task["id"], task.get("agent", ""))
                if key not in seen:
                    _add(
                        {
                            "type": "zombie_detected",
                            "task_id": task["id"],
                            "agent_id": task.get("agent", ""),
                            "severity": "warning",
                            "description": "任务状态为 in_progress 但队列空闲（ACK 超时或异常中断）",
                        }
                    )

    health = run_project_health(project_id)
    if health:
        for issue in health_issues_to_resume(project_id, health, project_data):
            _add(issue)
        if logger and not health.get("healthy"):
            logger.info(
                f"[RESUME_HEALTH] project={project_id}, issues={len(health.get('issues', []))}",
                extra={"skill_name": "RESUME"},
            )

    return issues


def recover_project(project_id, logger):
    """恢复项目的所有问题
    
    返回：
        (success, message, recovered_count, manual_count)
    """
    project_data = read_project_data(project_id)
    if not project_data:
        return False, "无法读取项目数据", 0, 0
    
    project_name = project_data['project']['name']
    
    # 检查项目状态
    if project_data['project']['status'] == 'completed':
        return False, f"项目 '{project_name}' 已完成，无需恢复", 0, 0
    
    queue_status = check_queue_status(project_id)
    fake_running, _ = is_fake_running_queue(project_id, project_data)
    if queue_status.startswith("running:") and not fake_running:
        return False, f"项目 '{project_name}' 当前有任务正在执行，请等待完成", 0, 0

    issues = detect_all_issues(project_id, logger)
    
    if not issues:
        # 没有问题，尝试调度下一个任务
        next_task_id = get_next_task(project_id)
        if next_task_id == "none":
            return False, f"项目 '{project_name}' 所有任务已完成", 0, 0
        
        # 调度下一个任务
        task_info = get_task_info(project_data, next_task_id)
        if task_info:
            agent_id = task_info['agent']
            success, stdout, stderr = dispatch_task(
                project_id,
                next_task_id,
                agent_id,
            )
            if success:
                logger.info(f"[RESUME_NORMAL] project={project_id}, task={next_task_id}", extra={'skill_name': 'RESUME'})
                return True, f"✅ 项目 '{project_name}' 已恢复\n📋 正在调度：{task_info['name']} ({next_task_id})", 1, 0
    
    # 处理检测到的问题
    recovered_count = 0
    manual_count = 0
    messages = []
    
    for issue in issues:
        issue_type = issue['type']
        task_id = issue['task_id']
        agent_id = issue['agent_id']
        
        logger.info(f"[RECOVER_START] issue={issue_type}, task={task_id}", extra={'skill_name': 'RESUME'})
        
        # 需要人工介入的问题
        if issue_type in MANUAL_INTERVENTION_ISSUES:
            manual_count += 1
            messages.append(f"❌ {issue_type}: {task_id} 需要人工介入")
            logger.warning(f"[RECOVER_MANUAL] issue={issue_type}, task={task_id}", extra={'skill_name': 'RESUME'})
            continue
        
        # 自动恢复的问题
        if issue_type in AUTO_RECOVERY_ISSUES:
            # 检查重试次数
            retry_count, max_retries, can_retry = check_retry_count(project_data, task_id)
            
            if not can_retry and issue_type in ['timeout', 'agent_comm_timeout', 'stuck', 'zombie_detected']:
                manual_count += 1
                messages.append(f"❌ {task_id} 已达到最大重试次数 ({max_retries})，需要人工介入")
                continue
            
            # 执行恢复
            success = False
            message = ""
            
            if issue_type == 'zombie_detected':
                success, message = recover_zombie_task(
                    project_id, task_id, agent_id, logger
                )
            elif issue_type == 'stuck':
                success, message = recover_zombie_task(
                    project_id, task_id, agent_id, logger
                )
            elif issue_type == 'state_mismatch':
                task_row = get_task_info(project_data, task_id)
                if task_row and task_row.get("status") == "pending":
                    success, message = recover_dispatch_stall(
                        project_id,
                        task_id,
                        agent_id,
                        project_data,
                        logger,
                    )
                else:
                    success, message = recover_state_mismatch(
                        project_id, task_id, agent_id, logger
                    )
            elif issue_type == 'timeout':
                success, message = recover_timeout(
                    project_id,
                    task_id,
                    agent_id,
                    project_data,
                    logger,
                )
            elif issue_type == 'agent_comm_timeout':
                success, message = recover_dispatch_stall(
                    project_id,
                    task_id,
                    agent_id,
                    project_data,
                    logger,
                )
            elif issue_type == 'deadlock':
                success, message = recover_dispatch_stall(
                    project_id,
                    task_id,
                    agent_id,
                    project_data,
                    logger,
                )
            elif issue_type == 'async_failure':
                success, message = recover_dispatch_stall(
                    project_id,
                    task_id,
                    agent_id,
                    project_data,
                    logger,
                )
            elif issue_type == 'queue_lock_failure':
                success, message = recover_dispatch_stall(
                    project_id,
                    task_id,
                    agent_id,
                    project_data,
                    logger,
                )
                if success:
                    message = f"队列锁已释放并重新调度：{message}"
            
            if success:
                recovered_count += 1
                messages.append(f"✅ {message}")
                logger.info(f"[RECOVER_SUCCESS] {message}", extra={'skill_name': 'RESUME'})
            else:
                messages.append(f"❌ 恢复失败：{message}")
                logger.error(f"[RECOVER_FAIL] {message}", extra={'skill_name': 'RESUME'})
    
    # 生成报告
    if recovered_count > 0 or manual_count > 0:
        report = f"✅ 项目 '{project_name}' 恢复完成\n"
        if recovered_count > 0:
            report += f"📊 自动恢复：{recovered_count} 个任务\n"
        if manual_count > 0:
            report += f"⚠️  需要人工介入：{manual_count} 个任务\n"
        report += "\n".join(messages)
        
        return True, report, recovered_count, manual_count
    else:
        return False, f"项目 '{project_name}' 无问题可恢复或所有恢复失败", 0, 0


def resume_project(query, auto_recover=True):
    """恢复项目执行（升级版）

    参数：
        query: 项目名称或关键词
        auto_recover: 是否自动检测和恢复问题

    返回：
        (success, message)
    """
    # 1. 查找项目
    project_id, project_name_or_matches = find_project_by_query(query)
    
    # 记录日志：项目查询
    logger = get_skill_logger("pro_global")
    if project_id:
        logger.info(f"[RESUME_QUERY] query={query}, found={project_id}", extra={'skill_name': 'RESUME'})
    
    if project_id is None:
        if project_name_or_matches is None:
            logger.error(f"[RESUME_FAIL] query={query}, error=project_not_found", extra={'skill_name': 'RESUME'})
            return False, f"未找到匹配的项目：'{query}'"
        else:
            # 多个匹配
            matches_str = "\n".join([
                f"  - {p['name']} (ID: {p['id']})" 
                for p in project_name_or_matches[:5]
            ])
            return False, f"找到多个匹配项目，请指定具体名称：\n{matches_str}"
    
    project_name = project_name_or_matches
    logger.info(f"[RESUME_START] project={project_id}, name={project_name}", extra={'skill_name': 'RESUME'})
    
    # 2. 自动检测和恢复（升级版）
    if auto_recover:
        success, message, recovered_count, manual_count = recover_project(
            project_id, logger
        )
        
        logger.info(f"[RESUME_END] project={project_id}, success={success}, recovered={recovered_count}, manual={manual_count}", extra={'skill_name': 'RESUME'})
        return success, message
    
    # 3. 传统模式（向后兼容）
    project_data = read_project_data(project_id)
    if not project_data:
        return False, f"无法读取项目数据：{project_id}"
    
    # 检查项目状态
    if project_data['project']['status'] == 'completed':
        return False, f"项目 '{project_name}' 已完成，无需继续"
    
    # 检查队列状态
    queue_status = check_queue_status(project_id)
    if queue_status.startswith("running:"):
        running_task = queue_status.split(":")[1]
        return False, f"项目 '{project_name}' 当前有任务正在执行：{running_task}，请等待完成"
    
    # 获取下一个任务
    next_task_id = get_next_task(project_id)
    
    if next_task_id == "none":
        # 检查是否有进行中的任务（可能是卡住的）
        in_progress_tasks = [
            t for t in project_data.get('tasks', [])
            if t['status'] == 'in_progress'
        ]
        
        if in_progress_tasks:
            # 处理卡住的任务
            stuck_task = in_progress_tasks[0]
            task_id = stuck_task['id']
            agent_id = stuck_task['agent']
            
            is_stuck, reason = detect_stuck_task(project_id, task_id, agent_id)
            
            if is_stuck:
                # 重置任务
                if reset_task_to_pending(project_id, task_id):
                    # 重新调度
                    success, stdout, stderr = dispatch_task(
                        project_id,
                        task_id,
                        agent_id,
                    )
                    if success:
                        logger.info(f"[RESUME_SUCCESS] project={project_id}, task={task_id}", extra={'skill_name': 'RESUME'})
                        return True, f"检测到任务 {task_id} 卡住（{reason}），已重置并重新调度给 {agent_id}"
                    else:
                        logger.error(f"[RESUME_FAIL] project={project_id}, error={stderr[:200]}", extra={'skill_name': 'RESUME'})
                        return False, f"重置任务成功，但调度失败：{stderr}"
                else:
                    return False, f"任务 {task_id} 卡住（{reason}），但重置失败"
            else:
                return False, f"任务 {task_id} 状态正常，可能正在执行中，请稍后再试"
        else:
            return False, f"项目 '{project_name}' 所有任务已完成，无需继续"
    
    # 调度下一个任务
    task_info = get_task_info(project_data, next_task_id)
    if not task_info:
        return False, f"无法获取任务信息：{next_task_id}"
    
    agent_id = task_info['agent']
    task_name = task_info['name']
    
    # 如果任务状态是 in_progress，先检查是否卡住
    if task_info['status'] == 'in_progress':
        is_stuck, reason = detect_stuck_task(project_id, next_task_id, agent_id)
        if is_stuck:
            if not reset_task_to_pending(project_id, next_task_id):
                logger.warning(f"[RESUME_RESET_FAIL] task={next_task_id} 重置失败，跳过调度", extra={'skill_name': 'RESUME'})
                return False, f"任务 {next_task_id} 卡住但重置失败"
    
    # 记录日志：调度前
    logger.info(f"[RESUME_DISPATCH] project={project_id}, task={next_task_id}, agent={agent_id}", extra={'skill_name': 'RESUME'})
    
    # 调度任务
    success, stdout, stderr = dispatch_task(
        project_id,
        next_task_id,
        agent_id,
    )
    
    if success:
        logger.info(f"[RESUME_SUCCESS] project={project_id}, task={next_task_id}", extra={'skill_name': 'RESUME'})
        return True, f"✅ 项目 '{project_name}' 已恢复\n📋 正在调度：{task_name} ({next_task_id})\n👤 执行 Agent：{agent_id}"
    else:
        logger.error(f"[RESUME_FAIL] project={project_id}, error={stderr[:200]}", extra={'skill_name': 'RESUME'})
        return False, f"调度任务失败：{stderr}"


def resume_all_projects():
    """恢复所有项目"""
    logger = get_skill_logger("pro_global")
    logger.info("[RESUME_ALL] 开始批量恢复所有项目", extra={'skill_name': 'RESUME'})
    
    projects = find_projects()
    if not projects:
        return False, "未找到任何项目"
    
    results = []
    total_recovered = 0
    total_manual = 0
    
    for project in projects:
        project_id = project['id']
        project_name = project['name']
        
        try:
            success, message, recovered, manual = recover_project(
                project_id, logger
            )
            total_recovered += recovered
            total_manual += manual
            
            if success:
                results.append(f"✅ {project_name}: 恢复 {recovered} 个，人工介入 {manual} 个")
            else:
                results.append(f"⚠️  {project_name}: {message}")
        except Exception as e:
            results.append(f"❌ {project_name}: 异常 - {e}")
            logger.error(f"[RESUME_ALL_FAIL] project={project_id}, error={e}", extra={'skill_name': 'RESUME'})
    
    report = f"📊 批量恢复完成\n"
    report += f"总项目数：{len(projects)}\n"
    report += f"自动恢复：{total_recovered} 个任务\n"
    report += f"需要人工介入：{total_manual} 个任务\n\n"
    report += "\n".join(results)
    
    logger.info(f"[RESUME_ALL_END] total={len(projects)}, recovered={total_recovered}, manual={total_manual}", extra={'skill_name': 'RESUME'})
    
    return total_recovered > 0 or total_manual == 0, report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Task Resume Skill - 恢复并继续执行项目任务')
    parser.add_argument('query', nargs='?', help='项目名称或关键词')
    parser.add_argument('--all', action='store_true', help='恢复所有项目')
    parser.add_argument('--no-auto', action='store_true', help='禁用自动检测（使用传统模式）')
    
    args = parser.parse_args()
    
    if args.all:
        success, message = resume_all_projects()
    elif args.query:
        auto_recover = not args.no_auto
        success, message = resume_project(
            args.query,
            auto_recover=auto_recover,
        )
    else:
        parser.print_help()
        print("\n示例:", file=sys.stderr)
        print("  resume.py 'AI GEO 优化调研报告'          # 恢复指定项目", file=sys.stderr)
        print("  resume.py --all                          # 恢复所有项目", file=sys.stderr)
        print("  resume.py '项目名' --no-auto             # 使用传统模式", file=sys.stderr)
        print("  resume.py '项目名'                           # 恢复指定项目", file=sys.stderr)
        log_skill_step_failure(
            "RESUME_CLI",
            "RESUME",
            "missing_args",
            "need --all or project query",
            "",
        )
        sys.exit(1)
    
    print(message)
    if not success:
        pid_for_log = ""
        if args.query:
            fpid, _rest = find_project_by_query(args.query)
            if fpid:
                pid_for_log = fpid
            else:
                pid_for_log = args.query
        mode = "all" if args.all else "single"
        log_skill_step_failure(
            pid_for_log or "RESUME_UNKNOWN",
            "RESUME",
            "cli_exit_failed",
            (message or "")[:500],
            mode,
        )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
