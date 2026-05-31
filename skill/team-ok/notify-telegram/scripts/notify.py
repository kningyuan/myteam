#!/usr/bin/env python3
"""
Notify Telegram Skill - 发送 Telegram 通知
统一通报格式：任务状态、项目、任务、子任务、负责人、成果物
"""

import html
import json
import logging
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.config import TELEGRAM_MAX_RETRIES, TELEGRAM_CURL_TIMEOUT
from common.logger import get_skill_logger, log_skill_step_failure

# Agent ID 到 bot 名称的映射
AGENT_BOT_MAP = {
    'main': 'redmacmainbot',
    'product': 'redmacproductbot',
    'developer': 'redcode1bot',
    'designer': 'redmain1bot',
    'researcher': 'redmac_researcher_bot',
    'content': 'redmac_content_bot',
    'social': 'redmac_social_bot',
    'seo': 'redmacanalystbot',
    'email': 'redwrite1bot',
    'docs': 'redstorm1bot',
    'ops': 'redmacopsbot',
    'ops2': 'redops1bot',
    'consultation': 'redmacConsultationbot',
    'coordinator': 'redmaccoordinatorbot',
    'deputy': 'redmacdeputybot',
    'tester': 'redmactestbot',
}

AGENT_NAME_MAP = {
    'main': '项目协调专家',
    'product': '产品经理',
    'developer': '开发工程师',
    'designer': 'UI设计师',
    'researcher': '调研专家',
    'content': '内容创作者',
    'social': '社交媒体运营',
    'seo': 'SEO优化师',
    'email': '邮件营销专家',
    'docs': '技术文档工程师',
    'ops': '运维工程师',
    'ops2': '运维工程师',
    'consultation': '咨询顾问',
    'coordinator': '合规审查员',
    'analyst': '数据分析师',
    'tester': '测试工程师',
    'deputy': '项目副手'
}

# 统一目标群组
TARGET_GROUP = '-1003735246121'

