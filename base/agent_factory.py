"""
Agent Factory - 一键创建 Agent
根据描述自动生成工作目录和能力文件
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from agent_chat import WORKSPACES_DIR, WORKSPACE_PREFIX
from agent_chat import get_agent_backend_config, set_agent_backend_config
from backends import registry

LOCAL_DIR = Path(__file__).parent


def generate_agent(
    agent_id: str,
    description: str,
    backend_id: str = "opencode",
    model: str = "",
    chinese_name: str = "",
    use_existing_agent_for_gen: bool = True,
) -> dict:
    """
    根据描述一键创建 Agent

    Args:
        agent_id: Agent ID（英文，用于标识）
        description: 对这个 Agent 的描述（它做什么工作、有什么能力）
        backend_id: 使用的 CLI 后端
        model: 使用的模型（空字符串则用后端默认）
        chinese_name: 中文名（空则自动从描述生成）
        use_existing_agent_for_gen: 是否用现有 Agent LLM 生成 identity 文件

    Returns:
        dict: 创建结果，包含 workspace 路径和生成的文件列表
    """
    werk = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"

    if werk.exists():
        return {"success": False, "error": f"Agent '{agent_id}' 的工作目录已存在"}

    # 确定模型
    if not model:
        backend = registry.get(backend_id)
        model = backend.get_default_model() if backend else ""

    # 生成 identity 文件内容
    if use_existing_agent_for_gen:
        files_content = _generate_via_llm(agent_id, description, chinese_name, backend_id, model)
    else:
        files_content = _generate_template(agent_id, description, chinese_name)

    if not files_content:
        files_content = _generate_template(agent_id, description, chinese_name)

    # 创建目录和文件
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

        # 从 IDENTITY.md 提取中文名（如果未提供）
        if filename == "IDENTITY.md" and not chinese_name:
            chinese_name = _extract_name_from_identity(content)

    # 注册到配置
    set_agent_backend_config(agent_id, backend_id, model)

    # 更新 multi_agent_manager 缓存（下次启动生效）
    return {
        "success": True,
        "agent_id": agent_id,
        "chinese_name": chinese_name,
        "workspace": str(werk),
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
    """用 LLM 根据描述自动生成 Agent identity 文件"""
    prompt = f"""你是一个 Agent 生成器。请根据以下描述，为一个 AI Agent 生成完整的身份和配置文件。

Agent ID: {agent_id}
{"中文名: " + chinese_name if chinese_name else ""}
描述: {description}

请生成以下 6 个文件的内容，用 JSON 格式返回：

{{
  "IDENTITY.md": "身份定义（emoji, name, role, vibe 等）",
  "AGENTS.md": "Agent 的能力、工作流程、协作方式",
  "SOUL.md": "灵魂与行为准则",
  "USER.md": "用户信息（当前未知，写 placeholder）",
  "TOOLS.md": "可用的工具描述",
  "HEARTBEAT.md": "心跳检查项"
}}

要求：
1. IDENTITY.md 用中文，name 用中文，emoji 要匹配角色
2. AGENTS.md 详细描述能力和工作流程，包含核心职责、工作方法、协作方式
3. 所有内容用 Markdown 格式
4. 只返回 JSON，不要其他文字
"""

    try:
        from agent_chat import stream_chat
        content_buffer = ""
        for sse_json in stream_chat("main", prompt):
            evt = json.loads(sse_json)
            if evt["event"] == "thinking" and evt["data"].get("type") == "text":
                content_buffer += evt["data"]["content"]

        # 解析 JSON
        content_buffer = content_buffer.strip()
        # 尝试从代码块提取
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content_buffer, re.DOTALL)
        if match:
            content_buffer = match.group(1)
        return json.loads(content_buffer)

    except Exception as e:
        print(f"[WARN] LLM 生成失败: {e}")
        return None


def _generate_template(agent_id: str, description: str, chinese_name: str = "") -> dict[str, str]:
    """用模板生成基本的 Agent 文件"""
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
- 通过 .trigger/.response 文件系统通信
- 返回 JSON 格式的 structured response
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
        "TOOLS.md": """# 可用工具

## 基础工具
- 文件读写：读取和写入工作目录中的文件
- 代码执行：执行 shell 命令
- 网络请求：进行 HTTP 请求

## 注意事项
- 所有操作在工作目录内进行
- 遵守安全规范
- 记录操作日志
""",
        "HEARTBEAT.md": """# 心跳检查项

## 每日检查
- [ ] 工作目录是否正常
- [ ] 身份文件是否完整
- [ ] 工具是否可用

## 异常处理
- 文件缺失：重新生成
- 通信失败：等待重试
- 任务超时：报告状态
""",
    }


def _extract_name_from_identity(content: str) -> str:
    """从 IDENTITY.md 提取中文名"""
    import re
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
    """列出可用的 agent_id（基于现有命名规则）"""
    existing = set()
    for d in WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*"):
        if d.is_dir():
            existing.add(d.name[len(WORKSPACE_PREFIX):])
    return sorted(existing)


def suggest_agent_id(description: str) -> str:
    """根据描述建议 agent_id"""
    # 简单规则：取前两个英文/拼音词
    import re
    words = re.findall(r'[a-zA-Z]+', description)
    if words:
        base = words[0].lower()
    else:
        base = "agent"
    existing = list_available_agent_ids()
    if base not in existing:
        return base
    i = 1
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"