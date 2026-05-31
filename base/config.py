"""
OpenCode 适配器配置模块
根据 opencode 实际参数配置 - 优化版
"""
import os
from pathlib import Path


def load_env_file():
    """从 .env 文件加载环境变量"""
    # 尝试多个可能的位置
    possible_paths = [
        Path(__file__).parent.parent / ".env",  # ~/myteam/.env
        Path(__file__).parent / ".env",         # ~/myteam/lib/.env
        Path.home() / ".openclaw" / "scripts" / ".env",  # 旧版 fallback
    ]
    
    for env_file in possible_paths:
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value
            break


# 启动时加载 .env 文件
load_env_file()


class Config:
    """配置类"""
    
    # 基础路径
    HOME_DIR = Path.home()
    MYTEAM_DIR = Path(__file__).parent.parent
    OPENCLAW_DIR = HOME_DIR / ".openclaw"  # 旧版 openclaw.json 共享配置
    
    # OpenCode CLI 路径
    OPENCODE_CLI_PATH = os.environ.get("OPENCODE_CLI_PATH", str(HOME_DIR / ".opencode/bin/opencode"))
    
    # 项目目录
    OPENCODE_PROJECTS_DIR = HOME_DIR / ".opencode" / "projects"
    
    # 调试模式
    DEBUG_MODE = os.environ.get("OPENCODE_DEBUG", "false").lower() == "true"
    DEBUGALL_MODE = os.environ.get("OPENCODE_DEBUG_ALL", "false").lower() == "true"
    
    # 上下文配置
    ENABLE_CONTEXT = os.environ.get("OPENCODE_ENABLE_CONTEXT", "true").lower() == "true"
    MAX_CONTEXT_TOKENS = int(os.environ.get("OPENCODE_MAX_CONTEXT_TOKENS", "80000"))
    
    # 上下文优化配置
    ENABLE_SMART_COMPRESSION = os.environ.get("OPENCODE_SMART_COMPRESSION", "true").lower() == "true"
    COMPRESSION_THRESHOLD = float(os.environ.get("OPENCODE_COMPRESSION_THRESHOLD", "0.8"))
    
    # 超时配置（秒）
    DEFAULT_TIMEOUT = int(os.environ.get("OPENCODE_TIMEOUT", "600"))
    MAX_RETRIES = int(os.environ.get("OPENCODE_MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.environ.get("OPENCODE_RETRY_DELAY", "5"))
    
    # 默认模型 - OpenCode 格式
    DEFAULT_MODEL = os.environ.get("OPENCODE_DEFAULT_MODEL", "opencode/minimax-m2.5-free")
    
    # Session 配置
    SESSION_PERSISTENCE = os.environ.get("OPENCODE_SESSION_PERSISTENCE", "true").lower() == "true"
    
    # 日志配置 - 输出到 /tmp 目录
    LOG_DIR = Path("/tmp")
    DEBUG_LOG = LOG_DIR / "openclaw-opencode-debug.log"
    DEBUG_ALL_LOG = LOG_DIR / "openclaw-opencode-debug-all.log"
    
    # Session 映射文件（myteam/data/ 下管理）
    SESSION_MAP_FILE = MYTEAM_DIR / "data" / "opencode_session_map.json"
    
    # Agent 身份配置
    ENABLE_AGENT_IDENTITY = os.environ.get("OPENCODE_ENABLE_AGENT_IDENTITY", "true").lower() == "true"
    IDENTITY_FILES = ["IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md"]
    
    # 允许的只读目录
    READONLY_DIRECTORIES = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/tmp",
        "/var/log",
        "/Users/user/.openclaw",
        str(MYTEAM_DIR),
    ]
    
    # 多 Agent 工作区根目录
    AGENTS_BASE_DIR = MYTEAM_DIR / "workspaces"
    
    # 优先级上下文文件（不会被压缩）
    PRIORITY_CONTEXT_FILES = [
        "IDENTITY.md",
        "USER.md", 
        "SOUL.md",
        "AGENTS.md",
    ]
    
    # 分层上下文配置
    ENABLE_LAYERED_CONTEXT = os.environ.get("OPENCODE_LAYERED_CONTEXT", "true").lower() == "true"
    LAYERED_CONTEXT_TOKENS = {
        "core": int(os.environ.get("OPENCODE_CORE_TOKENS", "15000")),
        "tools": int(os.environ.get("OPENCODE_TOOLS_TOKENS", "8000")),
        "fewshot": int(os.environ.get("OPENCODE_FEWSHOT_TOKENS", "5000")),
        "dynamic": int(os.environ.get("OPENCODE_DYNAMIC_TOKENS", "40000")),
    }
    
    # ========== 流式输出配置（新增）==========
    
    # 是否启用流式输出
    ENABLE_STREAMING_OUTPUT = os.environ.get("OPENCODE_ENABLE_STREAMING", "true").lower() == "true"
    
    # 每多少行汇报一次
    STREAMING_LINES_PER_REPORT = int(os.environ.get("OPENCODE_STREAMING_LINES", "10"))
    
    # 汇报间隔（秒）- 即使行数不足，到这个时间也汇报
    STREAMING_REPORT_INTERVAL = int(os.environ.get("OPENCODE_STREAMING_INTERVAL", "120"))
    
    # 最小汇报间隔（秒）- 防止刷屏
    STREAMING_MIN_REPORT_INTERVAL = int(os.environ.get("OPENCODE_STREAMING_MIN_INTERVAL", "30"))
    
    # 流式发送批量大小（缓存N条消息后发送，1=每条实时发）
    STREAMING_BATCH_SIZE = int(os.environ.get("OPENCODE_STREAMING_BATCH_SIZE", "1"))

    # A 档：工具输出在 Telegram 中单条预览最大字符（超出截断，长文仍由 send_long_message 分段）
    STREAMING_TOOL_OUTPUT_MAX = int(os.environ.get("OPENCODE_STREAMING_TOOL_OUTPUT_MAX", "12000"))

    # 是否在每条 step_finish 发送 Token 统计（false 可减少「空轮次+Token」噪音）
    STREAMING_SHOW_STEP_TOKENS = (
        os.environ.get("OPENCODE_STREAMING_SHOW_STEP_TOKENS", "true").lower() == "true"
    )

    # Telegram sendMessage 失败重试次数（含 URLError / 5xx）
    TELEGRAM_SEND_RETRIES = int(os.environ.get("OPENCODE_TELEGRAM_SEND_RETRIES", "3"))