def get_bot_token(bot_name):
    """从 openclaw.json 读取 Bot Token"""
    try:
        openclaw_config = Path.home() / ".openclaw/openclaw.json"
        with open(openclaw_config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 从 channels.telegram.accounts 中获取 token
        accounts = config.get('channels', {}).get('telegram', {}).get('accounts', {})
        account = accounts.get(bot_name, {})
        token = account.get('botToken')
        
        if token:
            return token
        else:
            print(f"Warning: Bot token not found for {bot_name}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Error reading bot token: {e}", file=sys.stderr)
        return None

def get_project_data(project_id):
    """读取项目数据"""
    project_file = Path.home() / f".openclaw/tasks/projects/{project_id}/task_data.json"
    if not project_file.exists():
        return None
    with open(project_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_task_info(project_data, task_id):
    """获取任务信息"""
    if not project_data:
        return None
    for task in project_data.get('tasks', []):
        if task['id'] == task_id:
            return task
    return None

def get_subtask_info(task_data, subtask_id):
    """获取子任务信息"""
    if not task_data:
        return None
    for subtask in task_data.get('subtasks', []):
        if subtask['id'] == subtask_id:
            return subtask
    return None

def get_deliverables(project_id, task_id):
    """获取任务成果物"""
    deliverables_dir = Path.home() / f".openclaw/tasks/projects/{project_id}/deliverables"
    if not deliverables_dir.exists():
        return []
    
    files = []
    for f in deliverables_dir.glob(f"{task_id}*.md"):
        files.append(f.name)
    for f in deliverables_dir.glob(f"{task_id}_*.md"):
        if f.name not in files:
            files.append(f.name)
    return sorted(files)

def format_notification(status, project_name, task_name, agent_name, 
                       subtask_name=None, deliverables=None, extra_info=None):
    """统一通报格式"""
    lines = [f"📋 {status}"]
    lines.append(f"📁 项目：{project_name}")
    lines.append(f"📝 任务：{task_name}")
    
    if subtask_name:
        lines.append(f"📎 子任务：{subtask_name}")
    
    lines.append(f"👤 负责人：{agent_name}")
    
    if deliverables:
        lines.append(f"📦 成果物：")
        for d in deliverables[:5]:
            lines.append(f"  • {d}")
        if len(deliverables) > 5:
            lines.append(f"  ... 等共 {len(deliverables)} 个文件")
    
    if extra_info:
        lines.append(f"💡 {extra_info}")
    
    return "\n".join(lines)

def send_to_telegram(bot_name, message, project_id="", event_type="", max_retries=TELEGRAM_MAX_RETRIES):
    """发送消息到 Telegram（带重试机制）"""
    bot_token = get_bot_token(bot_name)
    if not bot_token:
        print(f"Error: Cannot get bot token for {bot_name}", file=sys.stderr)
        return False
    
    encoded_message = urllib.parse.quote(html.escape(message))
    
    cmd = [
        'curl', '-s', '-X', 'POST',
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        '-d', f'chat_id={TARGET_GROUP}',
        '-d', f'text={encoded_message}',
        '-d', 'parse_mode=HTML'
    ]
    
    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=TELEGRAM_CURL_TIMEOUT)
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if response.get('ok'):
                        if attempt > 0:
                            print(f"✅ Message sent successfully via {bot_name} (retry #{attempt})")
                        else:
                            print(f"✅ Message sent successfully via {bot_name}")
                        
                        # 记录到项目 Skill 日志
                        try:
                            skill_logger = get_skill_logger(project_id)
                            skill_logger.info(f"[TELEGRAM_SENT] bot={bot_name}, event={event_type}, attempt={attempt+1}", 
                                            extra={'skill_name': 'NOTIFY'})
                        except Exception:
                            pass  # 忽略项目日志记录失败
                        
                        return True
                    else:
                        error_desc = response.get('description', 'Unknown error')
                        print(f"❌ Telegram API error (attempt {attempt + 1}/{max_retries + 1}): {error_desc}", file=sys.stderr)
                        if 'retry after' in error_desc.lower():
                            import time
                            retry_seconds = 5
                            try:
                                retry_seconds = int(error_desc.split('retry after')[1].split()[0])
                            except:
                                pass
                            print(f"⏳ Rate limited, waiting {retry_seconds}s before retry...")
                            time.sleep(retry_seconds)
                            continue
                        return False
                except json.JSONDecodeError:
                    print(f"⚠️ Could not parse response (attempt {attempt + 1}/{max_retries + 1}): {result.stdout[:200]}", file=sys.stderr)
                    if attempt < max_retries:
                        import time
                        time.sleep(2 ** attempt)
                        continue
                    return False
            else:
                print(f"❌ curl failed (attempt {attempt + 1}/{max_retries + 1}): {result.stderr[:200]}", file=sys.stderr)
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                return False
        except subprocess.TimeoutExpired:
            print(f"⏱️ Timeout (attempt {attempt + 1}/{max_retries + 1}), retrying...", file=sys.stderr)
            if attempt < max_retries:
                import time
                time.sleep(2 ** attempt)
                continue
            return False
        except Exception as e:
            print(f"❌ Error sending message (attempt {attempt + 1}/{max_retries + 1}): {e}", file=sys.stderr)
            if attempt < max_retries:
                import time
                time.sleep(2 ** attempt)
                continue
            return False
    
    print(f"❌ Failed after {max_retries + 1} attempts", file=sys.stderr)
    return False

def notify_task_created(project_id, agent_id, task_id):
    """任务创建通知"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    
    if not data or not task:
        return False
    
    project_name = data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    
    message = format_notification(
        status="📝 任务创建",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
        extra_info="任务已创建，等待执行"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)

def notify_task_start(project_id, agent_id, task_id):
    """任务开始通知"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    
    if not data or not task:
        return False
    
    project_name = data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    
    message = format_notification(
        status="🚀 任务开始",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
        extra_info="任务已开始执行"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)

def notify_task_complete(project_id, agent_id, task_id):
    """任务完成通知"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    
    if not data or not task:
        return False
    
    project_name = data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    deliverables = get_deliverables(project_id, task_id)
    
    message = format_notification(
        status="✅ 任务完成",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
        deliverables=deliverables if deliverables else None,
        extra_info="任务已执行完毕"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)


def notify_subtask_created(project_id, agent_id, parent_task_id, subtask_id):
    """子任务创建通知"""
    data = get_project_data(project_id)
    parent_task = get_task_info(data, parent_task_id)
    subtask = get_subtask_info(parent_task, subtask_id) if parent_task else None
    
    if not data or not parent_task or not subtask:
        return False
    
    project_name = data['project']['name']
    parent_name = parent_task['name']
    subtask_name = subtask['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    
    message = format_notification(
        status="📝 子任务创建",
        project_name=project_name,
        task_name=parent_name,
        subtask_name=subtask_name,
        agent_name=agent_name,
        extra_info="子任务已创建，等待执行"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)

def notify_subtask_start(project_id, agent_id, parent_task_id, subtask_id):
    """子任务开始通知"""
    data = get_project_data(project_id)
    parent_task = get_task_info(data, parent_task_id)
    subtask = get_subtask_info(parent_task, subtask_id) if parent_task else None
    
    if not data or not parent_task or not subtask:
        return False
    
    project_name = data['project']['name']
    parent_name = parent_task['name']
    subtask_name = subtask['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    
    message = format_notification(
        status="🚀 子任务开始",
        project_name=project_name,
        task_name=parent_name,
        subtask_name=subtask_name,
        agent_name=agent_name,
        extra_info="子任务开始执行"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)

def notify_subtask_complete(project_id, agent_id, parent_task_id, subtask_id):
    """子任务完成通知"""
    data = get_project_data(project_id)
    parent_task = get_task_info(data, parent_task_id)
    subtask = get_subtask_info(parent_task, subtask_id) if parent_task else None
    
    if not data or not parent_task or not subtask:
        return False
    
    project_name = data['project']['name']
    parent_name = parent_task['name']
    subtask_name = subtask['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    
    message = format_notification(
        status="✅ 子任务完成",
        project_name=project_name,
        task_name=parent_name,
        subtask_name=subtask_name,
        agent_name=agent_name,
        extra_info="子任务执行完毕"
    )
    
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message)

def notify_task_split(project_id, agent_id, task_id, sub_count):
    """任务拆分通知"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    if not data or not task:
        return False
    project_name = data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)

    message = format_notification(
        status="📋 任务拆分",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
        extra_info=f"已拆分为 {sub_count} 个子任务"
    )
    return send_to_telegram(AGENT_BOT_MAP.get(agent_id, 'redmacmainbot'), message, project_id=project_id, event_type="task_split")


