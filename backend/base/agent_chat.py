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
    AGENTS_REGISTRY_FILE,
    GROUPS_FILE,
    RULES_DIR,
    WORKSPACE_PREFIX,
    WORKSPACES_DIR,
    resolve_path,
    resolve_workspace,
    to_relative_path,
)
from store.system_config import system_config
from base.agent_identity import AgentIdentityBuilder, multi_agent_manager


@dataclass
class BackendConfig:
    backend_id: str
    model: str
    extra: dict = field(default_factory=dict)
    model_override: str = ""
    uses_settings_default: bool = False


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
    """获取 Agent 的后端配置：显式 agents_config 覆盖，否则跟随设置页默认。"""
    from common.agent_model import (
        agent_model_override,
        resolve_agent_backend,
        resolve_agent_model,
        uses_settings_default,
    )

    config = _load_agents_config()
    agent_cfg = config.get(agent_id)
    if agent_cfg:
        return BackendConfig(
            backend_id=resolve_agent_backend(agent_id, config=config),
            model=resolve_agent_model(agent_id, config=config),
            extra=agent_cfg.get("extra", {}),
            model_override=agent_model_override(agent_id, config=config),
            uses_settings_default=uses_settings_default(agent_id, config=config),
        )
    return _derive_backend_config(agent_id)


def apply_model_to_all(backend_id: str, model: str) -> dict:
    """把设置页选定的 backend + model 批量写入全部 agent。

    不区分 agent 当前后端——一并切换 backend 并改 model；保留 name/workspace/extra。
    """
    config = _load_agents_config()
    applied, migrated = [], []
    for agent in scan_agents():
        aid = agent["id"]
        prev_backend = agent.get("backend") or ""
        entry = dict(config.get(aid) or {})
        if prev_backend and prev_backend != backend_id:
            migrated.append(aid)
        entry["backend"] = backend_id
        entry["model"] = model
        entry.setdefault("extra", {})
        config[aid] = entry
        applied.append(aid)
    _save_agents_config(config)
    return {
        "backend": backend_id,
        "model": model,
        "applied": applied,
        "skipped": [],  # 兼容旧前端字段；不再按后端跳过
        "migrated": migrated,
    }


def delete_agent_config(agent_id: str):
    """删除 Agent 配置"""
    config = _load_agents_config()
    if agent_id in config:
        del config[agent_id]
        _save_agents_config(config)


def _remove_agent_from_registry(agent_id: str) -> None:
    """从 agents_registry.json 移除，避免 --init / bootstrap 再次创建 workspace。"""
    if not AGENTS_REGISTRY_FILE.exists():
        return
    try:
        with open(AGENTS_REGISTRY_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    agents = data.get("agents") or {}
    if agent_id not in agents:
        return
    del agents[agent_id]
    data["agents"] = agents
    AGENTS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENTS_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _remove_agent_from_groups(agent_id: str) -> None:
    """从群组成员列表移除已删 agent。"""
    if not GROUPS_FILE.exists():
        return
    try:
        with open(GROUPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    changed = False
    for grp in (data.get("groups") or {}).values():
        members = grp.get("members")
        if isinstance(members, list) and agent_id in members:
            grp["members"] = [m for m in members if m != agent_id]
            changed = True
    if changed:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


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
    default_backend = system_config.get("system", "default_backend", default="opencode")
    default_model = system_config.get_default_model(default_backend)
    return BackendConfig(
        backend_id=default_backend,
        model=default_model,
        uses_settings_default=True,
    )


def _adapter_models_payload(adapter, *, refresh: bool = False) -> list[dict]:
    """单后端模型列表；refresh 时绕过 OpenCode CLI 缓存。"""
    list_models = adapter.list_models
    if refresh and adapter.id == "opencode":
        from adapters.opencode.adapter import OpenCodeAdapter
        OpenCodeAdapter.invalidate_models_cache()
        models = list_models(refresh=True)
    else:
        models = list_models()
    return [
        {"id": m.id, "name": m.name, "provider": m.provider, "default": m.default}
        for m in models
    ]


def get_backend_models(backend_id: str, *, refresh: bool = False) -> list[dict]:
    """按 backend_id 返回模型列表；不存在则抛 ValueError。"""
    import adapters  # noqa: F401
    from adapter.registry import registry as adapter_registry

    adapter = adapter_registry.get(backend_id)
    if adapter is None:
        raise ValueError(f"unknown backend: {backend_id}")
    return _adapter_models_payload(adapter, refresh=refresh)


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
            "models": _adapter_models_payload(adapter),
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
            "model_override": backend_cfg.model_override,
            "uses_settings_default": backend_cfg.uses_settings_default,
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
    """删除 Agent（工作目录 + agents_config + registry + 群组 + session）"""
    import shutil

    backend_cfg = get_agent_backend_config(agent_id)
    workspace = resolve_workspace(agent_id, _load_agents_config().get(agent_id, {}).get("workspace"))
    if workspace.exists() and workspace.is_dir():
        shutil.rmtree(workspace)
    delete_agent_config(agent_id)
    _remove_agent_from_registry(agent_id)
    _remove_agent_from_groups(agent_id)
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
    # P0：DM 记忆路径的历史在 Store，清空时一并清掉（消息 + 摘要/pins）
    try:
        from common.store import Store
        s = Store()
        try:
            s.clear_conversation(f"dm:{agent_id}")
        finally:
            s.close()
    except Exception:
        pass
    return True, "对话记录与 Agent 上下文已清空"


# ============ 流式对话 ============

def stream_chat(agent_id: str, message: str, cancel_event=None,
                *, use_memory: bool = False) -> Generator[str, None, None]:
    """与 Agent 对话 — 委托 hub.services.ChatService（Adapter 抽象层）。

    use_memory=True：DM 记忆路径（对话进 Store + Context Assembler）。群组/通知等保持默认 False。
    """
    from hub.services.chat_service import chat_service
    yield from chat_service.stream(agent_id, message, cancel_event=cancel_event,
                                   use_memory=use_memory)


def get_agent_model(agent_id: str) -> str:
    return get_agent_backend_config(agent_id).model
