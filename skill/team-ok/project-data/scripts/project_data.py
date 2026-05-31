#!/usr/bin/env python3
"""Project Data Skill - 项目数据管理（带文件锁）

统一通报规则:
- 状态变为 in_progress → 发送"开始"通报
- 状态变为 completed → 发送"完成"通报
- 用户确认项目后 → 发送 project_start 通报（此时所有任务已添加）

依赖规则:
- 任务只能依赖已存在的任务
- 支持循环依赖自动检测
- 支持依赖传播（自动推导可选依赖）

优先级规则:
- 数值越小优先级越高
- 支持任务抢占（可配置）

【新增】--my-task 命令支持:
- 自动从 trigger 文件读取 project_id 和 task_id
- 验证当前 Agent 是否有权限操作
"""

import sys
import json
import logging
import re
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.agent_auth import assert_agent_allowed, is_cli_mode, get_current_agent_id
from common.logger import get_skill_logger, log_skill_step_failure
from common.task_data_store import atomic_write_json
import fcntl
import argparse
import subprocess
import os
from datetime import datetime
from collections import defaultdict, deque

# ========== 依赖传播规则 ==========
DEPENDENCY_RULES = {
    "product": ["researcher"],
    "designer": ["product"],
    "developer": ["product", "designer"],
    "ops": ["developer"],
    "docs": ["developer", "ops"],
    "content": ["researcher"],
    "seo": ["researcher", "content"],
    "social": ["content", "seo"],
    "email": ["content", "seo"],
    "consultation": ["researcher"],
    "coordinator": ["consultation", "product"]
}

from common.logger import normalize_project_id

# ========== Agent 能力关键词 ==========
AGENT_CAPABILITIES = {
    "researcher": ["调研", "分析", "竞品", "市场", "数据", "研究", "调查", "收集"],
    "product": ["需求", "PRD", "产品", "规划", "功能", "规格", "用户体验"],
    "designer": ["设计", "UI", "视觉", "交互", "原型", "界面", "配色", "布局"],
    "developer": ["开发", "代码", "实现", "技术", "架构", "前端", "后端", "API"],
    "ops": ["部署", "运维", "服务器", "上线", "CI/CD", "Docker", "Nginx"],
    "docs": ["文档", "API", "手册", "说明", "技术文档"],
    "content": ["文案", "内容", "创作", "策划", "文章", "推广"],
    "seo": ["SEO", "优化", "排名", "流量", "关键词", "搜索引擎"],
    "social": ["社交", "社媒", "微博", "微信", "社区", "运营"],
    "email": ["邮件", "EDM", "营销邮件", "群发"],
    "consultation": ["咨询", "战略", "商业模式", "规划", "顾问"],
    "coordinator": ["合规", "审查", "法务", "风险", "审核", "法律"]
}


def _fail_data(project_id: str, step: str, detail: str, ctx: str = "") -> None:
    cid = normalize_project_id(project_id or "")
    log_skill_step_failure(cid or (project_id or "_"), "PROJECT_DATA", step, detail, ctx)
    sys.exit(1)


def _fail_registry(step: str, detail: str, ctx: str = "") -> None:
    log_skill_step_failure("SKILL_REGISTRY", "PROJECT_DATA", step, detail, ctx)
    sys.exit(1)


def get_data_file(project_id):
    """获取项目数据文件路径（带自动修正和验证）"""
    corrected_id = normalize_project_id(project_id)
    data_file = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / "task_data.json"
    
    # 验证文件是否存在
    if not data_file.exists():
        project_dir = data_file.parent
        if project_dir.exists():
            raise FileNotFoundError(
                f"项目未初始化（缺少 task_data.json）：{corrected_id}\n"
                f"请先调用 project-init 重新创建项目"
            )
        else:
            raise FileNotFoundError(f"项目不存在：{corrected_id}")
    
    return data_file

def get_lock_file(project_id):
    """获取项目锁文件路径（带自动修正）"""
    corrected_id = normalize_project_id(project_id)
    return Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / ".task.lock"

def read_data(project_id):
    """读取项目数据（带初始化验证）"""
    data_file = get_data_file(project_id)
    
    # 【新增】验证项目是否已正确初始化
    if not data_file.exists():
        # 检查项目目录是否存在
        project_dir = data_file.parent
        if project_dir.exists():
            # 目录存在但没有 task_data.json → 初始化失败
            print(f"Error: 项目 {project_id} 未正确初始化（缺少 task_data.json）", file=sys.stderr)
            print(f"建议：删除残废目录，重新调用 project-init 创建项目", file=sys.stderr)
        else:
            print(f"Error: 项目 {project_id} 不存在", file=sys.stderr)
        _fail_data(project_id, "read_data_uninitialized", "missing task_data.json or project dir", str(data_file.parent))
    
    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_data(project_id, data):
    data_file = get_data_file(project_id)
    atomic_write_json(data_file, data)

