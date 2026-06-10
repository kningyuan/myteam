"""项目进度通报格式 — 与 notify-telegram 统一（myteam 项目群 / Telegram 共用模板）。"""

from __future__ import annotations

from typing import Optional

AGENT_NAME_MAP = {
    "main": "项目协调专家",
    "product": "产品经理",
    "developer": "开发工程师",
    "designer": "UI设计师",
    "research": "研究员",
    "researcher": "研究员",  # 废弃 id，展示兼容
    "content": "内容创作者",
    "social": "社交媒体运营",
    "seo": "SEO优化师",
    "email": "邮件营销专家",
    "docs": "技术文档工程师",
    "ops": "运维工程师",
    "consultation": "咨询顾问",
    "coordinator": "合规审查员",
    "tester": "测试工程师",
    "deputy": "项目副手",
}

EVENT_STATUS = {
    "project_start": "🚀 项目开始",
    "project_complete": "🎉 项目完成",
    "task_start": "🚀 任务开始",
    "task_complete": "✅ 任务完成",
    "task_failed": "❌ 任务失败",
    "task_retry": "🔄 任务重试",
    "task_split": "📋 任务拆分",
    "subtask_created": "➕ 子任务创建",
    "subtask_start": "📝 子任务开始",
    "subtask_complete": "✓ 子任务完成",
    "subtask_failed": "⚠️ 子任务失败",
    "quality_gate_failed": "🚫 质量门禁未通过",
    "quality_gate_passed": "✔️ 质量门禁通过",
    "review_passed": "👍 审核通过",
    "group_notify": "📢 协作通知",
}


def agent_display_name(agent_id: str) -> str:
    if not agent_id:
        return ""
    return AGENT_NAME_MAP.get(agent_id, agent_id)


def format_project_notification(
    status: str,
    project_name: str,
    task_name: str = "",
    agent_id: str = "",
    *,
    subtask_name: str = "",
    deliverables: Optional[list[str]] = None,
    extra_info: str = "",
    task_id: str = "",
) -> str:
    """统一多行通报（原 notify-telegram format_notification）。"""
    lines = [f"📋 {status}"]
    lines.append(f"📁 项目：{project_name}")
    if task_name or task_id:
        label = task_name or task_id
        if task_id and task_name and task_id not in task_name:
            label = f"{task_name} ({task_id})"
        lines.append(f"📝 任务：{label}")
    if subtask_name:
        lines.append(f"📎 子任务：{subtask_name}")
    if agent_id:
        lines.append(f"👤 负责人：{agent_display_name(agent_id)}")
    if deliverables:
        lines.append("📦 成果物：")
        for d in deliverables[:5]:
            lines.append(f"  • {d}")
        if len(deliverables) > 5:
            lines.append(f"  ... 等共 {len(deliverables)} 个文件")
    if extra_info:
        lines.append(f"💡 {extra_info}")
    return "\n".join(lines)


def format_event_message(
    event_type: str,
    project_name: str,
    *,
    agent_id: str = "",
    task_id: str = "",
    task_name: str = "",
    subtask_name: str = "",
    deliverables: Optional[list[str]] = None,
    extra: str = "",
) -> str:
    status = EVENT_STATUS.get(event_type, event_type)
    extra_info = extra.strip() if extra else ""
    if event_type == "task_start" and not extra_info:
        extra_info = "任务已开始执行"
    elif event_type == "task_complete" and not extra_info:
        extra_info = "任务已执行完毕"
    return format_project_notification(
        status,
        project_name,
        task_name=task_name,
        agent_id=agent_id,
        subtask_name=subtask_name,
        deliverables=deliverables,
        extra_info=extra_info,
        task_id=task_id,
    )
