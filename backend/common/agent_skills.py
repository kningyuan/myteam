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
        "",
    ]
    ws = workspace_dir(agent_id)
    for sid in ids:
        entry = get_skill_library_entry(sid) or {}
        name = (entry.get("name") or sid).strip()
        desc = (entry.get("description") or "").strip()
        p = skill_file_path(sid)
        if p:
            oc = ws / ".opencode" / "skills" / sid / "SKILL.md"
            cc = ws / ".claude" / "skills" / sid / "SKILL.md"
            head = f"- {sid}（{name}）"
            if desc:
                head += f"：{desc}"
            else:
                head += "（无 frontmatter description；执行前须 Read SKILL.md 了解用途）"
            lines.append(head)
            lines.append(f"    SKILL.md：{p}")
            lines.append(f"    OpenCode：{oc}")
            lines.append(f"    Claude Code：{cc}")
    if missing:
        lines.append(f"（配置中存在但文件缺失：{', '.join(missing)}）")
    lines.extend(
        [
            "",
            "先根据上表 description 判断是否需要某 Skill；若需要，须 Read 对应 SKILL.md 并按其流程执行。",
            "禁止把 ~/.claude/skills 或全局 skill 当作本 Agent 可用 skill。",
        ]
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


def _normalize_agents_md_after_strip(text: str) -> str:
    """去掉多余空行，保持文件末尾单个换行。"""
    import re as _re

    cleaned = _re.sub(r"\n{3,}", "\n\n", text.strip())
    return cleaned + "\n" if cleaned else ""


def strip_agents_md_skills_section(agent_id: str) -> bool:
    """从 workspace AGENTS.md 移除历史自动同步的「已挂载 Skill」节（幂等）。"""
    aid = (agent_id or "").strip()
    if not aid:
        return False
    agents_md = workspace_dir(aid) / "AGENTS.md"
    if not agents_md.is_file():
        return False
    text = agents_md.read_text(encoding="utf-8")
    if not _SKILLS_MD_SECTION_RE.search(text):
        return False
    text = _SKILLS_MD_SECTION_RE.sub("", text)
    agents_md.write_text(_normalize_agents_md_after_strip(text), encoding="utf-8")
    return True


def _dedupe(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sid in ids:
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out
