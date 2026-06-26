"""myteam 路径常量 — 重新导出自 common.paths（唯一来源）。

hub 侧的所有路径定义已合并至 common.paths，保证单一事实来源。
向后兼容：from hub.paths import X 的调用方无需改动。

弃用策略：新增路径请直接添加到 common/paths.py。本文件将逐步移除。
"""
from common.paths import (  # noqa: F401,F403  — re-export
    AGENTS_CONFIG_FILE,
    AGENTS_REGISTRY_FILE,
    AGENT_WORKSPACE_FILES,
    BACKEND_DIR,
    BUSINESS_CONFIG_DIR,
    BUSINESS_DIR,
    CHAT_ARCHIVES_DIR,
    CONFIG_DIR,
    DATA_DIR,
    FRONTEND_DIR,
    FRONTEND_DIST,
    GROUP_ARCHIVES_FILE,
    GROUPS_FILE,
    IDENTITY_FILES,
    MCP_REGISTRY_FILE,
    MYTEAM_DIR,
    MYTEAM_ROOT,
    PROJECTS_DIR,
    resolve_path,
    resolve_workspace,
    RULES_DIR,
    SESSION_MAP_FILE,
    SKILL_CONFIG_FILE,
    SKILL_DIR,
    SKILLS_DIR,
    SYSTEM_CONFIG_FILE,
    TASKS_DIR,
    TEAM_DIR,
    TEAM_OK_DIR,
    TEAM_SKILL_DIR,
    to_relative_path,
    WORKSPACES_DIR,
    WORKSPACE_PREFIX,
)