def notify_task_failed(project_id, agent_id, task_id, progress=None):
    """任务失败通知"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    if not data or not task:
        return False
    project_name = data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)

    extra = "任务执行失败"
    if progress:
        extra += f"（{progress}）"
    message = format_notification(
        status="❌ 任务失败",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
        extra_info=extra
    )
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message, project_id=project_id, event_type="task_failed")


def notify_subtask_failed(project_id, agent_id, parent_task_id, subtask_id, progress=None):
    """子任务失败通知"""
    data = get_project_data(project_id)
    parent_task = get_task_info(data, parent_task_id)
    subtask = get_subtask_info(parent_task, subtask_id) if parent_task else None
    if not data or not parent_task or not subtask:
        return False
    project_name = data['project']['name']
    parent_name = parent_task['name']
    subtask_name = subtask['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)

    extra = "子任务执行失败"
    if progress:
        extra += f"（{progress}）"
    message = format_notification(
        status="❌ 子任务失败",
        project_name=project_name,
        task_name=parent_name,
        subtask_name=subtask_name,
        agent_name=agent_name,
        extra_info=extra
    )
    bot_name = AGENT_BOT_MAP.get(agent_id, 'redmacmainbot')
    return send_to_telegram(bot_name, message, project_id=project_id, event_type="subtask_failed")


def notify_group_message(project_id, message):
    """发送群通报（通用消息）。"""
    project_data = get_project_data(project_id)
    project_name = project_data.get('project', {}).get('name', project_id) if project_data else project_id

    formatted_message = f"🤖 团队协作通知\n\n{message}\n\n📁 项目：{project_name}"
    return send_to_telegram(AGENT_BOT_MAP['main'], formatted_message, project_id=project_id, event_type="group_notify")


def notify_task_retry(project_id, agent_id, task_id, feedback=""):
    """通知任务因质量门禁未通过需要重试。"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    task_name = task['name'] if task else task_id
    project_name = data['project']['name'] if data else project_id

    if feedback:
        # 解析详细失败项，格式化展示
        lines = ["🔄 任务重试（质量门禁未通过）\n"]
        lines.append(f"📌 项目：{project_name}")
        lines.append(f"📌 任务：{task_name} ({task_id})")
        lines.append(f"📌 执行 Agent：{agent_id or '未指定'}")
        lines.append("")
        lines.append("🔍 具体问题：")
        # 按规则类型分组展示
        rule_descriptions = {
            "required_sections": "缺少必需章节",
            "must_include": "缺少必需关键词",
            "min_length": "内容长度不足",
            "section_level": "章节标题层级错误",
            "file_exists": "引用的文件不存在",
        }
        for line in feedback.strip().split("\n"):
            if line.startswith("❌ ["):
                # 解析 ❌ [rule] 期望：xxx，实际：xxx
                import re
                match = re.match(r"❌ \[(\w+)\]\s*期望：(.+?)，实际：(.+)", line)
                if match:
                    rule = match.group(1)
                    expected = match.group(2)
                    actual = match.group(3)
                    rule_label = rule_descriptions.get(rule, rule)
                    lines.append(f"  ❌ {rule_label}：期望「{expected}」，实际「{actual}」")
                else:
                    lines.append(f"  {line}")
            elif line.strip() and not line.startswith("你的任务") and not line.startswith("未通过的规则") and not line.startswith("请针对"):
                lines.append(line)
        message = "\n".join(lines)
    else:
        message = (
            f"🔄 任务重试\n"
            f"项目：{project_name}\n"
            f"任务：{task_name} ({task_id})\n"
            f"原因：质量门禁未通过\n"
            f"反馈：请检查交付物质量"
        )

    return send_to_telegram(AGENT_BOT_MAP.get(agent_id, 'redmacmainbot'), message,
                            project_id=project_id, event_type="task_retry")


