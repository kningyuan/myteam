"""Skill 目录挂载 — 符号链接优先，禁止只复制 SKILL.md。

- business/skills/<id>：生产 skill 真相目录；vendor skill（如 browse）软链到上游工具包
- .cursor/skills/<id>：软链到 business/skills/<id>，供 Cursor 发现
- workspace/.claude|.opencode/skills/<id>：软链到 business/skills/<id>（或 vendor 解析结果）
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, Optional

from common.paths import MYTEAM_ROOT
from common.skill_catalog import SKILLS_DIR

OFFICECLI_SKILLS_ROOT = "~/skill/OfficeCLI/skills"

OFFICECLI_VENDOR_SKILL_IDS = (
    "officecli",
    "officecli-docx",
    "officecli-pptx",
    "officecli-xlsx",
    "officecli-pitch-deck",
    "officecli-academic-paper",
    "officecli-data-dashboard",
    "officecli-financial-model",
    "officecli-word-form",
    "morph-ppt",
    "morph-ppt-3d",
)


def _officecli_vendor_sources(skill_id: str) -> list[str]:
    return [f"{OFFICECLI_SKILLS_ROOT}/{skill_id}"]


# vendor skill：business/skills/<id> 应为指向上游目录的软链，而非 stub SKILL.md
VENDOR_SKILL_SOURCES: dict[str, list[str]] = {
    "browse": [
        "~/.claude/skills/gstack/browse",
        "~/.cursor/skills/gstack-browse",
        "~/.claude/skills/browse",
    ],
    **{sid: _officecli_vendor_sources(sid) for sid in OFFICECLI_VENDOR_SKILL_IDS},
}

CURSOR_SKILLS_DIR = MYTEAM_ROOT / ".cursor" / "skills"
# 仅存在于 .cursor/skills、不在 business/skills 的 Cursor 专用条目
CURSOR_ONLY_SKILLS = frozenset({"myteam-usage"})


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def relative_symlink_target(src: Path, dest: Path) -> str:
    return os.path.relpath(src, dest.parent)


def remove_skill_entry(entry: Path) -> None:
    if not entry.exists() and not entry.is_symlink():
        return
    if entry.is_symlink():
        entry.unlink()
        return
    if entry.is_dir():
        shutil.rmtree(entry)
        return
    entry.unlink()


def link_skill_dir(dest: Path, src: Path, *, allow_copy_fallback: bool = False) -> str:
    """将 dest 指向 src 目录。默认仅软链；allow_copy_fallback 供测试/无权限环境。"""
    src = Path(src)
    if not src.exists() and not src.is_symlink():
        raise ValueError(f"skill 源目录不存在：{src}")
    if not (src / "SKILL.md").is_file():
        raise ValueError(f"skill 源缺少 SKILL.md：{src}")
    # vendor 锚点为 business/skills 下的软链时，不 follow，保持挂载链
    link_target = src if src.is_symlink() else src.resolve()
    if (dest.exists() or dest.is_symlink()) and not dest.is_dir() and not dest.is_symlink():
        remove_skill_entry(dest)
    if dest.exists() or dest.is_symlink():
        expected = relative_symlink_target(link_target, dest)
        try:
            if dest.is_symlink() and os.readlink(dest) == expected:
                return "linked"
            if dest.resolve() == link_target.resolve():
                return "linked"
        except OSError:
            pass
        remove_skill_entry(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(relative_symlink_target(link_target, dest))
        return "linked"
    except OSError:
        if not allow_copy_fallback:
            raise
        shutil.copytree(link_target.resolve(), dest, dirs_exist_ok=True)
        return "copied"


def business_skill_anchor(skill_id: str) -> Path:
    """business/skills/<id>/ — skill 目录始终扁平，分类仅元数据。"""
    return SKILLS_DIR / (skill_id or "").strip()


def _legacy_nested_skill_dir(skill_id: str) -> Optional[Path]:
    """只读兼容：迁移前嵌套在 <category>/<id>/ 下的旧路径。"""
    sid = (skill_id or "").strip()
    if not sid or not SKILLS_DIR.is_dir():
        return None
    for parent in sorted(SKILLS_DIR.iterdir()):
        if not parent.is_dir() or parent.name.startswith("."):
            continue
        nested = parent / sid
        if nested.is_dir() and (nested / "SKILL.md").is_file():
            return nested
    return None


def _migrate_flat_vendor_anchor(skill_id: str, dest: Path) -> None:
    """删除与 dest 重复的其它挂载锚点（扁平布局下通常无操作）。"""
    sid = (skill_id or "").strip()
    legacy = _legacy_nested_skill_dir(sid)
    if legacy and legacy != dest and (legacy.exists() or legacy.is_symlink()):
        remove_skill_entry(legacy)


def iter_business_skill_dir_names(business_root: Path = SKILLS_DIR) -> list[str]:
    """枚举 business/skills 下顶层含 SKILL.md 的 skill 目录。"""
    if not business_root.is_dir():
        return []
    names: list[str] = []
    for p in sorted(business_root.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if p.name == "categories.yaml":
            continue
        if (p / "SKILL.md").is_file():
            names.append(p.name)
    return names


def resolve_vendor_source(skill_id: str) -> Optional[Path]:
    sid = (skill_id or "").strip()
    for raw in VENDOR_SKILL_SOURCES.get(sid, []):
        p = _expand(raw)
        if p.is_dir() and (p / "SKILL.md").is_file():
            return p
    return None


def resolve_skill_source_dir(skill_id: str) -> Optional[Path]:
    """解析可挂载的 skill 源目录（business/skills 或 vendor 上游）。"""
    sid = (skill_id or "").strip()
    if not sid:
        return None

    local = business_skill_anchor(sid)
    if local.is_dir() and (local / "SKILL.md").is_file():
        return local if local.is_symlink() else local.resolve()

    nested = _legacy_nested_skill_dir(sid)
    if nested is not None:
        return nested if nested.is_symlink() else nested.resolve()

    vendor = resolve_vendor_source(sid)
    if vendor is not None:
        return vendor

    return None


def _is_stub_skill_dir(path: Path) -> bool:
    """仅含 SKILL.md、无脚本/子目录的占位目录（应换成 vendor 软链）。"""
    if not path.is_dir() or path.is_symlink():
        return False
    entries = [e for e in path.iterdir() if e.name != ".DS_Store"]
    if len(entries) != 1 or entries[0].name != "SKILL.md":
        return False
    return sid_has_vendor(path.name)


def sid_has_vendor(skill_id: str) -> bool:
    return skill_id in VENDOR_SKILL_SOURCES


def ensure_vendor_skill_link(skill_id: str) -> dict:
    """确保 business/skills 下 vendor skill 为上游软链（替换仅 SKILL.md 的 stub）。"""
    sid = (skill_id or "").strip()
    dest = business_skill_anchor(sid)
    src = resolve_vendor_source(sid)
    if src is None:
        if dest.is_dir() and (dest / "SKILL.md").is_file():
            return {"skill_id": sid, "status": "present", "path": str(dest.resolve())}
        return {"skill_id": sid, "status": "missing_upstream", "error": "未找到 vendor skill 源目录"}

    if dest.is_symlink():
        try:
            if dest.resolve() == src:
                _migrate_flat_vendor_anchor(sid, dest)
                return {"skill_id": sid, "status": "linked", "target": str(src)}
        except OSError:
            pass
    elif dest.is_dir() and not _is_stub_skill_dir(dest):
        if (dest / "SKILL.md").is_file():
            _migrate_flat_vendor_anchor(sid, dest)
            return {"skill_id": sid, "status": "local", "path": str(dest.resolve())}

    remove_skill_entry(dest)
    mode = link_skill_dir(dest, src)
    _migrate_flat_vendor_anchor(sid, dest)
    return {"skill_id": sid, "status": mode, "target": str(src)}


def ensure_all_vendor_skill_links() -> dict:
    results = [ensure_vendor_skill_link(sid) for sid in sorted(VENDOR_SKILL_SOURCES)]
    ok = all(r.get("status") in {"linked", "present", "local"} for r in results)
    return {"success": ok, "results": results}


def sync_cursor_skill_links(
    *,
    skill_ids: Optional[Iterable[str]] = None,
    cursor_root: Path = CURSOR_SKILLS_DIR,
    business_root: Path = SKILLS_DIR,
) -> dict:
    """将 .cursor/skills/<id> 软链到 business/skills/<id>。"""
    if skill_ids is None:
        skill_ids = iter_business_skill_dir_names(business_root)
    desired = {sid for sid in skill_ids if sid and sid not in CURSOR_ONLY_SKILLS}
    cursor_root.mkdir(parents=True, exist_ok=True)

    linked: list[str] = []
    missing: list[str] = []
    removed: list[str] = []

    for entry in list(cursor_root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name in CURSOR_ONLY_SKILLS:
            continue
        if entry.name not in desired:
            remove_skill_entry(entry)
            removed.append(entry.name)

    for sid in sorted(desired):
        src = business_skill_anchor(sid)
        if not src.is_dir() or not (src / "SKILL.md").is_file():
            missing.append(sid)
            continue
        dest = cursor_root / sid
        try:
            link_skill_dir(dest, src)
            linked.append(sid)
        except OSError:
            missing.append(sid)

    return {
        "success": not missing,
        "linked": linked,
        "missing": missing,
        "removed": removed,
    }
