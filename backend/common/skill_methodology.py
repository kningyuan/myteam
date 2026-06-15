"""Methodology skill chaining — 兼容层，委托 common.agent_skills。

历史：按 task_type+agent_id 隐式推导方法论；已废弃为主路径。
新代码请使用 agent_skills.get_agent_skill_ids / resolve_skill_paths。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.agent_skills import (
    SKILLS_DIR,
    get_agent_skill_ids,
    resolve_skill_paths,
    skill_file_path,
)

# 保留导出供旧测试引用；不再参与运行时主路径
TASK_DEFAULT_METHODOLOGY: dict[str, list[str]] = {
    "requirements": ["product-methodology"],
    "strategy": ["product-methodology"],
    "product-planning": ["product-methodology"],
    "product-research": ["product-methodology"],
    "acceptance-report": ["product-methodology"],
    "section-authoring": ["product-methodology"],
    "section-review": ["product-methodology"],
    "system-design": ["system-architecture-methodology"],
    "architecture-review": ["system-architecture-methodology"],
    "arch-research": ["system-architecture-methodology"],
    "code-testing": ["qa-methodology"],
    "test-plan": ["qa-methodology"],
}

AGENT_METHODOLOGY: dict[tuple[str, str], list[str]] = {
    ("code-writing", "developer"): ["backend-engineering-methodology"],
    ("code-writing", "frontend"): ["frontend-engineering-methodology"],
    ("code-deliverable", "developer"): ["backend-engineering-methodology"],
    ("code-deliverable", "frontend"): ["frontend-engineering-methodology"],
    ("code-review", "developer"): ["backend-engineering-methodology"],
    ("code-review", "frontend"): ["frontend-engineering-methodology"],
    ("architecture-review", "frontend"): [
        "frontend-architecture-methodology",
        "system-architecture-methodology",
    ],
    ("system-design", "frontend"): [
        "frontend-architecture-methodology",
        "system-architecture-methodology",
    ],
    ("architecture-review", "product"): ["product-methodology"],
    ("section-review", "product"): ["product-methodology"],
    ("section-review", "arch"): ["system-architecture-methodology"],
    ("requirements", "product"): ["product-methodology"],
    ("strategy", "product"): ["product-methodology"],
    ("acceptance-report", "product"): ["product-methodology"],
    ("code-testing", "qa"): ["qa-methodology"],
    ("test-plan", "qa"): ["qa-methodology"],
    ("code-review", "qa"): ["qa-methodology"],
    ("architecture-review", "qa"): ["qa-methodology"],
    ("decision-record", "main"): ["coordination-methodology"],
    ("section-review", "main"): ["coordination-methodology"],
    ("code-deployment", "main"): ["coordination-methodology"],
}


def resolve_methodology_skill_ids(
    task_type: str,
    agent_id: Optional[str] = None,
) -> list[str]:
    """兼容：返回 Agent 挂载的方法论 skill（不再按 task_type 分支）。"""
    _ = task_type
    return list(get_agent_skill_ids(agent_id or ""))


def methodology_skill_path(skill_id: str) -> Optional[Path]:
    return skill_file_path(skill_id)


def methodology_skill_paths(
    task_type: str,
    agent_id: Optional[str] = None,
) -> list[Path]:
    """兼容：Agent skills + 可选 task 执行 skill。"""
    return resolve_skill_paths(agent_id or "", task_type=task_type or None)
