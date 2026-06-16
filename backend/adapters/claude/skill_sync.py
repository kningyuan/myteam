"""Claude Code 工作区 Skill 同步 — 将 myteam 挂载的 Skill 注册到 .claude/skills/。"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from common.skill_catalog import SKILLS_DIR

CLAUDE_DIR_NAME = ".claude"
CLAUDE_SKILLS_DIR_NAME = "skills"
MANIFEST_NAME = ".myteam-skills.json"


def _skills_root(workspace: Path) -> Path:
    return workspace / CLAUDE_DIR_NAME / CLAUDE_SKILLS_DIR_NAME


def _manifest_path(workspace: Path) -> Path:
    return workspace / CLAUDE_DIR_NAME / MANIFEST_NAME


def _skill_source_dir(skill_id: str) -> Path | None:
    sid = (skill_id or "").strip()
    if not sid:
        return None
    src = (SKILLS_DIR / sid).resolve()
    if src.is_dir() and (src / "SKILL.md").is_file():
        return src
    return None


def _relative_symlink_target(src: Path, dest: Path) -> str:
    return os.path.relpath(src, dest.parent)


def _remove_skill_entry(entry: Path) -> None:
    if not entry.exists():
        return
    if entry.is_symlink():
        entry.unlink()
        return
    if entry.is_dir():
        shutil.rmtree(entry)
        return
    entry.unlink()


def _link_skill_dir(dest: Path, src: Path) -> None:
    if dest.exists() or dest.is_symlink():
        try:
            if dest.is_symlink() and dest.resolve() == src.resolve():
                return
        except OSError:
            pass
        _remove_skill_entry(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(_relative_symlink_target(src, dest))
        return
    except OSError:
        pass
    shutil.copytree(src, dest, dirs_exist_ok=True)


def sync_workspace_skills(workspace: str | Path, skill_ids: list[str]) -> dict:
    """把 skill_ids 同步到 workspace/.claude/skills/<id>/（符号链接或目录拷贝）。"""
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

    for entry in list(skills_root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name not in seen:
            _remove_skill_entry(entry)
            removed.append(entry.name)

    for sid in desired:
        src = _skill_source_dir(sid)
        if src is None:
            missing.append(sid)
            continue
        dest = skills_root / sid
        _link_skill_dir(dest, src)
        linked.append(sid)

    manifest = {
        "version": 1,
        "skill_ids": desired,
        "linked": linked,
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
        "missing": missing,
        "removed": removed,
    }
