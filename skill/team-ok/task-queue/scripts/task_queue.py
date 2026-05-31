#!/usr/bin/env python3
"""Task Queue Skill - 串行任务队列管理（支持优先级调度和抢占）

功能:
- 按优先级排序选择下一个任务
- 支持任务抢占（高优先级任务可中断低优先级任务）
- 保持子任务串行执行
"""

import os
import sys
import logging
import fcntl
import json
import argparse
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.agent_auth import assert_agent_allowed
from common.graph_gate import assert_valid_task_graph
from common.config import QUEUE_CMD_TIMEOUT
from common.logger import get_skill_logger, log_skill_step_failure, normalize_project_id
from common.task_data_store import is_pid_alive

# 队列锁过期时间（小时）：超过此时间未释放的锁视为过期
QUEUE_LOCK_TIMEOUT_HOURS = 2



def _task_lock_path(project_id: str) -> Path:
    """与 project-data 的 get_lock_file 一致：项目目录下 .task.lock。"""
    corrected_id = normalize_project_id(project_id)
    return Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / ".task.lock"


def get_queue_file(project_id):
    """获取队列文件路径（如果文件不存在，返回路径而不报错）"""
    corrected_id = normalize_project_id(project_id)
    queue_file = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / ".task_queue"
    return queue_file

def get_data_file(project_id):
    """获取项目数据文件路径（带自动修正和验证）"""
    corrected_id = normalize_project_id(project_id)
    data_file = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / "task_data.json"
    
    if not data_file.exists():
        raise FileNotFoundError(f"项目未初始化（缺少 task_data.json）：{corrected_id}")
    
    return data_file

def _parse_queue_lock(content: str) -> Optional[str]:
    """解析队列文件内容，提取任务 ID。

    兼容两种格式：
    - 旧格式 v1（平滑升级）：纯文本 task_id
    - 新格式 v2：JSON {"task_id": "...", "pid": ..., "locked_at": "...", "expires_at": "..."}

    Returns:
        任务 ID 字符串，无内容时返回 None
    """
    content = content.strip()
    if not content or content == "[]":
        return None
    # 尝试 JSON 格式
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data.get("task_id")
        if isinstance(data, list) and data:
            # v1 enqueue 格式（重试队列）— 不是 running，让 cmd_status 返回 idle
            return None
    except (json.JSONDecodeError, ValueError):
        pass
    # 回退：纯文本（旧格式兼容）
    return content


def _is_queue_lock_stale(queue_file: Path) -> tuple[bool, Optional[str]]:
    """检查队列锁是否过期（PID 死亡或超时）。

    Returns:
        (is_stale, task_id): True 表示锁已过期，可安全覆盖
    """
    try:
        content = queue_file.read_text(encoding="utf-8").strip()
    except OSError:
        return True, None

    if not content or content == "[]":
        return True, None

    # 尝试 JSON 格式解析
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            task_id = data.get("task_id", "")
            pid = data.get("pid")
            expires_at_str = data.get("expires_at")

            # 检查 PID 是否存活
            if pid is not None and not is_pid_alive(pid):
                return True, task_id

            # 检查是否超时
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() > expires_at:
                        return True, task_id
                except ValueError:
                    pass

            return False, task_id  # 锁有效

        if isinstance(data, list):
            # enqueue list — 不是有效锁，视为过期让 cmd_start 覆盖
            return True, None

    except (json.JSONDecodeError, ValueError):
        pass

    # 旧格式（纯文本）：无法判断是否过期，视为有效
    return False, content


