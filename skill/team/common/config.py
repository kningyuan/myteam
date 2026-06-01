"""
skill/team 全局配置模块
从 skill/team/.env 加载配置，支持环境变量覆盖
"""
import os
from pathlib import Path

# 定位 .env 文件（在 skill/team/ 目录下）
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text("utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            if _k:
                os.environ.setdefault(_k, _v.strip())


def env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _skill_cfg_int(section: str, key: str, default: int) -> int:
    try:
        from common.skill_settings import section_int
        return section_int(section, key, default)
    except Exception:
        return default


def resolve_int(env_key: str, section: str, cfg_key: str, default: int) -> int:
    """环境变量优先，其次 config/skill_config.json。"""
    if env_key in os.environ:
        return env_int(env_key, default)
    return _skill_cfg_int(section, cfg_key, default)


# ── Executor ──
POLL_INTERVAL = resolve_int("EXECUTOR_POLL_INTERVAL", "executor", "poll_interval", 5)
ACK_TIMEOUT = resolve_int("EXECUTOR_ACK_TIMEOUT", "executor", "ack_timeout", 300)
TASK_TIMEOUT = resolve_int("EXECUTOR_TASK_TIMEOUT", "executor", "task_timeout", 3600)
EVALUATE_TIMEOUT = env_int("EXECUTOR_EVALUATE_TIMEOUT", 600)
EXECUTE_TIMEOUT = env_int("EXECUTOR_EXECUTE_TIMEOUT", 3600)
MAX_RETRIES = resolve_int("EXECUTOR_MAX_RETRIES", "executor", "max_retries", 3)
MAX_EVALUATE_RETRIES = env_int("EXECUTOR_MAX_EVALUATE_RETRIES", 3)
MAX_EXECUTE_RETRIES = env_int("EXECUTOR_MAX_EXECUTE_RETRIES", 3)

# ── Agent 通知 ──
AGENT_MSG_TIMEOUT = resolve_int("AGENT_MSG_TIMEOUT", "executor", "agent_msg_timeout", 1800)

# ── 握手 ACK ──
HANDSHAKE_ACK_TIMEOUT = env_int("HANDSHAKE_ACK_TIMEOUT", 300)
HANDSHAKE_POLL_INTERVAL = env_int("HANDSHAKE_POLL_INTERVAL", 5)
HANDSHAKE_PROC_WAIT_TIMEOUT = env_int("HANDSHAKE_PROC_WAIT_TIMEOUT", 5)

# ── Telegram 通知 ──
TELEGRAM_CURL_TIMEOUT = env_int("TELEGRAM_CURL_TIMEOUT", 60)
TELEGRAM_MAX_RETRIES = env_int("TELEGRAM_MAX_RETRIES", 2)
GROUP_NOTIFY_TIMEOUT = env_int("GROUP_NOTIFY_TIMEOUT", 30)
GROUP_NOTIFY_URL_TIMEOUT = env_int("GROUP_NOTIFY_URL_TIMEOUT", 10)
NOTIFY_EVENT_TIMEOUT = env_int("NOTIFY_EVENT_TIMEOUT", 30)

# ── 子进程默认超时 ──
SUBPROCESS_TIMEOUT = env_int("SUBPROCESS_TIMEOUT", 120)

# ── Executor 状态等待 ──
TEAM_CONFIG_TIMEOUT = resolve_int("TEAM_CONFIG_TIMEOUT", "executor", "team_config_timeout", 600)
TASK_PLAN_TIMEOUT = resolve_int("TASK_PLAN_TIMEOUT", "executor", "task_plan_timeout", 600)
TEAM_CONFIG_MAX_RETRIES = env_int("TEAM_CONFIG_MAX_RETRIES", 2)
TASK_PLAN_MAX_RETRIES = env_int("TASK_PLAN_MAX_RETRIES", 3)
NOTIFY_AGENT_TIMEOUT = env_int("NOTIFY_AGENT_TIMEOUT", 300)
RETRY_DISPATCH_SLEEP = env_int("RETRY_DISPATCH_SLEEP", 10)

# ── 各子命令调用超时 ──
QUEUE_CMD_TIMEOUT = env_int("QUEUE_CMD_TIMEOUT", 120)
COMPLETE_CMD_TIMEOUT = env_int("COMPLETE_CMD_TIMEOUT", 120)
PROJECT_DATA_CMD_TIMEOUT = env_int("PROJECT_DATA_CMD_TIMEOUT", 120)
DISPATCH_RETRY_SLEEP = env_int("DISPATCH_RETRY_SLEEP", 5)
MEMORY_SAVE_TIMEOUT = env_int("MEMORY_SAVE_TIMEOUT", 30)

# ── Resume ──
RESUME_CMD_TIMEOUT = env_int("RESUME_CMD_TIMEOUT", 120)
RESUME_CMD_SHORT_TIMEOUT = env_int("RESUME_CMD_SHORT_TIMEOUT", 5)
RESUME_RELEASE_TIMEOUT = env_int("RESUME_RELEASE_TIMEOUT", 30)
RESUME_SLEEP_INTERVAL = env_int("RESUME_SLEEP_INTERVAL", 30)