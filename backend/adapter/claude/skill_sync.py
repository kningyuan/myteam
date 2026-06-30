"""Claude Code 工作区 Skill 同步 — 将 myteam 挂载的 Skill 注册到 .claude/skills/。"""

from __future__ import annotations

import json
from pathlib import Path

from common.skill.skill_link import link_skill_dir, remove_skill_entry, resolve_skill_source_dir

CLAUDE_DIR_NAME = ".claude"
CLAUDE_SKILLS_DIR_NAME = "skills"
MANIFEST_NAME = ".myteam-skills.json"


def _skills_root(workspace: Path) -> Path:
    return workspace / CLAUDE_DIR_NAME / CLAUDE_SKILLS_DIR_NAME


def _manifest_path(workspace: Path) -> Path:
    return workspace / CLAUDE_DIR_NAME / MANIFEST_NAME


def sync_workspace_skills(workspace: str | Path, skill_ids: list[str]) -> dict:
    """把 skill_ids 同步到 workspace/.claude/skills/<id>/（目录软链，非仅 SKILL.md）。"""
    ws = Path(workspace).resolve()
    if not ws.is_dir():
        return {"success": False, "error": f"workspace 不存在: {ws}"}

    desired = []
    seen: set[str] = set()
    for raw in skill_ids:
        sid = (raw or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            desired.append(sid)

    skills_root = _skills_root(ws)
    skills_root.mkdir(parents=True, exist_ok=True)

    linked: list[str] = []
    missing: list[str] = []
    removed: list[str] = []
    modes: dict[str, str] = {}

    for entry in list(skills_root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name not in seen:
            remove_skill_entry(entry)
            removed.append(entry.name)

    for sid in desired:
        src = resolve_skill_source_dir(sid)
        if src is None:
            missing.append(sid)
            continue
        dest = skills_root / sid
        modes[sid] = link_skill_dir(dest, src)
        linked.append(sid)

    manifest = {
        "version": 2,
        "skill_ids": desired,
        "linked": linked,
        "modes": modes,
        "missing": missing,
        "removed": removed,
    }
    _manifest_path(ws).parent.mkdir(parents=True, exist_ok=True)
    _manifest_path(ws).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "success": True,
        "workspace": str(ws),
        "linked": linked,
        "modes": modes,
        "missing": missing,
        "removed": removed,
    }