def read_data(project_id):
    """读取 task_data.json；缺失或 JSON 损坏时非 0 退出（非 LLM 硬错误）。"""
    try:
        path = get_data_file(project_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        cid = normalize_project_id(project_id)
        data_path = (
            Path.home()
            / ".openclaw"
            / "tasks"
            / "projects"
            / cid
            / "task_data.json"
        )
        log_skill_step_failure(
            cid,
            "QUEUE",
            "read_data_missing",
            "task_data.json not found",
            str(data_path),
        )
        print(
            f"Error: 项目数据不存在或未初始化（缺少 task_data.json）：{cid}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        cid = normalize_project_id(project_id)
        log_skill_step_failure(
            cid,
            "QUEUE",
            "read_data_json_error",
            str(e),
            "",
        )
        print(f"Error: task_data.json 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_enqueue(project_id, task_id):
    """将指定任务重新加入队列（用于质量门禁失败后的重试）"""
    corrected_id = normalize_project_id(project_id)
    base = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id
    queue_file = base / ".task_queue"
    lock_path = _task_lock_path(project_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            current = []
            if queue_file.exists():
                try:
                    current = json.loads(queue_file.read_text(encoding="utf-8").strip() or "[]")
                except (json.JSONDecodeError, OSError):
                    current = []
            current.append(task_id)
            queue_file.write_text(json.dumps(current), encoding="utf-8")

            logger = get_skill_logger(corrected_id)
            logger.info(f"[QUEUE_ENQUEUE] project={corrected_id}, task={task_id}", extra={'skill_name': 'QUEUE'})
            print(f"Task {task_id} enqueued")
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def cmd_status(project_id):
    """检查队列状态"""
    # 直接构建路径，不使用 get_queue_file（避免文件不存在时抛出异常）
    corrected_id = normalize_project_id(project_id)
    queue_file = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / ".task_queue"

    if queue_file.exists():
        try:
            content = queue_file.read_text(encoding="utf-8").strip()
        except OSError:
            content = ""
        if content and content != '[]':
            task_id = _parse_queue_lock(content)
            if task_id:
                logger = get_skill_logger(corrected_id)
                logger.info(f"[QUEUE_STATUS] project={corrected_id}, status=running, task={task_id}", extra={'skill_name': 'QUEUE'})
                print(f"running:{task_id}")
                return
    logger = get_skill_logger(corrected_id)
    logger.info(f"[QUEUE_STATUS] project={corrected_id}, status=idle", extra={'skill_name': 'QUEUE'})
    print("idle")

def get_next_pending_subtask(task):
    """获取下一个待执行的子任务（串行执行）"""
    subtasks = task.get('subtasks', [])
    if not subtasks:
        return None
    
    # 按ID排序（确保顺序）
    sorted_subtasks = sorted(subtasks, key=lambda x: x.get('id', ''))
    
    for subtask in sorted_subtasks:
        if subtask['status'] == 'pending':
            # 检查是否有前置子任务未完成
            current_idx = sorted_subtasks.index(subtask)
            if current_idx == 0:
                return subtask  # 第一个子任务
            
            # 检查前面所有子任务是否都已完成
            all_prev_completed = all(
                sorted_subtasks[i]['status'] == 'completed'
                for i in range(current_idx)
            )
            
            if all_prev_completed:
                return subtask
    
    return None

def are_all_subtasks_completed(task):
    """检查任务的所有子任务是否都已完成"""
    subtasks = task.get('subtasks', [])
    if not subtasks:
        return True
    return all(sub['status'] == 'completed' for sub in subtasks)

def check_dependencies_satisfied(task, all_tasks):
    """检查任务的依赖是否都已完成"""
    deps = task.get('dependencies', [])
    if not deps:
        return True
    
    # 过滤无效依赖
    valid_deps = [d for d in deps if d and str(d).lower() not in ('null', 'none', '')]
    if not valid_deps:
        return True
    
    # 检查每个依赖是否已完成
    for dep_id in valid_deps:
        dep_task = next((t for t in all_tasks if t['id'] == dep_id), None)
        if not dep_task:
            return False
        if dep_task['status'] not in ('completed', 'needs_review'):
            return False
    
    return True

def cmd_next(project_id, check_preempt=False):
    """获取下一个可执行任务或子任务
    
    参数:
        check_preempt: 是否检查抢占（默认 False）
    """
    corrected_id = normalize_project_id(project_id)
    logger = get_skill_logger(corrected_id)
    data = read_data(project_id)
    all_tasks = data.get('tasks', [])
    
    # 检查当前运行中的任务
    current_task = None
    for task in all_tasks:
        if task['status'] == 'in_progress':
            current_task = task
            break
    
    # 如果有运行中的任务，先处理其子任务
    if current_task:
        next_subtask = get_next_pending_subtask(current_task)
        if next_subtask:
            # 子任务优先执行
            print(f"{current_task['id']}:{next_subtask['id']}")
            return
        
        # 检查是否需要抢占
        if check_preempt and current_task.get('preemptible', True):
            # 获取所有可抢占的高优先级任务
            ready_tasks = get_ready_tasks(all_tasks, current_task)
            if ready_tasks:
                # 按优先级排序
                ready_tasks.sort(key=lambda t: (t.get('priority', 999), t['id']))
                highest_priority = ready_tasks[0]
                
                # 如果高优先级任务的优先级数值更小（更高）
                current_priority = current_task.get('priority', 999)
                if highest_priority['priority'] < current_priority:
                    # 可以抢占，返回抢占标识
                    print(f"preempt:{highest_priority['id']}:{current_task['id']}")
                    return
    
    # 正常获取下一个任务（按优先级排序）
    ready_tasks = get_ready_tasks(all_tasks, None)
    if ready_tasks:
        # 按优先级排序（priority 数值越小越高）
        ready_tasks.sort(key=lambda t: (t.get('priority', 999), t['id']))
        logger.info(f"[QUEUE_NEXT] project={corrected_id}, task={ready_tasks[0]['id']}, priority={ready_tasks[0].get('priority', 999)}", extra={'skill_name': 'QUEUE'})
        print(ready_tasks[0]['id'])
        return

    logger.info(f"[QUEUE_NEXT] project={corrected_id}, result=none", extra={'skill_name': 'QUEUE'})
    print("none")


def get_ready_tasks(all_tasks, current_task=None):
    """获取所有就绪的任务（依赖已满足且状态为 pending）"""
    ready = []
    for task in all_tasks:
        if task['status'] != 'pending':
            continue
        # 排除当前正在执行的任务（如果是抢占检查模式）
        if current_task and task['id'] == current_task['id']:
            continue
        # 检查依赖是否满足
        if check_dependencies_satisfied(task, all_tasks):
            ready.append(task)
    return ready

def cmd_next_subtask(project_id, parent_task_id):
    """获取指定父任务的下一个可执行子任务"""
    corrected_id = normalize_project_id(project_id)
    logger = get_skill_logger(corrected_id)
    data = read_data(project_id)

    for task in data.get('tasks', []):
        if task['id'] == parent_task_id:
            next_subtask = get_next_pending_subtask(task)
            if next_subtask:
                logger.info(f"[QUEUE_NEXT_SUBTASK] project={corrected_id}, parent={parent_task_id}, subtask={next_subtask['id']}", extra={'skill_name': 'QUEUE'})
                print(next_subtask['id'])
                return
            break
    logger.info(f"[QUEUE_NEXT_SUBTASK] project={corrected_id}, parent={parent_task_id}, result=none", extra={'skill_name': 'QUEUE'})
    print("none")

def cmd_check_subtasks(project_id, parent_task_id):
    """检查父任务的所有子任务是否都已完成"""
    corrected_id = normalize_project_id(project_id)
    logger = get_skill_logger(corrected_id)
    data = read_data(project_id)

    for task in data.get('tasks', []):
        if task['id'] == parent_task_id:
            if are_all_subtasks_completed(task):
                logger.info(f"[QUEUE_CHECK_SUBTASKS] project={corrected_id}, parent={parent_task_id}, result=completed", extra={'skill_name': 'QUEUE'})
                print("completed")
            else:
                logger.info(f"[QUEUE_CHECK_SUBTASKS] project={corrected_id}, parent={parent_task_id}, result=pending", extra={'skill_name': 'QUEUE'})
                print("pending")
            return
    logger.info(f"[QUEUE_CHECK_SUBTASKS] project={corrected_id}, parent={parent_task_id}, result=not_found", extra={'skill_name': 'QUEUE'})
    print("not_found")

def cmd_start(project_id, task_id, require_valid_graph=False):
    """开始任务（与 project-data 共用 .task.lock，保证队列读写与任务数据变更互斥）。

    .task_queue 存储 JSON 格式：{"task_id", "pid", "locked_at", "expires_at"}。
    启动时检查已有锁是否过期（PID 死亡或超时），过期则自动释放并继续。
    """
    if require_valid_graph:
        assert_valid_task_graph(project_id)
    corrected_id = normalize_project_id(project_id)
    base = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id
    queue_file = base / ".task_queue"
    lock_path = _task_lock_path(project_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    logger = get_skill_logger(corrected_id)

    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            if queue_file.exists():
                stale, current_task_id = _is_queue_lock_stale(queue_file)
                if current_task_id and not stale:
                    log_skill_step_failure(
                        corrected_id,
                        "QUEUE",
                        "start_already_running",
                        f"current={current_task_id}, requested={task_id}",
                        str(queue_file),
                    )
                    print(
                        f"Error: Task {current_task_id} already running",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                if current_task_id and stale:
                    logger.warning(
                        f"[QUEUE_STALE_LOCK] task={current_task_id}, "
                        f"stale lock auto-released",
                        extra={"skill_name": "QUEUE"},
                    )
            # 写入 JSON 格式锁信息
            now = datetime.now()
            lock_data = {
                "task_id": task_id,
                "pid": os.getpid(),
                "locked_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=QUEUE_LOCK_TIMEOUT_HOURS)).isoformat(),
            }
            try:
                queue_file.write_text(json.dumps(lock_data), encoding="utf-8")
            except OSError as e:
                log_skill_step_failure(
                    corrected_id,
                    "QUEUE",
                    "start_write_queue_failed",
                    str(e),
                    str(queue_file),
                )
                print(f"Error: 无法写入队列文件: {e}", file=sys.stderr)
                sys.exit(1)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

    # 【状态同步】锁已释放，安全调用 project-data 同步状态
    # 注意：必须先释放锁再调用子进程，否则 macOS 上 fcntl.flock 为文件级锁，
    # 子进程 project_data.py 同样会获取同一锁，导致父子进程死锁。
    project_data_py = str(
        Path.home()
        / ".openclaw"
        / "skills"
        / "team-ok"
        / "project-data"
        / "scripts"
        / "project_data.py"
    )
    subprocess.run(
        [project_data_py, "update-task", corrected_id, task_id, "in_progress"],
        capture_output=True,
        text=True,
        timeout=QUEUE_CMD_TIMEOUT,
    )

    logger = get_skill_logger(corrected_id)
    logger.info(
        f"[QUEUE_START] project={corrected_id}, task={task_id}, result=success",
        extra={"skill_name": "QUEUE"},
    )
    print(f"Task {task_id} started")

def cmd_release(project_id):
    """释放队列（持 .task.lock，与 start / project-data 一致）。"""
    corrected_id = normalize_project_id(project_id)
    base = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id
    queue_file = base / ".task_queue"
    lock_path = _task_lock_path(project_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            if queue_file.exists():
                try:
                    queue_file.unlink()
                except OSError as e:
                    print(f"Warning: 无法删除队列文件: {e}", file=sys.stderr)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

    logger = get_skill_logger(corrected_id)
    logger.info(f"[QUEUE_RELEASE] project={corrected_id}", extra={"skill_name": "QUEUE"})
    print("Queue released")

def main():
    # 角色边界检查：仅 Main Agent 可管理队列
    assert_agent_allowed("task-queue")

    parser = argparse.ArgumentParser(description='Task Queue Manager')
    subparsers = parser.add_subparsers(dest='command')
    
    # status
    p_status = subparsers.add_parser('status', help='Check queue status')
    p_status.add_argument('project_id')
    
    # next
    p_next = subparsers.add_parser('next', help='Get next executable task/subtask')
    p_next.add_argument('project_id')
    p_next.add_argument('--check-preempt', action='store_true', help='Check if current task can be preempted')
    
    # next-subtask
    p_next_sub = subparsers.add_parser('next-subtask', help='Get next executable subtask for parent task')
    p_next_sub.add_argument('project_id')
    p_next_sub.add_argument('parent_task_id')
    
    # check-subtasks
    p_check_sub = subparsers.add_parser('check-subtasks', help='Check if all subtasks are completed')
    p_check_sub.add_argument('project_id')
    p_check_sub.add_argument('parent_task_id')
    
    # start
    p_start = subparsers.add_parser('start', help='Start task (acquire lock)')
    p_start.add_argument('project_id')
    p_start.add_argument('task_id')
    p_start.add_argument(
        '--require-valid-graph',
        action='store_true',
        help='持锁前执行 project-data check-cycle；图非法则非 0 退出',
    )
    
    # release
    p_release = subparsers.add_parser('release', help='Release queue lock')
    p_release.add_argument('project_id')

    # enqueue
    p_enqueue = subparsers.add_parser('enqueue', help='Re-enqueue a task (for QG retry)')
    p_enqueue.add_argument('project_id')
    p_enqueue.add_argument('task_id')

    args = parser.parse_args()
    
    if args.command == 'status':
        cmd_status(args.project_id)
    elif args.command == 'next':
        cmd_next(args.project_id, getattr(args, 'check_preempt', False))
    elif args.command == 'next-subtask':
        cmd_next_subtask(args.project_id, args.parent_task_id)
    elif args.command == 'check-subtasks':
        cmd_check_subtasks(args.project_id, args.parent_task_id)
    elif args.command == 'start':
        cmd_start(
            args.project_id,
            args.task_id,
            getattr(args, 'require_valid_graph', False),
        )
    elif args.command == 'release':
        cmd_release(args.project_id)
    elif args.command == 'enqueue':
        cmd_enqueue(args.project_id, args.task_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