def get_current_task_from_trigger(agent_id=None):
    """从 trigger 文件获取当前任务信息
    
    Returns:
        tuple: (project_id, task_id) 或 (None, None) 如果没有 trigger 文件
    
    如果不指定 agent_id，从环境变量 OPENCODE_AGENT_ID 获取
    """
    if agent_id is None:
        agent_id = os.environ.get('OPENCODE_AGENT_ID')
    
    if not agent_id:
        print("Error: 无法获取 Agent ID，请设置 OPENCODE_AGENT_ID 环境变量", file=sys.stderr)
        return None, None
    
    # 查找 trigger 目录
    trigger_dir = Path.home() / f".openclaw/workspace-{agent_id}/.trigger"
    
    if not trigger_dir.exists():
        print(f"Error: trigger 目录不存在: {trigger_dir}", file=sys.stderr)
        return None, None
    
    # 获取最新的 trigger 文件
    trigger_files = list(trigger_dir.glob("*.trigger"))
    
    if not trigger_files:
        print(f"Error: 无待执行任务（没有 trigger 文件）", file=sys.stderr)
        return None, None
    
    # 使用最新的 trigger 文件
    trigger_file = sorted(trigger_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    
    try:
        with open(trigger_file, 'r', encoding='utf-8') as f:
            trigger_data = json.load(f)
        
        project_id = trigger_data.get('project_id')
        task_id = trigger_data.get('task_id')
        
        if not project_id or not task_id:
            print(f"Error: trigger 文件内容不完整", file=sys.stderr)
            return None, None
        
        return project_id, task_id
    except Exception as e:
        print(f"Error: 读取 trigger 文件失败: {e}", file=sys.stderr)
        return None, None

def verify_task_owner(project_id, task_id, agent_id=None):
    """验证任务是否属于当前 Agent
    
    Returns:
        tuple: (is_owner, task_data)
            - is_owner: True 如果任务属于当前 Agent
            - task_data: 任务数据
    """
    if agent_id is None:
        agent_id = os.environ.get('OPENCODE_AGENT_ID')
    
    data = read_data(project_id)
    
    task = None
    for t in data.get('tasks', []):
        if t['id'] == task_id:
            task = t
            break
    
    if not task:
        print(f"Error: 任务 {task_id} 不存在", file=sys.stderr)
        return False, None
    
    if task.get('agent') != agent_id:
        print(f"Error: 任务 {task_id} 不属于当前 Agent (当前: {agent_id}, 任务: {task.get('agent')})", file=sys.stderr)
        return False, task
    
    return True, task

def send_notification(project_id, event_type, *args, sync=False):
    """发送 Telegram 通知
    
    参数:
        sync: 是否同步等待发送完成
              - task_start, subtask_start: 建议 sync=True（确保消息与执行一致）
              - task_complete, subtask_complete: 建议 sync=True（确保确实完成）
              - project_complete: 可 sync=False（不阻塞后续流程）
              - task_created, subtask_created: 可 sync=False（仅创建通知）
    """
    try:
        log_dir = Path.home() / ".openclaw" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "notify_errors.log"
        
        # 记录通知类型和同步状态
        sync_status = "同步" if sync else "异步"
        timestamp = datetime.now().isoformat()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {event_type} ({sync_status}) 开始发送\n")
        
        if sync:
            # 同步发送：等待完成
            with open(log_file, 'a', encoding='utf-8') as f:
                subprocess.run(
                    [str(Path.home() / ".openclaw" / "skills" / "team-ok" / "notify-telegram" / "scripts" / "notify.py"),
                     project_id, event_type] + list(args),
                    stdout=f,
                    stderr=f,
                    timeout=PROJECT_DATA_CMD_TIMEOUT
                )
            # 记录同步发送完成
            timestamp = datetime.now().isoformat()
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {event_type} 同步发送完成\n")
            
            # 同时记录到项目 Skill 日志
            try:
                skill_logger = get_skill_logger(project_id)
                skill_logger.info(f"[NOTIFY_SENT] event={event_type}, mode=sync, args={args}", extra={'skill_name': 'NOTIFY'})
            except Exception:
                pass  # 忽略项目日志记录失败
        else:
            # 异步发送：立即返回
            with open(log_file, 'a', encoding='utf-8') as f:
                subprocess.Popen(
                    [str(Path.home() / ".openclaw" / "skills" / "team-ok" / "notify-telegram" / "scripts" / "notify.py"),
                     project_id, event_type] + list(args),
                    stdout=f,
                    stderr=f,
                    start_new_session=True
                )
            # 异步不记录完成（由子进程记录）
            
            # 同时记录到项目 Skill 日志
            try:
                skill_logger = get_skill_logger(project_id)
                skill_logger.info(f"[NOTIFY_SENT] event={event_type}, mode=async, args={args}", extra={'skill_name': 'NOTIFY'})
            except Exception:
                pass  # 忽略项目日志记录失败
    except Exception as e:
        log_dir = Path.home() / ".openclaw" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "notify_errors.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"send_notification exception: {e}\n")

def _task_rank(task_id: str) -> int:
    """从 task_001 / task_042 解析序号，用于安全依赖传播（只向更早任务边）。"""
    if not task_id:
        return 0
    m = re.match(r"^task_(\d+)$", str(task_id).strip())
    return int(m.group(1)) if m else 0


def validate_tasks_graph(tasks) -> tuple:
    """校验整张任务依赖图：无未知依赖、无自依赖、无环（Kahn 拓扑）。

    边语义：若 task T 依赖 D，则 D 完成后才能启动 T，即边 D -> T。

    返回 (True, None) 或 (False, 错误说明)。
    """
    if not tasks:
        return True, None
    task_ids = {t["id"] for t in tasks}
    for t in tasks:
        tid = t["id"]
        for raw in t.get("dependencies") or []:
            d = (raw or "").strip()
            if not d or d.lower() in ("null", "none"):
                continue
            if d == tid:
                return False, f"自依赖: {tid} -> {tid}"
            if d not in task_ids:
                return False, f"任务 {tid} 依赖不存在的任务: {d}"

    adj = defaultdict(list)
    indeg = {tid: 0 for tid in task_ids}
    for t in tasks:
        tid = t["id"]
        for raw in t.get("dependencies") or []:
            d = (raw or "").strip()
            if not d or d.lower() in ("null", "none") or d not in task_ids:
                continue
            adj[d].append(tid)
            indeg[tid] += 1
    q = deque([i for i in task_ids if indeg[i] == 0])
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if seen != len(task_ids):
        return False, "存在循环依赖（拓扑无法完成）；请检查 task_data.json 中的 dependencies"
    return True, None


def validate_dependencies(data, deps, current_task_id):
    """验证依赖是否合法
    
    规则:
    1. 依赖的任务必须已存在
    2. 不能依赖自己
    3. 检测循环依赖
    """
    if not deps:
        return True, None
    
    existing_task_ids = {t['id'] for t in data['tasks']}
    
    for dep in deps:
        if dep == current_task_id:
            return False, f"Task cannot depend on itself: {dep}"
        if dep not in existing_task_ids:
            return False, f"Dependency task does not exist: {dep}"
    
    # 检测循环依赖
    cycle = detect_cycle(data['tasks'], current_task_id, deps)
    if cycle:
        return False, f"Circular dependency detected: {' -> '.join(cycle)}"
    
    return True, None


def detect_cycle(tasks, new_task_id, new_deps):
    """检测循环依赖
    
    使用 DFS 检测添加新依赖后是否会形成环
    返回: 环路径列表 或 None
    """
    # 构建现有任务的依赖图
    graph = defaultdict(list)
    for task in tasks:
        task_id = task['id']
        deps = task.get('dependencies', [])
        for dep in deps:
            if dep:  # 排除空依赖
                graph[dep].append(task_id)  # dep -> task_id
    
    # 添加新任务的边
    for dep in new_deps:
        if dep:
            graph[dep].append(new_task_id)
    
    # DFS 检测环
    visited = set()
    rec_stack = set()
    path = []
    
    def dfs(node, current_path):
        visited.add(node)
        rec_stack.add(node)
        current_path.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                result = dfs(neighbor, current_path[:])
                if result:
                    return result
            elif neighbor in rec_stack:
                # 找到环
                cycle_start = current_path.index(neighbor)
                return current_path[cycle_start:] + [neighbor]
        
        rec_stack.remove(node)
        return None
    
    # 从新任务开始检测
    result = dfs(new_task_id, [])
    return result


def validate_dependencies_semantic(tasks, new_task_id, deps, agent):
    """语义验证：检查依赖关系是否合理

    非阻塞警告（不阻止操作），但会输出 warning 提示可能的问题：
    1. 依赖的任务 Agent 与当前任务 Agent 在流水线中的顺序是否合理
    2. 依赖的任务是否在更早的位置（task_id 更小）
    """
    warnings = []

    # 按 DEPENDENCY_RULES 检查 Agent 流水线顺序
    agent_order = ["researcher", "consultation", "product", "designer", "developer",
                   "tester", "ops", "docs", "content", "seo", "social", "email", "coordinator"]

    if agent in agent_order:
        agent_idx = agent_order.index(agent)
        for dep_id in deps:
            dep_task = next((t for t in tasks if t["id"] == dep_id), None)
            if dep_task:
                dep_agent = dep_task.get("agent", "")
                if dep_agent in agent_order:
                    dep_idx = agent_order.index(dep_agent)
                    if dep_idx > agent_idx:
                        warnings.append(
                            f"语义警告: 任务 '{new_task_id}' ({agent}) 依赖 '{dep_id}' ({dep_agent})，"
                            f"但 {dep_agent} 在流水线中位于 {agent} 之后"
                        )

    # 检查是否依赖了更晚创建的任务（task_id 更大）
    new_rank = _task_rank(new_task_id)
    for dep_id in deps:
        dep_rank = _task_rank(dep_id)
        if dep_rank > new_rank:
            warnings.append(
                f"语义警告: 任务 '{new_task_id}' 依赖了更晚创建的任务 '{dep_id}'"
            )

    return warnings


def auto_propagate_dependencies(tasks):
    """依赖传播：按 DEPENDENCY_RULES 自动补充依赖。

    【重要】仅向「序号更小」的同 agent 任务连边，避免把尚未执行的下游任务
    （如 task_003）误挂到上游任务（如 task_002）上，从而形成
    task_002 <-> task_003 一类循环依赖（历史事故根因）。
    """
    for task in tasks:
        agent = task.get('agent', '')
        if agent not in DEPENDENCY_RULES:
            continue
        
        required_agents = DEPENDENCY_RULES[agent]
        current_deps = set(task.get('dependencies', []))
        cur_rank = _task_rank(task['id'])
        
        for required_agent in required_agents:
            for dep_task in tasks:
                if dep_task['id'] == task['id']:
                    continue
                if dep_task.get('agent') != required_agent:
                    continue
                if _task_rank(dep_task['id']) >= cur_rank:
                    continue
                current_deps.add(dep_task['id'])
        
        task['dependencies'] = list(current_deps)
    
    return tasks


def recommend_agent(task_name, task_description=""):
    """根据任务名称和描述自动推荐合适的 Agent
    
    使用关键词匹配算法
    返回: Agent ID
    """
    text = (task_name + " " + task_description).lower()
    scores = {}
    
    for agent, keywords in AGENT_CAPABILITIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        scores[agent] = score
    
    # 排序返回最高分
    if max(scores.values()) > 0:
        best = max(scores, key=scores.get)
        return best
    
    return "main"  # 默认分配给 main

def add_task(project_id, name, agent, description="", dependencies="", priority=None, preemptible=True, timeout_minutes=None, max_retries=None, parent=None, task_id=None, task_type="", reviewer=""):
    """添加任务，按添加顺序生成 task_id

    参数:
        priority: 优先级（数值越小越高），默认按添加顺序递增
        preemptible: 是否可被抢占，默认 True
        timeout_minutes: 超时分钟数，默认 10
        max_retries: 最大重试次数，默认 0（不重试）
        parent: 父任务 ID（用于子任务）
        task_id: 自定义任务 ID（不提供则自动按顺序生成）
    """
    lock_file = get_lock_file(project_id)

    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            # 必须在持锁后读取，避免并发 add_task 导致 task_id 重复或依赖误判
            data = read_data(project_id)
            now = datetime.now().isoformat()

            # 解析依赖，过滤掉空值、"null" 和 "none"
            deps = [d.strip() for d in dependencies.split(",") if d.strip() and d.strip().lower() not in ("null", "none", "")]

            # 使用提供的 task_id 或自动生成
            if task_id:
                # 验证自定义 task_id 是否已被使用
                existing_ids = {t['id'] for t in data['tasks']}
                if task_id in existing_ids:
                    print(f"Error: 任务 ID '{task_id}' 已存在", file=sys.stderr)
                    _fail_data(project_id, "add_task_duplicate_id", f"duplicate task_id={task_id}", task_id)
            else:
                # 按顺序生成 task_id
                task_num = len(data['tasks']) + 1
                task_id = f"task_{task_num:03d}"
            
            # 验证依赖（包括循环检测）
            if deps:
                valid, error_msg = validate_dependencies(data, deps, task_id)
                if not valid:
                    print(f"Error: {error_msg}", file=sys.stderr)
                    _fail_data(project_id, "add_task_invalid_deps", error_msg, task_id)

            # 语义验证（非阻塞警告）
            semantic_warnings = validate_dependencies_semantic(data.get("tasks", []), task_id, deps, agent)
            for warning in semantic_warnings:
                print(warning, file=sys.stderr)
                logger = get_skill_logger(project_id)
                logger.warning(f"[SEMANTIC_WARN] {warning}", extra={"skill_name": "PROJECT-DATA"})
            
            # 计算优先级（默认按添加顺序）
            if priority is None:
                priority = len(data['tasks']) + 1
            
            # 创建任务对象
            task = {
                "id": task_id,
                "name": name,
                "description": description,
                "agent": agent,
                "task_type": task_type,
                "reviewer": reviewer,
                "status": "pending",
                "dependencies": deps,
                "priority": priority,
                "preemptible": preemptible,
                "timeout_minutes": timeout_minutes if timeout_minutes else 10,
                "max_retries": max_retries if max_retries is not None else 0,
                "retry_count": 0,
                "failed_at": None,
                "failure_reason": None,
                "subtasks": [],
                "created_at": now,
                "updated_at": now,
                "triggered_at": None,
                "started_at": None,
                "completed_at": None
            }

            # 新增：父子任务关系
            if parent:
                task["parent_task"] = parent
                task["is_subtask"] = True
            
            # 直接追加到末尾
            data['tasks'].append(task)
            
            # 自动依赖传播（仅向更早任务连边，见 auto_propagate_dependencies 说明）
            data['tasks'] = auto_propagate_dependencies(data['tasks'])
            ok_graph, graph_err = validate_tasks_graph(data['tasks'])
            if not ok_graph:
                print(f"Error: 添加任务后依赖图不合法（非 LLM 硬错误）: {graph_err}", file=sys.stderr)
                _fail_data(project_id, "add_task_invalid_graph", graph_err or "validate_tasks_graph", task_id)
            
            data['project']['updated_at'] = now
            write_data(project_id, data)
            
            # 记录任务添加日志
            logger = get_skill_logger(project_id)
            logger.info(f"[TASK_ADDED] task_id={task_id}, name={name}, agent={agent}, priority={priority}", extra={'skill_name': 'PROJECT-DATA'})
            
            print(task_id)
            return task_id
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

def add_subtask(project_id, parent_task_id, name, agent, description=""):
    """添加子任务到父任务的 subtasks 数组中"""
    lock_file = get_lock_file(project_id)
    
    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = read_data(project_id)
            now = datetime.now().isoformat()
            
            # 查找父任务
            parent_task = None
            for task in data['tasks']:
                if task['id'] == parent_task_id:
                    parent_task = task
                    break
            
            if not parent_task:
                print(f"Error: Parent task {parent_task_id} not found", file=sys.stderr)
                _fail_data(project_id, "add_subtask_parent_not_found", parent_task_id, "")
            
            # 生成子任务ID
            existing_subtasks = parent_task.get('subtasks', [])
            subtask_index = len(existing_subtasks) + 1
            subtask_id = f"{parent_task_id}_subtask_{subtask_index:03d}"
            
            # 创建子任务对象
            subtask = {
                "id": subtask_id,
                "name": name,
                "description": description,
                "agent": agent,
                "status": "pending",
                "parent_task": parent_task_id,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "completed_at": None
            }
            
            # 添加到父任务的 subtasks 数组
            if 'subtasks' not in parent_task:
                parent_task['subtasks'] = []
            parent_task['subtasks'].append(subtask)
            parent_task['updated_at'] = now
            
            data['project']['updated_at'] = now
            write_data(project_id, data)
            
            # 记录子任务添加日志
            logger = get_skill_logger(project_id)
            logger.info(f"[SUBTASK_ADDED] subtask_id={subtask_id}, parent={parent_task_id}, name={name}, agent={agent}", extra={'skill_name': 'PROJECT-DATA'})

            # 子任务创建通报
            send_notification(project_id, "subtask_created", agent, parent_task_id, subtask_id)

            print(subtask_id)
            return subtask_id
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

def list_subtasks(project_id, parent_task_id):
    """列出某个父任务的所有子任务。"""
    data = read_data(project_id)

    sub_tasks = [
        t for t in data.get("tasks", [])
        if t.get("parent_task") == parent_task_id
    ]

    if not sub_tasks:
        print(f"父任务 {parent_task_id} 没有子任务")
        return

    print(f"父任务 {parent_task_id} 的子任务:")
    for st in sub_tasks:
        status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}
        icon = status_icon.get(st.get("status"), "❓")
        deps = ",".join(st.get("dependencies", []))
        dep_info = f" (依赖: {deps})" if deps else ""
        print(f"  {icon} {st['id']}: {st['name']} [{st.get('status')}]{dep_info}")


