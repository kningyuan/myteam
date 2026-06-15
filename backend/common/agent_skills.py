"""Agent Skill 解析 — 严格模式：仅 registry 显式配置的 Skill 生效。

- ``task_types`` = 可接哪些交付物（workflow 派工 / Gate）
- ``skills`` = Agent 允许使用的 Skill id 列表（私聊 / 群聊 / 圆桌 / execute 统一注入）
- 无默认兜底、无 task_type 隐式追加；未配置则 Agent 不挂载任何 Skill
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from common.agent_registry import get_agent_info
from common.paths import MYTEAM_ROOT, workspace_dir
from common.skill_catalog import get_skill_library_entry

SKILLS_DIR = MYTEAM_ROOT / "business" / "skills"

_SKILLS_MD_HEADER = "## 已挂载 Skill"
_SKILLS_MD_NOTE = (
    "> 本节由系统根据 `agents_registry.json` 自动同步，请勿手工编辑列表。"
)
_SKILLS_MD_SECTION_RE = re.compile(
    rf"^{re.escape(_SKILLS_MD_HEADER)}\s*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def skill_file_path(skill_id: str) -> Optional[Path]:
    entry = get_skill_library_entry(skill_id)
    if not entry:
        return None
    p = MYTEAM_ROOT / entry["path"]
    return p if p.is_file() else None


def get_agent_skill_ids(agent_id: str) -> list[str]:
    """仅返回 agents_registry.json 中显式配置的 skills（可为空）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return []
    info = get_agent_info(aid) or {}
    configured = info.get("skills")
    if not isinstance(configured, list):
        return []
    return _dedupe([str(s).strip() for s in configured if str(s).strip()])


def resolve_skill_ids(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> list[str]:
    """严格：仅 Agent 配置的 skills；task_type 不参与解析。"""
    _ = task_type
    return list(get_agent_skill_ids(agent_id))


def resolve_skill_paths(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> list[Path]:
    paths: list[Path] = []
    for sid in resolve_skill_ids(agent_id, task_type=task_type):
        p = skill_file_path(sid)
        if p is not None:
            paths.append(p)
    return paths


def build_skill_context(
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> str:
    """拼入 system / worker prompt 的 Skill 块。"""
    _ = task_type
    ids = get_agent_skill_ids(agent_id)
    if not ids:
        return (
            "【Skill 边界】本 Agent 未挂载任何 Skill。"
            "禁止查阅或沿用 business/skills 下其他目录中的 SKILL.md。"
        )

    paths = [p for sid in ids if (p := skill_file_path(sid))]
    missing = [sid for sid in ids if skill_file_path(sid) is None]

    lines: list[str] = [
        "【已挂载 Skill】仅允许使用下列 Skill（禁止查阅未列出的其他 skill 目录）：",
    ]
    for sid, p in zip(ids, [skill_file_path(s) for s in ids]):
        if p:
            lines.append(f"  - {sid} → {p}")
    if missing:
        lines.append(f"  （配置中存在但文件缺失：{', '.join(missing)}）")
    lines.append("")
    lines.append(
        "执行任务时必须先 Read 上述 SKILL.md，且不得使用未在上述列表中的 Skill 或臆造流程。"
    )
    return "\n".join(lines)


def append_skill_instructions(
    lines: list[str],
    agent_id: str,
    *,
    task_type: Optional[str] = None,
) -> None:
    block = build_skill_context(agent_id, task_type=task_type)
    if block:
        lines.append(block)


def render_agents_md_skills_section(agent_id: str) -> str:
    """生成 AGENTS.md 中「已挂载 Skill」段落（与 registry 一致）。"""
    ids = get_agent_skill_ids(agent_id)
    lines = [_SKILLS_MD_HEADER, "", _SKILLS_MD_NOTE, ""]
    if not ids:
        lines.append("本 Agent 未挂载任何 Skill。")
        return "\n".join(lines)

    for sid in ids:
        entry = get_skill_library_entry(sid)
        rel = entry["path"] if entry else f"business/skills/{sid}/SKILL.md"
        lines.append(f"- `{sid}` → {rel}")
    lines.append("")
    lines.append("执行任务时须 Read 上述 SKILL.md；禁止使用未列出的 Skill。")
    return "\n".join(lines)


def sync_agents_md_skills_section(agent_id: str) -> bool:
    """将 registry 中的 skills 写入 workspace AGENTS.md（幂等）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return False
    ws = workspace_dir(aid)
    if not ws.is_dir():
        return False

    section = render_agents_md_skills_section(aid) + "\n"
    agents_md = ws / "AGENTS.md"

    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8")
        if _SKILLS_MD_SECTION_RE.search(text):
            text = _SKILLS_MD_SECTION_RE.sub(section, text)
        else:
            text = text.rstrip() + "\n\n" + section
    else:
        info = get_agent_info(aid) or {}
        name = info.get("name") or aid
        text = f"# {name} - Agent 配置\n\n{section}"

    agents_md.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return True


def _dedupe(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sid in ids:
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out
