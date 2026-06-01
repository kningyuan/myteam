"""myteam skill/team 路径常量 — 唯一来源（全部相对 MYTEAM_ROOT）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# skill/team/common/paths.py → parents: common(0) team(1) skill(2) myteam(3)
MYTEAM_ROOT = Path(os.environ.get("MYTEAM_ROOT", str(Path(__file__).resolve().parents[3])))
TEAM_SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_DIR = MYTEAM_ROOT / "skill"
CONFIG_DIR = MYTEAM_ROOT / "config"

TASKS_DIR = MYTEAM_ROOT / "tasks"
PROJECTS_DIR = TASKS_DIR / "project"
WORKSPACES_DIR = MYTEAM_ROOT / "workspaces"
LOGS_DIR = TASKS_DIR / "_logs"

WORKSPACE_PREFIX = "workspace-"

SESSION_MAP_FILE = Path(
    os.environ.get("MYTEAM_SESSION_MAP", str(CONFIG_DIR / "session_map.json"))
)
MYTEAM_HUB_URL = os.environ.get("MYTEAM_HUB_URL", "http://127.0.0.1:8765").rstrip("/")

# 兼容旧名
TEAM_OK_DIR = TEAM_SKILL_DIR
SKILLS_DIR = TEAM_SKILL_DIR
TEAM_DIR = MYTEAM_ROOT
MYTEAM_DIR = MYTEAM_ROOT
CONTINUOUS_DIR = TASKS_DIR / "continuous"


def ensure_team_importable() -> Path:
    """将 skill/team 加入 sys.path。"""
    p = str(TEAM_SKILL_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
    return TEAM_SKILL_DIR


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


def notify_agent_script() -> Path:
    return script_path("agent-notify", "scripts", "notify_agent.py")


def task_queue_script() -> Path:
    return script_path("task-queue", "scripts", "task_queue.py")


def project_data_script() -> Path:
    return script_path("project-data", "scripts", "project_data.py")


def dispatch_script() -> Path:
    return script_path("task-dispatch", "scripts", "dispatch.py")


def task_monitor_script() -> Path:
    return script_path("task-monitor", "scripts", "task_monitor.py")


def templates_file() -> Path:
    return script_path("templates", "templates.yaml")


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