def check_parent_complete(project_id, parent_task_id):
    """检查父任务是否所有子任务都已完成。"""
    data = read_data(project_id)

    sub_tasks = [
        t for t in data.get("tasks", [])
        if t.get("parent_task") == parent_task_id
    ]

    if not sub_tasks:
        print(f"父任务 {parent_task_id} 没有子任务，可直接完成")
        print("can_complete=true")
        return

    all_completed = all(st.get("status") == "completed" for st in sub_tasks)

    if all_completed:
        print(f"父任务 {parent_task_id} 的所有子任务已完成")
        print("can_complete=true")
    else:
        pending = [st['id'] for st in sub_tasks if st.get("status") != "completed"]
        print(f"父任务 {parent_task_id} 还有 {len(pending)} 个子任务未完成: {', '.join(pending)}")
        print("can_complete=false")


def update_subtask(project_id, parent_task_id, subtask_id, status):
    """更新子任务状态，状态变更时发送通报"""
    lock_file = get_lock_file(project_id)
    
    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = read_data(project_id)
            now = datetime.now().isoformat()
            
            # 查找父任务
            parent_task = None
            for task in data['tasks']:
                if task['id'] == parent_task_id:
                    parent_task = task
                    break
            
            if not parent_task:
                print(f"Error: Parent task {parent_task_id} not found", file=sys.stderr)
                _fail_data(project_id, "update_subtask_parent_not_found", parent_task_id, subtask_id)
            subtask_found = False
            old_status = None
            agent = None
            for subtask in parent_task.get('subtasks', []):
                if subtask['id'] == subtask_id:
                    old_status = subtask['status']
                    agent = subtask['agent']
                    subtask['status'] = status
                    subtask['updated_at'] = datetime.now().isoformat()
                    
                    # 【关键改进】对于 in_progress 状态：
                    # 1. 先同步发送通知
                    # 2. 通知完成后再记录 started_at
                    if status == 'in_progress' and not subtask.get('started_at'):
                        # 发送通知（同步，等待完成）
                        send_notification(project_id, "subtask_start", agent, parent_task_id, subtask_id, sync=True)
                        
                        # 通知发送完成后，记录真正"开始"的时间
                        now = datetime.now().isoformat()
                        subtask['started_at'] = now
                        
                    elif status == 'completed':
                        subtask['completed_at'] = datetime.now().isoformat()
                        # subtask_complete 同步发送
                        send_notification(project_id, "subtask_complete", agent, parent_task_id, subtask_id, sync=True)
                    
                    subtask_found = True
                    break
            
            if not subtask_found:
                print(f"Error: Subtask {subtask_id} not found in {parent_task_id}", file=sys.stderr)
                _fail_data(project_id, "update_subtask_not_found", subtask_id, parent_task_id)
            
            parent_task['updated_at'] = datetime.now().isoformat()
            data['project']['updated_at'] = datetime.now().isoformat()
            
            write_data(project_id, data)
            
            print(f"Subtask {subtask_id} updated from {old_status} to {status}")

            # 记录子任务状态变更日志
            logger = get_skill_logger(project_id)
            logger.info(f"[SUBTASK_STATUS] subtask_id={subtask_id}, parent={parent_task_id}, from={old_status}, to={status}, agent={agent}", extra={'skill_name': 'PROJECT-DATA'})
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