def notify_quality_gate_passed(project_id, agent_id, task_id):
    """质量门禁通过通知。"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    if not data or not task:
        return False
    task_name = task['name']
    project_name = data['project']['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)
    message = format_notification(
        status="✅ 质量门禁通过",
        project_name=project_name,
        task_name=task_name,
        agent_name=agent_name,
    )
    return send_to_telegram(AGENT_BOT_MAP.get(agent_id, 'redmacmainbot'), message,
                            project_id=project_id, event_type="quality_gate_passed")


def notify_review_passed(project_id, reviewer, task_id):
    """交叉审核通过通知（由审核者发送）。"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    if not data or not task:
        return False
    task_name = task['name']
    project_name = data['project']['name']
    reviewer_name = AGENT_NAME_MAP.get(reviewer, reviewer)
    message = format_notification(
        status="✅ 审核通过",
        project_name=project_name,
        task_name=task_name,
        agent_name=reviewer_name,
    )
    return send_to_telegram(AGENT_BOT_MAP.get(reviewer, 'redmacmainbot'), message,
                            project_id=project_id, event_type="review_passed")


def notify_quality_gate_failed(project_id, task_id):
    """通知质量门禁重试耗尽，需要人工审核。"""
    data = get_project_data(project_id)
    task = get_task_info(data, task_id)
    task_name = task['name'] if task else task_id
    project_name = data['project']['name'] if data else project_id
    message = (
        f"⚠️ 质量门禁重试耗尽\n"
        f"项目：{project_name}\n"
        f"任务：{task_name} ({task_id})\n"
        f"状态：需要人工审核（needs_review）"
    )
    return send_to_telegram(AGENT_BOT_MAP['main'], message,
                            project_id=project_id, event_type="quality_gate_failed")


