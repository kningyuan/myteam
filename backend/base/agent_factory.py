"""
Agent Factory - 一键创建 Agent
根据描述自动生成工作目录和能力文件
"""

from common.coordinator import get_coordinator_id

import json
import re
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.paths import WORKSPACE_PREFIX, WORKSPACES_DIR, to_relative_path
from base.agent_chat import (
    set_agent_backend_config,
    stream_chat,
)
from hub.services.agent_registry import register_agent


def _default_model(backend_id: str) -> str:
    import adapter as _adapter  # noqa: F401  — side-effect CLI 注册
    from adapter.core.registry import registry

    adapter = registry.get(backend_id)
    return adapter.get_default_model() if adapter else ""


def generate_agent(
    agent_id: str,
    description: str,
    backend_id: str = "opencode",
    model: str = "",
    chinese_name: str = "",
    use_existing_agent_for_gen: bool = True,
    role: str = "worker",
    task_types: Optional[list[str]] = None,
    capabilities: Optional[list[str]] = None,
) -> dict:
    werk = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"

    if werk.exists():
        return {"success": False, "error": f"Agent '{agent_id}' 的工作目录已存在"}

    if not model:
        model = _default_model(backend_id)

    if use_existing_agent_for_gen:
        files_content = _generate_via_llm(agent_id, description, chinese_name, backend_id, model)
    else:
        files_content = _generate_template(agent_id, description, chinese_name)

    if not files_content:
        files_content = _generate_template(agent_id, description, chinese_name)

    werk.mkdir(parents=True, exist_ok=True)
    trigger_dir = werk / ".trigger"
    response_dir = werk / ".response"
    trigger_dir.mkdir(exist_ok=True)
    response_dir.mkdir(exist_ok=True)

    created_files = []
    for filename, content in files_content.items():
        file_path = werk / filename
        file_path.write_text(content.strip() + "\n", encoding="utf-8")
        created_files.append(filename)

        if filename == "IDENTITY.md" and not chinese_name:
            chinese_name = _extract_name_from_identity(content)

    set_agent_backend_config(agent_id, backend_id, model, workspace=to_relative_path(werk))

    resolved_tts = list(task_types or [])
    if not resolved_tts:
        from common.agent.agent_task_type_suggest import suggest_task_types_for_agent

        try:
            resolved_tts = suggest_task_types_for_agent(
                description, name=chinese_name or agent_id, agent_id=agent_id,
            ).get("task_types") or []
        except ValueError:
            resolved_tts = []

    # 注册到 agents_registry.json
    register_agent(agent_id, name=chinese_name or agent_id, role=role,
                   description=description,
                   capabilities=capabilities or [],
                   task_types=resolved_tts)

    return {
        "success": True,
        "agent_id": agent_id,
        "chinese_name": chinese_name,
        "workspace": to_relative_path(werk),
        "files": created_files,
        "backend": backend_id,
        "model": model,
    }


def _generate_via_llm(
    agent_id: str,
    description: str,
    chinese_name: str,
    backend_id: str,
    model: str,
) -> Optional[dict[str, str]]:
    prompt = f"""你是一个 Agent 生成器。请根据以下描述，为一个 AI Agent 生成完整的身份和配置文件。

Agent ID: {agent_id}
{"中文名: " + chinese_name if chinese_name else ""}
描述: {description}

请生成以下 4 个文件的内容，用 JSON 格式返回：

{{
  "IDENTITY.md": "身份定义（emoji, name, role, vibe 等）",
  "AGENTS.md": "Agent 的能力、工作流程、协作方式",
  "SOUL.md": "灵魂与行为准则",
  "USER.md": "用户信息（当前未知，写 placeholder）"
}}

要求：
1. IDENTITY.md 用中文，name 用中文，emoji 要匹配角色
2. AGENTS.md 详细描述能力和工作流程，包含核心职责、工作方法、协作方式
3. 所有内容用 Markdown 格式
4. 只返回 JSON，不要其他文字
"""

    try:
        content_buffer = ""
        for sse_json in stream_chat(get_coordinator_id(), prompt):
            evt = json.loads(sse_json)
            if evt["event"] == "thinking" and evt["data"].get("type") == "text":
                content_buffer += evt["data"].get("content", "")

        content_buffer = content_buffer.strip()
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content_buffer, re.DOTALL)
        if match:
            content_buffer = match.group(1)
        return json.loads(content_buffer)

    except Exception as e:
        print(f"[WARN] LLM 生成失败: {e}")
        return None


def _generate_template(agent_id: str, description: str, chinese_name: str = "") -> dict[str, str]:
    name = chinese_name or f"Agent-{agent_id}"
    return {
        "IDENTITY.md": f"""# Agent Identity

emoji: 🤖
name: {name}
role: AI 助手
description: {description}
""",
        "AGENTS.md": f"""# {name} - Agent 配置

## 核心定位
{description}

## 工作流程
1. 接收任务
2. 分析需求
3. 执行工作
4. 输出结果

## 协作方式
- 编排任务：内核下发 worker prompt；交卷用 submit_result 写 .response/{{interaction_id}}.response
- 团队任务由 Process 调度 DAG；与其他 Agent 不直接互读 .trigger
- 不直接调用外部脚本
""",
        "SOUL.md": f"""# {name} - 灵魂与行为准则

## 行为准则
1. 准确：确保输出正确可靠
2. 高效：快速响应，不浪费资源
3. 协作：积极与其他 Agent 配合
4. 透明：清晰说明工作状态

## 工作态度
- 主动解决问题
- 保持专业
- 持续改进
""",
        "USER.md": """# 用户信息

用户: 待配置
联系方式: 待配置
偏好: 待配置
""",
    }


def _extract_name_from_identity(content: str) -> str:
    patterns = [
        r"name[：:]\s*(\S+)",
        r"称呼[：:]\s*(\S+)",
    ]
    for p in patterns:
        m = re.search(p, content)
        if m:
            return m.group(1)
    return ""


def list_available_agent_ids() -> list[str]:
    if not WORKSPACES_DIR.is_dir():
        return []
    existing = set()
    for d in WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*"):
        if d.is_dir():
            existing.add(d.name[len(WORKSPACE_PREFIX):])
    return sorted(existing)


def suggest_agent_id(description: str) -> str:
    words = re.findall(r'[a-zA-Z]+', description)
    base = words[0].lower() if words else "agent"
    existing = list_available_agent_ids()
    if base not in existing:
        return base
    i = 1
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"