_TASK_STATUSES = frozenset(
    {"pending", "in_progress", "completed", "failed", "cancelled", "waiting_for_input"}
)


def update_task(project_id, task_id, status):
    """更新任务状态，状态变更时发送通报
    
    关键时序（in_progress 状态）:
    1. 先同步发送通知（等待 Telegram 响应）
    2. 通知发送完成后，记录 started_at（此时才是真正"开始"的时间点）
    3. 写入 JSON 持久化
    4. 返回后，Worker Agent 开始执行实际工作
    
    这确保了：
    - started_at ≈ 通知完成时间 ≈ Worker 即将开始执行的时间
    - 用户收到消息时，任务确实即将开始
    """
    lock_file = get_lock_file(project_id)
    
    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = read_data(project_id)
            if status not in _TASK_STATUSES:
                print(
                    f"Error: 非法状态 '{status}'，允许值: {', '.join(sorted(_TASK_STATUSES))}",
                    file=sys.stderr,
                )
                _fail_data(project_id, "update_task_bad_status", status, task_id)
            
            found = False
            for task in data['tasks']:
                if task['id'] == task_id:
                    found = True
                    old_status = task['status']
                    agent = task['agent']
                    task['updated_at'] = datetime.now().isoformat()
                    
                    # 幂等：已完成再次 completed 不再发通报（避免双份 task_complete）
                    if status == 'completed' and old_status == 'completed':
                        task['status'] = status
                        print(f"Task {task_id} already completed (idempotent noop)")
                        break

                    # 幂等：in_progress 再次 in_progress 不再发通报（避免双份 task_start）
                    if status == 'in_progress' and old_status == 'in_progress':
                        task['status'] = status
                        print(f"Task {task_id} already in_progress (idempotent noop)")
                        break

                    # 幂等：waiting_for_input 再次 waiting_for_input 不再重复释放队列
                    if status == 'waiting_for_input' and old_status == 'waiting_for_input':
                        task['status'] = status
                        print(f"Task {task_id} already waiting_for_input (idempotent noop)")
                        break
                    
                    task['status'] = status
                    
                    # 【关键改进】对于 in_progress 状态：
                    # 1. 先同步发送通知
                    # 2. 通知完成后再记录 started_at
                    if status == 'in_progress' and not task.get('started_at'):
                        # 发送通知（同步，等待完成）
                        send_notification(project_id, "task_start", agent, task_id, sync=True)
                        
                        # 通知发送完成后，记录真正"开始"的时间
                        now = datetime.now().isoformat()
                        task['started_at'] = now
                        data['_last_event'] = 'task_started'
                        
                    elif status == 'completed':
                        task['completed_at'] = datetime.now().isoformat()
                        data['_last_event'] = 'task_completed'
                        # task_complete 同步发送
                        send_notification(project_id, "task_complete", agent, task_id, sync=True)

                    elif status == 'waiting_for_input':
                        task['waiting_since'] = datetime.now().isoformat()
                        data['_last_event'] = 'task_waiting_for_input'
                        # 自动释放队列锁（让其他任务可以执行）
                        corrected_id = normalize_project_id(project_id)
                        queue_file = Path.home() / ".openclaw" / "tasks" / "projects" / corrected_id / ".task_queue"
                        if queue_file.exists():
                            try:
                                queue_file.unlink()
                                print(f"Queue auto-released for task {task_id} (waiting_for_input)")
                            except OSError as e:
                                print(f"Warning: 无法删除队列文件: {e}", file=sys.stderr)

                    break
            if not found:
                print(f"Error: 任务不存在: {task_id}", file=sys.stderr)
                _fail_data(project_id, "update_task_not_found", task_id, status)
            
            data['project']['updated_at'] = datetime.now().isoformat()
            write_data(project_id, data)
            print(f"Task {task_id} updated to {status}")

            # 记录任务状态变更日志
            logger = get_skill_logger(project_id)
            logger.info(f"[TASK_STATUS] task_id={task_id}, from={old_status}, to={status}, agent={agent}", extra={'skill_name': 'PROJECT-DATA'})
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

