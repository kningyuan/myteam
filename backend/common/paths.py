"""myteam 内核（backend/common）路径常量 — 唯一来源（全部相对 MYTEAM_ROOT）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# backend/common/paths.py → parents: common(0) backend(1) myteam(2)
MYTEAM_ROOT = Path(os.environ.get("MYTEAM_ROOT", str(Path(__file__).resolve().parents[2])))
BACKEND_DIR = Path(__file__).resolve().parents[1]
TEAM_SKILL_DIR = MYTEAM_ROOT / "skill" / "team"
SKILL_DIR = MYTEAM_ROOT / "skill"
CONFIG_DIR = MYTEAM_ROOT / "config"
BUSINESS_DIR = MYTEAM_ROOT / "business"
BUSINESS_CONFIG_DIR = BUSINESS_DIR / "config"
RULES_DIR = BUSINESS_DIR / "rules"

AGENTS_CONFIG_FILE = BUSINESS_CONFIG_DIR / "agents_config.json"
AGENTS_REGISTRY_FILE = BUSINESS_CONFIG_DIR / "agents_registry.json"

TASKS_DIR = BUSINESS_DIR / "tasks"
PROJECTS_DIR = TASKS_DIR / "project"
WORKSPACES_DIR = BUSINESS_DIR / "workspaces"
LOGS_DIR = TASKS_DIR / "_logs"

WORKSPACE_PREFIX = "workspace-"

SESSION_MAP_FILE = Path(
    os.environ.get("MYTEAM_SESSION_MAP", str(BUSINESS_CONFIG_DIR / "session_map.json"))
)
MYTEAM_HUB_URL = os.environ.get("MYTEAM_HUB_URL", "http://127.0.0.1:8765").rstrip("/")

# 兼容旧名
TEAM_OK_DIR = TEAM_SKILL_DIR
SKILLS_DIR = TEAM_SKILL_DIR
TEAM_DIR = MYTEAM_ROOT
MYTEAM_DIR = MYTEAM_ROOT
CONTINUOUS_DIR = TASKS_DIR / "continuous"


def ensure_team_importable() -> Path:
    """将 backend 加入 sys.path，使 `common` 内核包可被导入。"""
    p = str(BACKEND_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
    return BACKEND_DIR


def bootstrap(from_file: str | Path) -> Path:
    """脚本入口：插入 skill/team 到 sys.path 并返回 TEAM_SKILL_DIR。"""
    team_dir = Path(from_file).resolve().parents[2]
    p = str(team_dir)
    if p not in sys.path:
        sys.path.insert(0, p)
    return team_dir


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (MYTEAM_ROOT / p).resolve()


def to_relative_path(path: str | Path) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(MYTEAM_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def workspace_dir(agent_id: str) -> Path:
    return WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def task_data_path(project_id: str) -> Path:
    return project_dir(project_id) / "task_data.json"


def deliverables_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "deliverables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def skills_log_path(project_id: str) -> Path:
    return project_dir(project_id) / "skill-logs" / "skills.log"


def trigger_dir(agent_id: str) -> Path:
    return workspace_dir(agent_id) / ".trigger"


def response_dir(agent_id: str) -> Path:
    return workspace_dir(agent_id) / ".response"


def trigger_file_path(agent_id: str, project_id: str, task_id: str) -> Path:
    return trigger_dir(agent_id) / f"{project_id}_{task_id}.trigger"


def ack_file_path(agent_id: str, project_id: str, task_id: str) -> Path:
    return trigger_dir(agent_id) / f"{project_id}_{task_id}.ack"


def response_file_path(agent_id: str, project_id: str, task_id: str) -> Path:
    return response_dir(agent_id) / f"{project_id}_{task_id}.response"


def script_path(*parts: str) -> Path:
    return TEAM_SKILL_DIR.joinpath(*parts)


def templates_file() -> Path:
    return BUSINESS_DIR / "templates" / "templates.yaml"


def prompt_templates_file() -> Path:
    return BUSINESS_DIR / "templates" / "prompt_templates.yaml"


def prompt_injections_file() -> Path:
    return BUSINESS_DIR / "templates" / "prompt_injections.yaml"


def delivery_profiles_file() -> Path:
    return BUSINESS_DIR / "templates" / "delivery_profiles.yaml"


def delivery_templates_dir() -> Path:
    return BUSINESS_DIR / "delivery_templates"


def telegram_config_file() -> Path:
    """Telegram bot 配置：优先 config/telegram.json，其次 config/openclaw.json。"""
    for name in ("telegram.json", "openclaw.json"):
        p = CONFIG_DIR / name
        if p.exists():
            return p
    return CONFIG_DIR / "telegram.json"


def registry_file() -> Path:
    return TEAM_SKILL_DIR / "registry.json"


def session_key(adapter_id: str, agent_id: str, *, context: str = "chat") -> str:
    ws = f"{WORKSPACE_PREFIX}{agent_id}" if context == "chat" else context
    return f"{adapter_id}:{agent_id}:{ws}"
