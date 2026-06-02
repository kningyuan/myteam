"""
Agent Chat - 轻量级本地 Agent 交互核心模块
支持多 CLI 后端、Agent 配置管理
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hub.paths import (
    AGENTS_CONFIG_FILE,
    SKILL_DIR,
    WORKSPACE_PREFIX,
    WORKSPACES_DIR,
    resolve_path,
    resolve_workspace,
    to_relative_path,
)
from store.system_config import system_config
from base.agent_identity import AgentIdentityBuilder, multi_agent_manager

RULES_DIR = SKILL_DIR / "rule"


@dataclass
class BackendConfig:
    backend_id: str
    model: str
    extra: dict = field(default_factory=dict)


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


def set_agent_backend_config(
    agent_id: str,
    backend_id: str,
    model: str,
    extra: dict = None,
    name: str = None,
    workspace: str = None,
):
    config = _load_agents_config()
    entry = {"backend": backend_id, "model": model, "extra": extra or {}}
    if name is not None:
        entry["name"] = name
    if workspace is not None:
        entry["workspace"] = to_relative_path(resolve_path(workspace)) if workspace else workspace
    config[agent_id] = entry
    _save_agents_config(config)


def _derive_backend_config(agent_id: str) -> BackendConfig:
    """从系统配置推导后端配置"""
    default_model = system_config.get_default_model("opencode")
    return BackendConfig(backend_id="opencode", model=default_model)


def list_all_backends_with_models() -> list[dict]:
    """列出所有 Adapter 及其模型。"""
    import adapters  # noqa: F401
    from adapter.registry import registry as adapter_registry

    result = []
    for adapter in adapter_registry.list_all():
        caps = adapter.capabilities
        result.append({
            "id": adapter.id,
            "name": adapter.display_name,
            "capabilities": {
                "streaming": caps.streaming,
                "tool_use": caps.tool_use,
                "multi_turn": caps.multi_turn,
                "json_output": True,
                "custom_rules": caps.custom_rules,
            },
            "models": [
                {"id": m.id, "name": m.name, "provider": m.provider, "default": m.default}
                for m in adapter.list_models()
            ],
        })
    return result


# ============ Agent 扫描 ============

def scan_agents() -> list[dict]:
    """扫描 team/workspaces 目录，返回可用 Agent 列表（含 backend/model）"""
    agents = []
    config = _load_agents_config()
    if not WORKSPACES_DIR.is_dir():
        return agents

    for ws_dir in sorted(WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*")):
        if not ws_dir.is_dir():
            continue
        agent_id = ws_dir.name[len(WORKSPACE_PREFIX):]
        if not agent_id:
            continue
        builder = AgentIdentityBuilder(agent_id, str(ws_dir))
        backend_cfg = get_agent_backend_config(agent_id)
        agent_cfg = config.get(agent_id, {})
        custom_name = agent_cfg.get("name")
        custom_workspace = agent_cfg.get("workspace")
        workspace_path = resolve_workspace(agent_id, custom_workspace)
        agents.append({
            "id": agent_id,
            "name": custom_name or builder.extract_chinese_name(),
            "workspace": to_relative_path(workspace_path),
            "backend": backend_cfg.backend_id,
            "model": backend_cfg.model,
        })

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
    universal_rules = RULES_DIR / "universal-rules.md"
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
                fp = RULES_DIR / rfile
                if agent_id != "main" and fp.exists():
                    f.write(fp.read_text(encoding="utf-8"))
                    f.write("\n\n---\n\n")
            if agent_agents_md.exists():
                f.write(agent_agents_md.read_text(encoding="utf-8"))
        return temp_path
    except Exception as e:
        print(f"[WARN] 创建规则文件失败: {e}", file=sys.stderr)
        return None


def _clear_agent_sessions(agent_id: str, backend_id: str | None = None):
    from store.sessions import session_store

    ws_key = f"workspace-{agent_id}"
    adapter_ids = [backend_id] if backend_id else ["opencode", "claude"]
    for aid in adapter_ids:
        if aid:
            try:
                session_store.remove(aid, agent_id, ws_key)
            except Exception:
                pass


# ============ Agent 删除 ============

def delete_agent(agent_id: str) -> tuple[bool, str]:
    """删除 Agent（工作目录 + 配置 + session）"""
    import shutil

    backend_cfg = get_agent_backend_config(agent_id)
    workspace = resolve_workspace(agent_id, _load_agents_config().get(agent_id, {}).get("workspace"))
    if workspace.exists() and workspace.is_dir():
        shutil.rmtree(workspace)
    delete_agent_config(agent_id)
    _clear_agent_sessions(agent_id, backend_cfg.backend_id)
    return True, f"Agent '{agent_id}' 已删除"


# ============ 清空对话 ============

def clear_agent_chat_context(agent_id: str) -> tuple[bool, str]:
    """清空 Agent 多轮上下文（Session 映射），不影响工作区文件。"""
    agent_cfg = _load_agents_config().get(agent_id, {})
    workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
    if not workspace.is_dir():
        return False, f"Agent '{agent_id}' 不存在"

    backend_cfg = get_agent_backend_config(agent_id)
    _clear_agent_sessions(agent_id, backend_cfg.backend_id)
    return True, "对话记录与 Agent 上下文已清空"


# ============ 流式对话 ============

def stream_chat(agent_id: str, message: str, cancel_event=None) -> Generator[str, None, None]:
    """与 Agent 对话 — 委托 hub.services.ChatService（Adapter 抽象层）。"""
    from hub.services.chat_service import chat_service
    yield from chat_service.stream(agent_id, message, cancel_event=cancel_event)


def get_agent_model(agent_id: str) -> str:
    return get_agent_backend_config(agent_id).model