def confirm_project(project_id):
    """确认项目，此时所有任务已添加完毕，发送 project_start 通报"""
    lock_file = get_lock_file(project_id)
    
    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = read_data(project_id)
            ok_graph, graph_err = validate_tasks_graph(data.get('tasks', []))
            if not ok_graph:
                print(
                    f"Error: 无法 confirm，任务依赖图不合法: {graph_err}",
                    file=sys.stderr,
                )
                _fail_data(project_id, "confirm_invalid_graph", graph_err or "validate_tasks_graph", "")
            now = datetime.now().isoformat()
            
            data['project']['confirmed_by_user'] = True
            data['project']['confirmed_at'] = now
            data['project']['status'] = 'in_progress'
            data['project']['updated_at'] = now
            data['_last_event'] = 'project_confirmed'
            
            write_data(project_id, data)
            
            # 用户确认后发送 project_start 通报
            task_count = len(data['tasks'])
            send_notification(project_id, "project_start", str(task_count))
            
            print(f"Project {project_id} confirmed with {task_count} tasks")

            # 记录项目确认日志
            logger = get_skill_logger(project_id)
            logger.info(f"[PROJECT_CONFIRMED] project={project_id}, tasks={task_count}", extra={'skill_name': 'PROJECT-DATA'})
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