def notify_project_start(project_id, task_count):
    """项目开始通知（Main Agent 调用）"""
    data = get_project_data(project_id)
    if not data:
        return False
    
    project_name = data['project']['name']
    agent_name = AGENT_NAME_MAP.get('main', '项目协调专家')
    
    message = format_notification(
        status="🎬 项目启动",
        project_name=project_name,
        task_name="项目初始化完成",
        agent_name=agent_name,
        extra_info=f"共 {task_count} 个任务，用户已确认，开始执行"
    )
    
    return send_to_telegram(AGENT_BOT_MAP['main'], message)

def notify_project_complete(project_id):
    """项目完成通知（Main Agent 调用）"""
    data = get_project_data(project_id)
    if not data:
        return False
    
    project_name = data['project']['name']
    agent_name = AGENT_NAME_MAP.get('main', '项目协调专家')
    
    # 统计完成情况
    tasks = data.get('tasks', [])
    completed = sum(1 for t in tasks if t.get('status') == 'completed')
    total = len(tasks)
    
    # 获取所有成果物
    deliverables_dir = Path.home() / f".openclaw/tasks/projects/{project_id}/deliverables"
    all_deliverables = []
    if deliverables_dir.exists():
        all_deliverables = [f.name for f in deliverables_dir.glob("*.md")]
    
    message = format_notification(
        status="🎉 项目完成",
        project_name=project_name,
        task_name=f"所有任务执行完毕 ({completed}/{total})",
        agent_name=agent_name,
        deliverables=all_deliverables if all_deliverables else None,
        extra_info="项目已成功交付"
    )
    
    return send_to_telegram(AGENT_BOT_MAP['main'], message)

