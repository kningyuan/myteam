"""myteam 路径常量 — 唯一来源（全部相对 MYTEAM_ROOT）。"""

import os
from pathlib import Path

MYTEAM_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = MYTEAM_ROOT / "backend"

FRONTEND_DIR = MYTEAM_ROOT / "frontend"
FRONTEND_V2_DIR = MYTEAM_ROOT / "frontend-v2"
FRONTEND_V2_DIST = FRONTEND_V2_DIR / "dist"
# Legacy v1 UI — 默认关闭对外访问；源码保留在 frontend/。设 MYTEAM_V1_UI=1 可临时恢复。
FRONTEND_V1_ENABLED = os.environ.get("MYTEAM_V1_UI", "").lower() in ("1", "true", "yes")
CONFIG_DIR = MYTEAM_ROOT / "config"
BUSINESS_DIR = MYTEAM_ROOT / "business"
BUSINESS_CONFIG_DIR = BUSINESS_DIR / "config"
RULES_DIR = BUSINESS_DIR / "rules"
WORKSPACES_DIR = BUSINESS_DIR / "workspaces"
SKILL_DIR = MYTEAM_ROOT / "skill"
TASKS_DIR = BUSINESS_DIR / "tasks"
PROJECTS_DIR = TASKS_DIR / "project"

WORKSPACE_PREFIX = "workspace-"

MYTEAM_DIR = MYTEAM_ROOT
STATIC_DIR = FRONTEND_DIR
DATA_DIR = CONFIG_DIR
TEAM_DIR = MYTEAM_ROOT

# 系统配置（与业务领域无关，随代码走，留在 config/）
SKILL_CONFIG_FILE = CONFIG_DIR / "skill_config.json"
SYSTEM_CONFIG_FILE = CONFIG_DIR / "system_config.json"

# 业务配置 + 业务运行态（随业务领域变化，落 business/config/，已 gitignore）
AGENTS_CONFIG_FILE = BUSINESS_CONFIG_DIR / "agents_config.json"
AGENTS_REGISTRY_FILE = BUSINESS_CONFIG_DIR / "agents_registry.json"
MCP_REGISTRY_FILE = BUSINESS_CONFIG_DIR / "mcp_registry.json"
GROUPS_FILE = BUSINESS_CONFIG_DIR / "groups.json"
SESSION_MAP_FILE = BUSINESS_CONFIG_DIR / "session_map.json"
CHAT_ARCHIVES_DIR = BUSINESS_CONFIG_DIR / "chat_archives"
GROUP_ARCHIVES_FILE = BUSINESS_CONFIG_DIR / "group_archives.json"

IDENTITY_FILES = ["IDENTITY.md", "SOUL.md", "USER.md"]
# CLI 编排 + Hub 聊天实际读取的工作区 Markdown（与 IDENTITY_FILES 同源）
AGENT_WORKSPACE_FILES = IDENTITY_FILES


def resolve_path(path: str | Path) -> Path:
    """将配置中的相对路径解析为绝对路径（相对 MYTEAM_ROOT）。"""
    p = Path(path)
    if p.is_absolute():
        return p
    return (MYTEAM_ROOT / p).resolve()


def to_relative_path(path: str | Path) -> str:
    """存储/API 返回用：尽量转为相对 MYTEAM_ROOT 的路径。"""
    p = Path(path).resolve()
    try:
        rel = p.relative_to(MYTEAM_ROOT.resolve())
        return rel.as_posix()
    except ValueError:
        return p.as_posix()


def resolve_workspace(agent_id: str, custom: str | None = None) -> Path:
    """解析 Agent 工作目录（支持相对路径）。"""
    if custom:
        p = resolve_path(custom)
        if p.is_dir():
            return p
    primary = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"
    if primary.is_dir():
        return primary
    alt = WORKSPACES_DIR / agent_id
    if alt.is_dir():
        return alt
    return primary
