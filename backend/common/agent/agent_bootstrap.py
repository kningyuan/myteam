"""Agent 工作区 bootstrap — team_config 时自动创建 workspace 与注册项。"""
from __future__ import annotations

import json

from common import paths

# 身份文件模板 — 优先从 YAML 加载，失败时回退到内置模板
# 正式模板请编辑 business/templates/identity_templates.yaml
IDENTITY_TEMPLATES: dict[str, str] = {}


def _load_identity_templates() -> dict[str, str]:
    """从 identity_templates.yaml 加载模板，失败时返回内置默认。"""
    fpath = paths.identity_templates_file()
    if fpath.exists():
        try:
            import yaml
            raw = yaml.safe_load(fpath.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "identity_templates" in raw:
                return raw["identity_templates"]
        except Exception:
            pass

    # 内置回退
    return {
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
- 编排任务：内核经 AgentPort 下发 prompt；交卷用 submit_result 写 .response/{{interaction_id}}.response
- 团队编排由 Process 调度 DAG，不与其他 Agent 直接互读 .trigger
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
    }


# 模块加载时初始化
IDENTITY_TEMPLATES.update(_load_identity_templates())


def auto_create_agent(agent_id: str, *, name: str = "", role: str = "worker",
                      description: str = "",
                      backend: str = "opencode", model: str = "") -> bool:
    """自动创建 agent 工作目录、身份文件和注册项（纯模板，不调用 LLM）。"""
    from common.agent.agent_model import system_default_backend

    if not (model or "").strip():
        model = ""  # 新建 agent 默认跟随设置页，不写入硬编码 model
    if not (backend or "").strip():
        backend = system_default_backend()
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