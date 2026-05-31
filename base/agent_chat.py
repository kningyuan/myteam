"""
Agent Chat - 轻量级本地 Agent 交互核心模块
支持多 CLI 后端、Agent 配置管理
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator, Optional

# 注册所有 CLI 后端
sys.path.insert(0, str(Path(__file__).parent))
from backends import registry
from backends.base import BackendConfig

# 身份和 session 管理
from agent_identity import AgentIdentityBuilder, multi_agent_manager
from session_manager import session_manager as sm
from system_config import system_config

BASE_DIR = Path(__file__).parent.parent  # myteam/
WORKSPACES_DIR = BASE_DIR / "workspaces"
RULES_DIR = BASE_DIR / "skill"
WORKSPACE_PREFIX = "workspace-"
AGENTS_CONFIG_FILE = BASE_DIR / "data" / "agents_config.json"


# ============ Agent 后端配置管理 ============

def _load_agents_config() -> dict:
    try:
        if AGENTS_CONFIG_FILE.exists():
            with open(AGENTS_CONFIG_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_agents_config(config: dict):
    AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENTS_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_agent_backend_config(agent_id: str) -> BackendConfig:
    """获取 Agent 的后端配置（backend + model），未配置时从系统配置推导"""
    config = _load_agents_config()
    agent_cfg = config.get(agent_id)
    if agent_cfg:
        return BackendConfig(
            backend_id=agent_cfg.get("backend", "opencode"),
            model=agent_cfg.get("model", ""),
            extra=agent_cfg.get("extra", {}),
        )
    return _derive_backend_config(agent_id)

def delete_agent_config(agent_id: str):
    """删除 Agent 配置"""
    config = _load_agents_config()
    if agent_id in config:
        del config[agent_id]
        _save_agents_config(config)

def set_agent_backend_config(agent_id: str, backend_id: str, model: str, extra: dict = None, name: str = None, workspace: str = None):
    config = _load_agents_config()
    entry = {"backend": backend_id, "model": model, "extra": extra or {}}
    if name is not None:
        entry["name"] = name
    if workspace is not None:
        entry["workspace"] = workspace
    config[agent_id] = entry
    _save_agents_config(config)

def _derive_backend_config(agent_id: str) -> BackendConfig:
    """从系统配置推导后端配置"""
    backend = registry.get("opencode")
    default_model = system_config.get_default_model("opencode")
    return BackendConfig(backend_id="opencode", model=default_model)

def list_all_backends_with_models() -> list[dict]:
    """列出所有后端及其模型"""
    result = []
    for backend in registry.list_all():
        models = backend.list_models()
        result.append({
            "id": backend.id,
            "name": backend.display_name,
            "capabilities": {
                "streaming": backend.capabilities.streaming,
                "tool_use": backend.capabilities.tool_use,
                "multi_turn": backend.capabilities.multi_turn,
                "json_output": backend.capabilities.json_output,
                "custom_rules": backend.capabilities.custom_rules,
            },
            "models": [
                {"id": m.id, "name": m.name, "provider": m.provider, "default": m.default}
                for m in models
            ],
        })
    return result


# ============ Agent 扫描 ============

def scan_agents() -> list[dict]:
    """扫描所有 workspace 目录，返回可用 Agent 列表（含 backend/model）"""
    seen = set()
    agents = []
    config = _load_agents_config()
    for ws_dir in sorted(WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*")):
        if not ws_dir.is_dir():
            continue
        agent_id = ws_dir.name[len(WORKSPACE_PREFIX):]
        builder = AgentIdentityBuilder(agent_id, str(ws_dir))
        backend_cfg = get_agent_backend_config(agent_id)
        # 优先使用自定义名称
        agent_cfg = config.get(agent_id, {})
        custom_name = agent_cfg.get("name")
        custom_workspace = agent_cfg.get("workspace")
        agents.append({
            "id": agent_id,
            "name": custom_name or builder.extract_chinese_name(),
            "workspace": custom_workspace or str(ws_dir),
            "backend": backend_cfg.backend_id,
            "model": backend_cfg.model,
        })
        seen.add(agent_id)

    return agents


# ============ 系统提示和规则文件 ============

def build_system_prompt(agent_id: str, workspace: str) -> str:
    builder = AgentIdentityBuilder(agent_id, workspace)
    sections = []
    identity = builder.get_identity_context()
    if identity:
        sections.append(f"<core_instructions>\n{identity}\n</core_instructions>")
    multi_context = multi_agent_manager.build_multi_agent_context(agent_id)
    if multi_context:
        sections.append(f"<multi_agent_context>\n{multi_context}\n</multi_agent_context>")
    return "\n\n".join(sections) if sections else ""

def create_merged_rules_file(agent_id: str, workspace: str) -> Optional[str]:
    """动态合并规则文件"""
    rules_dir = RULES_DIR
    universal_rules = rules_dir / "universal-rules.md"
    agent_agents_md = Path(workspace) / "AGENTS.md"
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".md", prefix=f"rules-{agent_id}-", dir="/tmp")
        builder = AgentIdentityBuilder(agent_id, workspace)
        chinese_name = builder.extract_chinese_name()
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"# {chinese_name} - 完整规则\n\n")
            if universal_rules.exists():
                f.write(universal_rules.read_text(encoding="utf-8"))
                f.write("\n\n---\n\n")
            for rfile in ["brainstorming-guide.md", "worker-template.md"]:
                fp = rules_dir / rfile
                if agent_id != "main" and fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            if agent_agents_md.exists():
                f.write(agent_agents_md.read_text(encoding="utf-8"))
        return temp_path
    except Exception as e:
        print(f"[WARN] 创建规则文件失败: {e}", file=sys.stderr)
        return None


# ============ Agent 删除 ============

def delete_agent(agent_id: str) -> tuple[bool, str]:
    """删除 Agent（工作目录 + 配置 + session）"""
    import shutil
    workspace = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"
    if workspace.exists() and workspace.is_dir():
        shutil.rmtree(workspace)
    delete_agent_config(agent_id)
    try:
        sm.remove_mapping(f"{agent_id}:workspace-{agent_id}", agent_id)
    except Exception:
        pass
    return True, f"Agent '{agent_id}' 已删除"


# ============ 流式对话 ============

def stream_chat(agent_id: str, message: str) -> Generator[str, None, None]:
    """
    与 Agent 对话，流式返回 SSE JSON 事件
    使用 Agent 配置的 CLI 后端和模型
    """
    workspace = str(WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}")
    if not os.path.isdir(workspace):
        # 也检查 workspace 直接 = agent_id 的情况
        alt_workspace = str(WORKSPACES_DIR / agent_id)
        if not os.path.isdir(alt_workspace):
            yield json.dumps({"event": "error", "data": {"message": f"Agent '{agent_id}' 的工作目录不存在"}})
            return
        workspace = alt_workspace

    backend_cfg = get_agent_backend_config(agent_id)
    backend = registry.get(backend_cfg.backend_id)
    if not backend:
        yield json.dumps({"event": "error", "data": {"message": f"后端 '{backend_cfg.backend_id}' 未注册"}})
        return

    stable_key = f"{agent_id}:workspace-{agent_id}"
    rules_file = create_merged_rules_file(agent_id, workspace)
    system_prompt = build_system_prompt(agent_id, workspace)
    full_message = f"【系统指令】\n{system_prompt}\n\n【用户消息】\n{message}" if system_prompt else message

    try:
        # 已有 session？
        session_id = sm.get_opencode_session(stable_key, agent_id) if sm else None

        events = list(backend.chat(
            workspace, full_message, backend_cfg.model,
            session_id, rules_file, agent_id,
        ))

        has_thinking = any(e.event_type == "thinking" for e in events)

        # session 过期重试
        if not has_thinking and session_id and backend.capabilities.multi_turn:
            sm.remove_mapping(stable_key, agent_id)
            events = list(backend.chat(
                workspace, full_message, backend_cfg.model,
                None, rules_file, agent_id,
            ))

        # yield 所有事件
        sid = ""
        for event in events:
            if event.event_type == "thinking":
                yield json.dumps({"event": "thinking", "data": event.data})
            elif event.event_type == "error":
                yield json.dumps({"event": "error", "data": {"message": event.data.get("message", "")}})
                return
            elif event.event_type == "session":
                sid = event.data.get("session_id", "")

        # 保存 session
        if sm and sid:
            sm.set_opencode_session(stable_key, agent_id, sid)

        yield json.dumps({"event": "done", "data": {"session_id": sid}})

    finally:
        if rules_file and os.path.exists(rules_file):
            try:
                os.remove(rules_file)
            except Exception:
                pass


# 兼容旧函数
def get_agent_model(agent_id: str) -> str:
    return get_agent_backend_config(agent_id).model
