#!/usr/bin/env python3
"""从 business-roster.json 读取角色定义，为每个 agent workspace 生成身份文件。

生成 4 个文件：IDENTITY.md / SOUL.md / AGENTS.md / MEMORY.md
幂等：已存在且非空的文件跳过，不覆盖用户手动编辑的内容。
roster 中未定义但 workspace 已存在的 agent（如 test-harness-agent）用默认模板生成。

运行：PYTHONPATH=backend python scripts/bootstrap_agent_identity.py
"""
from __future__ import annotations

import json
import sys

from common.paths import MYTEAM_ROOT, WORKSPACES_DIR, WORKSPACE_PREFIX

# 角色名册权威源
ROSTER_FILE = MYTEAM_ROOT / "business" / "templates" / "business-roster.json"

# 需要生成的 4 个身份文件（USER.md 由其他机制管理，不在此列）
IDENTITY_FILES = ("IDENTITY.md", "SOUL.md", "AGENTS.md", "MEMORY.md")


def load_roster() -> dict:
    """读取角色名册，返回 {agent_id: agent_def}。"""
    if not ROSTER_FILE.exists():
        print(f"[警告] 找不到 roster 文件：{ROSTER_FILE}", file=sys.stderr)
        return {}
    raw = json.loads(ROSTER_FILE.read_text(encoding="utf-8"))
    return raw.get("agents", {}) if isinstance(raw, dict) else {}


def list_existing_workspaces() -> list[tuple[str, "Path"]]:
    """枚举已存在的 workspace 目录，返回 [(agent_id, dir)]。"""
    result = []
    if not WORKSPACES_DIR.exists():
        return result
    from pathlib import Path

    for d in sorted(WORKSPACES_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if not name.startswith(WORKSPACE_PREFIX):
            continue
        agent_id = name[len(WORKSPACE_PREFIX):]
        if not agent_id:
            continue  # 跳过空 agent_id（如 workspace-）
        result.append((agent_id, d))
    return result


def default_agent(agent_id: str) -> dict:
    """roster 中未定义的 agent 使用默认模板。"""
    return {
        "name": agent_id,
        "role": "worker",
        "description": "（roster 中未定义，使用默认模板）",
        "capabilities": [],
        "task_types": [],
        "boundaries": {"does": [], "does_not": []},
    }


def _bullet_list(items, fallback="（未声明）") -> str:
    """列表转 markdown 无序列表，空则用 fallback。"""
    if items:
        return "\n".join(f"- {x}" for x in items)
    return f"- {fallback}"


def render_identity(agent: dict) -> str:
    """生成 IDENTITY.md — 身份定义。"""
    name = agent.get("name", "")
    description = agent.get("description", "")
    capabilities = agent.get("capabilities", []) or []
    task_types = agent.get("task_types", []) or []
    boundaries = agent.get("boundaries", {}) or {}
    does = boundaries.get("does", []) or []
    does_not = boundaries.get("does_not", []) or []

    caps = _bullet_list(capabilities)
    tt = _bullet_list(task_types, fallback="由 workflow 动态分配") if not task_types else _bullet_list(task_types)
    does_lines = _bullet_list(does)
    does_not_lines = _bullet_list(does_not)

    return f"""# {name}

## 角色定位
{description}

## 核心能力
{caps}

## 任务类型
{tt}

## 边界
**应做：**
{does_lines}

**不应做：**
{does_not_lines}
"""


def render_soul(agent: dict) -> str:
    """生成 SOUL.md — 人格风格。"""
    name = agent.get("name", "")
    role = agent.get("role", "worker")
    if role == "coordinator":
        collab = "- 统筹全局，不越俎代庖具体实现"
    else:
        collab = "- 专注本职，按时高质量交付"

    return f"""# {name} 的工作风格

## 沟通原则
- 简洁直接，先结论后过程
- 用中文沟通，技术术语保留英文
- 不确定时主动澄清，不臆测

## 工作态度
- 对交付质量负责，输出即可用的成品
- 主动暴露风险和依赖，不隐瞒问题
- 遇到阻塞时给出替代方案，而非停下

## 协作风格
{collab}
"""


def render_agents_guide(agent: dict) -> str:
    """生成 AGENTS.md — 工作指引。"""
    name = agent.get("name", "")
    return f"""# {name} 工作指引

## 启动检查
1. 确认任务意图和交付物要求
2. 检查相关 Skill 和知识库引用
3. 确认 task_type 和验收标准

## 执行流程
1. 理解 intent，规划执行步骤
2. 调用必要的方法论和经验
3. 产出交付物，确保格式符合 task_type 规范
4. 填写 ledger（summary/lesson/pitfalls/sources）

## 交付标准
- 交付物内容完整，无占位符
- 格式符合 task_type 的 required_sections
- ledger 记录关键决策和踩坑
"""


def render_memory(agent: dict) -> str:
    """生成 MEMORY.md — 工作记忆（初始空模板）。"""
    name = agent.get("name", "")
    return f"""# {name} 工作记忆

## 经验沉淀
（随任务执行自动积累）

## 常见踩坑
（随任务执行自动积累）

## 有效做法
（随任务执行自动积累）
"""


# 文件名 → 渲染函数
RENDERERS = {
    "IDENTITY.md": render_identity,
    "SOUL.md": render_soul,
    "AGENTS.md": render_agents_guide,
    "MEMORY.md": render_memory,
}


def should_write(path) -> bool:
    """文件不存在或内容为空（仅空白）时才写入；非空则跳过以保护手动编辑。"""
    if not path.exists():
        return True
    return not path.read_text(encoding="utf-8").strip()


def main() -> int:
    roster = load_roster()
    workspaces = list_existing_workspaces()
    if not workspaces:
        print("[完成] 没有找到任何 workspace 目录")
        return 0

    total_written = 0
    for agent_id, ws_dir in workspaces:
        in_roster = agent_id in roster
        agent = roster.get(agent_id) or default_agent(agent_id)
        source = "roster" if in_roster else "默认模板"
        written = []
        skipped = []
        for fname in IDENTITY_FILES:
            fpath = ws_dir / fname
            if should_write(fpath):
                content = RENDERERS[fname](agent)
                fpath.write_text(content, encoding="utf-8")
                written.append(fname)
                total_written += 1
            else:
                skipped.append(fname)
        if written:
            print(f"[写入] {agent_id}（来源：{source}）→ 生成：{', '.join(written)}"
                  + (f"；跳过：{', '.join(skipped)}" if skipped else ""))
        else:
            print(f"[跳过] {agent_id}（4 个文件均已存在且非空）")

    print(f"\n共生成 {total_written} 个文件，覆盖 {len(workspaces)} 个 workspace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