def update_project(project_id, status):
    """更新项目状态（含守卫：completed 须所有任务已完成）"""
    lock_file = get_lock_file(project_id)

    with open(lock_file, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = read_data(project_id)
            now = datetime.now().isoformat()

            # 【守卫】只有所有任务已完成才能设为 completed
            if status == 'completed':
                all_tasks = data.get('tasks', [])
                total = len(all_tasks)
                completed = sum(1 for t in all_tasks if t.get('status') == 'completed')
                if completed < total:
                    print(f"Error: 无法标记项目完成 — 仅 {completed}/{total} 任务已完成", file=sys.stderr)
                    return

            old_status = data['project']['status']
            data['project']['status'] = status
            data['project']['updated_at'] = now

            # 【统一通报规则】状态变更时发送通报
            if old_status != status and status == 'completed':
                data['project']['completed_at'] = now
                # project_complete 异步发送（sync=False），由调用者负责等待
                send_notification(project_id, "project_complete", sync=False)

            write_data(project_id, data)
            print(f"Project {project_id} updated from {old_status} to {status}")

            # 记录项目状态变更日志
            logger = get_skill_logger(project_id)
            logger.info(f"[PROJECT_STATUS] project={project_id}, from={old_status}, to={status}", extra={'skill_name': 'PROJECT-DATA'})
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

# ========== Skill Management ==========

SKILLS_DIR = Path.home() / ".openclaw" / "skills"
REGISTRY_FILE = SKILLS_DIR / "registry.json"

def load_registry():
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"version": "1.0", "skills": []}

def save_registry(registry):
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

def list_skills():
    """列出所有技能"""
    registry = load_registry()
    if not registry.get("skills"):
        print("No skills registered")
        return
    
    print(f"{'ID':<35} {'Name':<15} {'Category':<12} {'Status':<10}")
    print("-" * 75)
    for skill in registry["skills"]:
        status = "✅ enabled" if skill.get("enabled", True) else "❌ disabled"
        print(f"{skill['id']:<35} {skill['name']:<15} {skill['category']:<12} {status:<10}")

def register_skill(skill_id, name, category, path, description):
    """注册新技能"""
    registry = load_registry()
    
    # 检查是否已存在
    for skill in registry["skills"]:
        if skill["id"] == skill_id:
            print(f"Error: Skill {skill_id} already exists", file=sys.stderr)
            _fail_registry("register_skill_duplicate", skill_id, name)
    
    # 验证路径存在
    skill_path = SKILLS_DIR / path
    if not skill_path.exists():
        print(f"Error: Skill file not found: {skill_path}", file=sys.stderr)
        _fail_registry("register_skill_path_missing", str(skill_path), skill_id)
    
    registry["skills"].append({
        "id": skill_id,
        "name": name,
        "category": category,
        "path": path,
        "enabled": True,
        "description": description
    })
    
    save_registry(registry)
    print(f"Skill {skill_id} registered successfully")

