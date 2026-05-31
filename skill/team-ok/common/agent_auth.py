"""Agent 角色权限验证模块

用于在 Team Skill 脚本中强制执行角色边界：
- Main Agent（OPENCODE_AGENT_ID=main）可以调用所有脚本
- Worker Agent（OPENCODE_AGENT_ID=其他值）禁止调用 project-init、task-dispatch、task-queue
- CLI 模式（OPENCODE_AGENT_ID 未设置）允许所有操作
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Main 专属脚本列表（Worker 禁止调用）
MAIN_ONLY_SCRIPTS = {
    "project-init",
    "task-dispatch",
    "task-queue",
}

# Worker 允许的脚本列表
WORKER_ALLOWED_SCRIPTS = {
    "project-data",
}


def get_current_agent_id() -> str | None:
    """获取当前 Agent ID（环境变量），None 表示 CLI 模式"""
    return os.environ.get("OPENCODE_AGENT_ID")


def is_cli_mode() -> bool:
    """是否 CLI 模式（非 Agent 调用）"""
    return get_current_agent_id() is None


def is_main_agent() -> bool:
    """是否 Main Agent"""
    return get_current_agent_id() == "main"


def assert_agent_allowed(script_name: str) -> None:
    """验证当前 Agent 是否有权限执行指定脚本。

    规则：
    - CLI 模式（无 OPENCODE_AGENT_ID）：允许所有操作
    - Main Agent（OPENCODE_AGENT_ID=main）：允许所有操作
    - Worker Agent（其他值）：禁止调用 MAIN_ONLY_SCRIPTS 中的脚本

    参数：
        script_name: 脚本名称（如 "task-dispatch", "project-init"）

    退出：
        如果 Worker 越权调用，打印错误并 sys.exit(1)
    """
    agent_id = get_current_agent_id()
    if agent_id is None:
        return  # CLI 模式，允许
    if agent_id == "main":
        return  # Main Agent，允许

    # Worker Agent 检查
    if script_name in MAIN_ONLY_SCRIPTS:
        print(
            f"Error: Agent '{agent_id}' 无权执行 {script_name} 脚本。"
            f" 该操作仅限 Main Agent 执行。",
            file=sys.stderr,
        )
        print(
            f"提示：Worker Agent 只能调用 {', '.join(sorted(WORKER_ALLOWED_SCRIPTS))}",
            file=sys.stderr,
        )
        sys.exit(1)