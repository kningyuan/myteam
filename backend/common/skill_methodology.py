"""Methodology skill chaining — kernel execute 提示词自动注入专业方法论。

除 business/skills/<task_type>/SKILL.md 外，按 task_type + agent_id 追加
business/skills/<methodology-id>/SKILL.md，保证 worker 不凭想象交付。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.paths import MYTEAM_ROOT

SKILLS_DIR = MYTEAM_ROOT / "business" / "skills"

# task_type → 默认方法论 skill 目录名（与 agent 无关时）
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

# (task_type, agent_id) → 覆盖/追加（agent 专责时优先于或替换默认）
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
    """返回应注入的方法论 skill id 列表（有序、去重）。"""
    if not task_type:
        return []
    aid = (agent_id or "").strip()
    key = (task_type, aid)
    if aid and key in AGENT_METHODOLOGY:
        ids = list(AGENT_METHODOLOGY[key])
    else:
        ids = list(TASK_DEFAULT_METHODOLOGY.get(task_type, []))
    seen: set[str] = set()
    out: list[str] = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def methodology_skill_path(skill_id: str) -> Optional[Path]:
    p = SKILLS_DIR / skill_id / "SKILL.md"
    return p if p.is_file() else None


def methodology_skill_paths(
    task_type: str,
    agent_id: Optional[str] = None,
) -> list[Path]:
    """仅返回磁盘上存在的 SKILL.md 路径。"""
    paths: list[Path] = []
    for sid in resolve_methodology_skill_ids(task_type, agent_id):
        p = methodology_skill_path(sid)
        if p is not None:
            paths.append(p)
    return paths