def update_skill(skill_id, enabled):
    """启用/禁用技能"""
    registry = load_registry()
    
    found = False
    for skill in registry["skills"]:
        if skill["id"] == skill_id:
            skill["enabled"] = enabled
            found = True
            break
    
    if not found:
        print(f"Error: Skill {skill_id} not found", file=sys.stderr)
        _fail_registry("update_skill_not_found", skill_id, str(enabled))
    
    save_registry(registry)
    status = "enabled" if enabled else "disabled"
    print(f"Skill {skill_id} {status}")

def load_skills_for_project(project_id):
    """为项目加载技能"""
    data = read_data(project_id)
    registry = load_registry()
    
    # 获取可用的技能
    available_skills = [s for s in registry["skills"] if s.get("enabled", True)]
    
    # 将技能信息添加到项目数据
    if "skills" not in data:
        data["skills"] = []
    
    data["skills"] = available_skills
    
    # 保存到项目
    data_file = get_data_file(project_id)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Loaded {len(available_skills)} skills for project {project_id}")

def main():
    parser = argparse.ArgumentParser(description='Project Data Manager')
    subparsers = parser.add_subparsers(dest='command')
    
    # recommend-agent
    p_recommend = subparsers.add_parser('recommend-agent', help='Recommend agent for a task')
    p_recommend.add_argument('task_name', help='Task name')
    p_recommend.add_argument('description', nargs='?', default='', help='Task description')
    
    # check-cycle
    p_cycle = subparsers.add_parser('check-cycle', help='Check for circular dependencies')
    p_cycle.add_argument('project_id', help='Project ID')
    
    # add-task
    p_add = subparsers.add_parser('add-task', help='Add task')
    p_add.add_argument('project_id')
    p_add.add_argument('name')
    p_add.add_argument('agent')
    p_add.add_argument('description', nargs='?', default='')
    p_add.add_argument('dependencies', nargs='?', default='')
    p_add.add_argument('priority', nargs='?', type=int, default=None, help='Priority (lower number = higher priority)')
    p_add.add_argument('preemptible', nargs='?', default='true', help='Can be preempted (true/false)')
    p_add.add_argument('timeout', nargs='?', type=int, default=None, help='Timeout in minutes')
    p_add.add_argument('max_retries', nargs='?', type=int, default=None, help='Max retry count (0 = no retry)')
    p_add.add_argument('--task-id', default=None, help='Custom task ID (auto-generated if not provided)')
    p_add.add_argument('--parent', default=None, help='Parent task ID (for subtasks)')
    p_add.add_argument('--task-type', default='', help='Task type for quality gate (code-deliverable/test-plan/prd/etc)')
    p_add.add_argument('--reviewer', default='', help='Reviewer agent ID for cross-review')
    
    # add-subtask
    p_sub = subparsers.add_parser('add-subtask', help='Add subtask to parent task')
    p_sub.add_argument('project_id', help='Project ID')
    p_sub.add_argument('parent_task_id', help='Parent task ID')
    p_sub.add_argument('name', help='Subtask name')
    p_sub.add_argument('agent', help='Agent ID')
    p_sub.add_argument('description', nargs='?', default='', help='Subtask description')
    
    # update-subtask
    p_upd_sub = subparsers.add_parser('update-subtask', help='Update subtask status')
    p_upd_sub.add_argument('project_id', help='Project ID')
    p_upd_sub.add_argument('parent_task_id', help='Parent task ID')
    p_upd_sub.add_argument('subtask_id', help='Subtask ID')
    p_upd_sub.add_argument('status', help='New status')
    
    # update-task
    p_upd = subparsers.add_parser('update-task', help='Update task status')
    p_upd.add_argument('project_id')
    p_upd.add_argument('task_id')
    p_upd.add_argument('status')
    
    # update-my-task（从 trigger 文件自动读取任务信息）
    p_my_task = subparsers.add_parser('update-my-task', help='Update current task status (auto-read from trigger)')
    p_my_task.add_argument('status', help='New status (in_progress/completed)')
    
    # add-my-subtask（为当前任务添加子任务）
    p_my_sub = subparsers.add_parser('add-my-subtask', help='Add subtask to current task (auto-read from trigger)')
    p_my_sub.add_argument('name', help='Subtask name')
    p_my_sub.add_argument('agent', help='Agent ID')
    p_my_sub.add_argument('description', nargs='?', default='', help='Subtask description')
    
    # update-my-subtask（更新当前任务的子任务）
    p_my_sub_upd = subparsers.add_parser('update-my-subtask', help='Update subtask of current task (auto-read from trigger)')
    p_my_sub_upd.add_argument('subtask_id', help='Subtask ID')
    p_my_sub_upd.add_argument('status', help='New status')
    
    # list-subtasks
    p_list_sub = subparsers.add_parser('list-subtasks', help='List all subtasks of a parent task')
    p_list_sub.add_argument('project_id', help='Project ID')
    p_list_sub.add_argument('parent_task_id', help='Parent task ID')

    # check-parent-complete
    p_check_parent = subparsers.add_parser('check-parent-complete', help='Check if all subtasks of a parent task are complete')
    p_check_parent.add_argument('project_id', help='Project ID')
    p_check_parent.add_argument('parent_task_id', help='Parent task ID')

    # get-my-task（获取当前任务信息）
    p_my_task_get = subparsers.add_parser('get-my-task', help='Get current task info (auto-read from trigger)')
    
    # confirm
    p_con = subparsers.add_parser('confirm', help='Confirm project')
    p_con.add_argument('project_id')
    
    # update-project
    p_upd_proj = subparsers.add_parser('update-project', help='Update project status')
    p_upd_proj.add_argument('project_id', help='Project ID')
    p_upd_proj.add_argument('status', help='New status (e.g., completed)')
    
    # list-skills
    p_list_skills = subparsers.add_parser('list-skills', help='List all registered skills')
    
    # register-skill
    p_reg = subparsers.add_parser('register-skill', help='Register a new skill')
    p_reg.add_argument('skill_id', help='Skill ID')
    p_reg.add_argument('name', help='Skill name')
    p_reg.add_argument('category', help='Category (research/product/developer/etc)')
    p_reg.add_argument('path', help='Path to SKILL.md relative to skills dir')
    p_reg.add_argument('description', help='Skill description')
    
    # update-skill
    p_skill = subparsers.add_parser('update-skill', help='Enable/disable a skill')
    p_skill.add_argument('skill_id', help='Skill ID')
    p_skill.add_argument('enabled', help='true or false')
    
    # load-skills
    p_load = subparsers.add_parser('load-skills', help='Load skills for a project')
    p_load.add_argument('project_id', help='Project ID')
    
    args = parser.parse_args()
    
    if args.command == 'recommend-agent':
        agent = recommend_agent(args.task_name, args.description)
        print(agent)
    elif args.command == 'check-cycle':
        data = read_data(args.project_id)
        ok, msg = validate_tasks_graph(data.get("tasks", []))
        if ok:
            print("✅ 任务依赖图为合法 DAG（无未知依赖、无自依赖、无环）")
        else:
            print(f"Error: {msg}", file=sys.stderr)
            _fail_data(args.project_id, "check_cycle_cli_failed", msg or "validate_tasks_graph", "")
    elif args.command == 'add-task':
        assert_agent_allowed("project-data")
        preemptible = args.preemptible.lower() in ('true', '1', 'yes')
        add_task(args.project_id, args.name, args.agent, args.description, args.dependencies, args.priority, preemptible, args.timeout, args.max_retries, parent=args.parent, task_id=args.task_id, task_type=args.task_type, reviewer=args.reviewer)
    elif args.command == 'add-subtask':
        assert_agent_allowed("project-data")
        add_subtask(args.project_id, args.parent_task_id, args.name, args.agent, args.description)
    elif args.command == 'list-subtasks':
        assert_agent_allowed("project-data")
        list_subtasks(args.project_id, args.parent_task_id)
    elif args.command == 'check-parent-complete':
        assert_agent_allowed("project-data")
        check_parent_complete(args.project_id, args.parent_task_id)
    elif args.command == 'update-subtask':
        assert_agent_allowed("project-data")
        update_subtask(args.project_id, args.parent_task_id, args.subtask_id, args.status)
    elif args.command == 'update-task':
        assert_agent_allowed("project-data")
        update_task(args.project_id, args.task_id, args.status)
    elif args.command == 'update-my-task':
        # 从 trigger 文件读取任务信息
        project_id, task_id = get_current_task_from_trigger()
        if not project_id or not task_id:
            _fail_data(
                project_id or "",
                "update_my_task_no_trigger",
                "missing project_id or task_id from trigger",
                args.command,
            )
        # 验证权限
        is_owner, task = verify_task_owner(project_id, task_id)
        if not is_owner:
            _fail_data(
                project_id,
                "update_my_task_not_owner",
                f"task_id={task_id}",
                os.environ.get("OPENCODE_AGENT_ID") or "",
            )
        # 执行更新
        update_task(project_id, task_id, args.status)
    elif args.command == 'add-my-subtask':
        # 从 trigger 文件读取任务信息
        project_id, task_id = get_current_task_from_trigger()
        if not project_id or not task_id:
            _fail_data(
                project_id or "",
                "add_my_subtask_no_trigger",
                "missing project_id or task_id from trigger",
                args.command,
            )
        # 验证权限
        is_owner, task = verify_task_owner(project_id, task_id)
        if not is_owner:
            _fail_data(
                project_id,
                "add_my_subtask_not_owner",
                f"task_id={task_id}",
                os.environ.get("OPENCODE_AGENT_ID") or "",
            )
        # 添加子任务
        add_subtask(project_id, task_id, args.name, args.agent, args.description or '')
    elif args.command == 'update-my-subtask':
        # 从 trigger 文件读取任务信息
        project_id, task_id = get_current_task_from_trigger()
        if not project_id or not task_id:
            _fail_data(
                project_id or "",
                "update_my_subtask_no_trigger",
                "missing project_id or task_id from trigger",
                args.command,
            )
        # 验证权限
        is_owner, task = verify_task_owner(project_id, task_id)
        if not is_owner:
            _fail_data(
                project_id,
                "update_my_subtask_not_owner",
                f"task_id={task_id}",
                os.environ.get("OPENCODE_AGENT_ID") or "",
            )
        # 更新子任务
        update_subtask(project_id, task_id, args.subtask_id, args.status)
    elif args.command == 'get-my-task':
        # 从 trigger 文件读取任务信息
        project_id, task_id = get_current_task_from_trigger()
        if not project_id or not task_id:
            _fail_data(
                project_id or "",
                "get_my_task_no_trigger",
                "missing project_id or task_id from trigger",
                args.command,
            )
        # 验证权限
        is_owner, task = verify_task_owner(project_id, task_id)
        if not is_owner:
            _fail_data(
                project_id,
                "get_my_task_not_owner",
                f"task_id={task_id}",
                os.environ.get("OPENCODE_AGENT_ID") or "",
            )
        # 输出任务信息
        import json
        print(json.dumps(task, ensure_ascii=False, indent=2))
    elif args.command == 'confirm':
        confirm_project(args.project_id)
    elif args.command == 'update-project':
        update_project(args.project_id, args.status)
    elif args.command == 'list-skills':
        list_skills()
    elif args.command == 'register-skill':
        register_skill(args.skill_id, args.name, args.category, args.path, args.description)
    elif args.command == 'update-skill':
        update_skill(args.skill_id, args.enabled.lower() == 'true')
    elif args.command == 'load-skills':
        load_skills_for_project(args.project_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