def main():
    if len(sys.argv) < 3:
        print("Usage: notify.py <project_id> <event_type> [agent_id] [task_id] [subtask_id]")
        print("\nEvents:")
        print("  task_created <project_id> <agent_id> <task_id>")
        print("  task_start <project_id> <agent_id> <task_id>")
        print("  task_complete <project_id> <agent_id> <task_id>")
        print("  subtask_created <project_id> <agent_id> <parent_task_id> <subtask_id>")
        print("  subtask_start <project_id> <agent_id> <parent_task_id> <subtask_id>")
        print("  subtask_complete <project_id> <agent_id> <parent_task_id> <subtask_id>")
        print("  subtask_failed <project_id> <agent_id> <parent_task_id> <subtask_id> [progress]")
        print("  task_failed <project_id> <agent_id> <task_id> [progress]")
        print("  task_split <project_id> <agent_id> <task_id> <sub_count>")
        print("  project_start <project_id> <task_count>")
        print("  project_complete <project_id>")
        log_skill_step_failure(
            "TELEGRAM_NOTIFY_CLI",
            "TELEGRAM_NOTIFY",
            "usage_missing_args",
            "need project_id and event_type",
            "",
        )
        sys.exit(1)
    
    project_id = sys.argv[1]
    event_type = sys.argv[2]
    
    if event_type == 'task_created':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> task_created <agent_id> <task_id>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_task_created",
                "missing agent_id or task_id",
                "",
            )
            sys.exit(1)
        success = notify_task_created(project_id, sys.argv[3], sys.argv[4])
    
    elif event_type == 'task_start':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> task_start <agent_id> <task_id>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_task_start",
                "missing agent_id or task_id",
                "",
            )
            sys.exit(1)
        success = notify_task_start(project_id, sys.argv[3], sys.argv[4])
    
    elif event_type == 'task_complete':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> task_complete <agent_id> <task_id>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_task_complete",
                "missing agent_id or task_id",
                "",
            )
            sys.exit(1)
        success = notify_task_complete(project_id, sys.argv[3], sys.argv[4])

    elif event_type == 'task_retry':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> task_retry <agent_id> <task_id>")
            sys.exit(1)
        feedback = sys.argv[5] if len(sys.argv) > 5 else ""
        success = notify_task_retry(project_id, sys.argv[3], sys.argv[4], feedback)

    elif event_type == 'quality_gate_failed':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> quality_gate_failed <agent_id> <task_id>")
            sys.exit(1)
        success = notify_quality_gate_failed(project_id, sys.argv[4])

    elif event_type == 'subtask_created':
        agent_id = sys.argv[3]
        parent_task_id = sys.argv[4]
        subtask_id = sys.argv[5]
        success = notify_subtask_created(project_id, agent_id, parent_task_id, subtask_id)
    
    elif event_type == 'subtask_start':
        agent_id = sys.argv[3]
        parent_task_id = sys.argv[4]
        subtask_id = sys.argv[5]
        success = notify_subtask_start(project_id, agent_id, parent_task_id, subtask_id)
        
    elif event_type == 'subtask_complete':
        if len(sys.argv) < 6:
            print("Usage: notify.py <project_id> subtask_complete <agent_id> <parent_task_id> <subtask_id>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_subtask_complete",
                "missing args",
                "",
            )
            sys.exit(1)
        success = notify_subtask_complete(project_id, sys.argv[3], sys.argv[4], sys.argv[5])
    
    elif event_type == 'subtask_failed':
        if len(sys.argv) < 6:
            print("Usage: notify.py <project_id> subtask_failed <agent_id> <parent_task_id> <subtask_id> [progress]")
            sys.exit(1)
        progress = sys.argv[6] if len(sys.argv) > 6 else None
        success = notify_subtask_failed(project_id, sys.argv[3], sys.argv[4], sys.argv[5], progress)
    
    elif event_type == 'task_failed':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> task_failed <agent_id> <task_id> [progress]")
            sys.exit(1)
        progress = sys.argv[5] if len(sys.argv) > 5 else None
        success = notify_task_failed(project_id, sys.argv[3], sys.argv[4], progress)
    
    elif event_type == 'task_split':
        if len(sys.argv) < 6:
            print("Usage: notify.py <project_id> task_split <agent_id> <task_id> <sub_count>")
            sys.exit(1)
        success = notify_task_split(project_id, sys.argv[3], sys.argv[4], int(sys.argv[5]))
    
    elif event_type == 'project_start':
        if len(sys.argv) < 4:
            print("Usage: notify.py <project_id> project_start <task_count>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_project_start",
                "missing task_count",
                "",
            )
            sys.exit(1)
        success = notify_project_start(project_id, int(sys.argv[3]))
    
    elif event_type == 'project_complete':
        success = notify_project_complete(project_id)

    elif event_type == 'group_notify':
        if len(sys.argv) < 4:
            print("Usage: notify.py <project_id> group_notify <message>")
            log_skill_step_failure(
                project_id,
                "TELEGRAM_NOTIFY",
                "usage_group_notify",
                "missing message",
                "",
            )
            sys.exit(1)
        success = notify_group_message(project_id, sys.argv[3])

    elif event_type == 'quality_gate_passed':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> quality_gate_passed <agent_id> <task_id>")
            sys.exit(1)
        success = notify_quality_gate_passed(project_id, sys.argv[3], sys.argv[4])

    elif event_type == 'review_passed':
        if len(sys.argv) < 5:
            print("Usage: notify.py <project_id> review_passed <reviewer> <task_id>")
            sys.exit(1)
        success = notify_review_passed(project_id, sys.argv[3], sys.argv[4])

    else:
        print(f"Unknown event type: {event_type}")
        log_skill_step_failure(
            project_id,
            "TELEGRAM_NOTIFY",
            "unknown_event_type",
            event_type,
            "",
        )
        sys.exit(1)
    
    if success:
        print(f"✅ Notification sent: {event_type}")
        sys.exit(0)
    else:
        print(f"❌ Failed to send notification: {event_type}", file=sys.stderr)
        log_skill_step_failure(
            project_id,
            "TELEGRAM_NOTIFY",
            "send_failed",
            event_type,
            "",
        )
        sys.exit(1)

if __name__ == '__main__':
    main()
