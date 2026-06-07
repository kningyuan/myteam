#!/usr/bin/env python3
"""Agent 工作区 bootstrap — team_config 时自动创建 workspace 与注册项。"""
from __future__ import annotations

import json

from common import paths

IDENTITY_TEMPLATES = {
    "IDENTITY.md": """# Agent Identity

emoji: 🤖
name: {name}
role: {role}
description: {description}
""",
    "AGENTS.md": """# {name} - Agent 配置

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
""",
    "SOUL.md": """# {name} - 灵魂与行为准则

## 行为准则
1. 准确：确保输出正确可靠
2. 高效：快速响应，不浪费资源
3. 协作：积极与其他 Agent 配合
4. 透明：清晰说明工作状态
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
""",
    "HEARTBEAT.md": """# 心跳检查项

## 每日检查
- [ ] 工作目录是否正常
- [ ] 身份文件是否完整
- [ ] 工具是否可用
""",
}


def auto_create_agent(agent_id: str, *, name: str = "", role: str = "worker",
                      description: str = "",
                      backend: str = "opencode", model: str = "") -> bool:
    """自动创建 agent 工作目录、身份文件和注册项（纯模板，不调用 LLM）。"""
    ws_dir = paths.WORKSPACES_DIR / f"{paths.WORKSPACE_PREFIX}{agent_id}"
    if ws_dir.exists():
        return True

    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / ".trigger").mkdir(exist_ok=True)
    (ws_dir / ".response").mkdir(exist_ok=True)

    display_name = name or agent_id
    desc = description or f"自动创建的 agent：{agent_id}"
    for fname, template in IDENTITY_TEMPLATES.items():
        content = template.format(name=display_name, role=role, description=desc)
        (ws_dir / fname).write_text(content.strip() + "\n", encoding="utf-8")

    paths.AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if paths.AGENTS_CONFIG_FILE.exists():
        try:
            cfg = json.loads(paths.AGENTS_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg[agent_id] = {"backend": backend, "model": model, "extra": {}}
    paths.AGENTS_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    reg = {"version": "1.0", "agents": {}}
    if paths.AGENTS_REGISTRY_FILE.exists():
        try:
            reg = json.loads(paths.AGENTS_REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    reg.setdefault("agents", {})
    pre = reg["agents"].get(agent_id) or {}
    reg["agents"][agent_id] = {
        "name": pre.get("name") or display_name,
        "role": pre.get("role") or role,
        "description": pre.get("description") or desc,
        "capabilities": list(pre.get("capabilities") or []),
        "task_types": list(pre.get("task_types") or []),
    }
    paths.AGENTS_REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")

    return True


# 兼容旧私有名
_auto_create_agent = auto_create_agent
