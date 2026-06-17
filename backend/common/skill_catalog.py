"""Skill 库 — 扫描 business/skills 下 Skill（生产 + auto-* 草案，单一出处）。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from common.paths import MYTEAM_ROOT
from common.skill_display_names import (
    resolve_skill_display_description,
    resolve_skill_display_name,
)

SKILLS_DIR = MYTEAM_ROOT / "business" / "skills"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_FILE_KIND = {
    ".md": "doc",
    ".yaml": "config",
    ".yml": "config",
    ".sh": "script",
    ".py": "script",
    ".ts": "script",
    ".js": "script",
}


def _stringify_frontmatter_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        raw = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        raw = None
    if isinstance(raw, dict):
        return {
            str(k): _stringify_frontmatter_value(v)
            for k, v in raw.items()
            if v is not None and str(k).strip()
        }
    # 退化：仅解析单行 key: value（兼容极简 frontmatter）
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _is_production_skill_dir(name: str) -> bool:
    return bool(name) and not name.startswith("auto-")


def _skill_dir(skill_id: str) -> Optional[Path]:
    from common.skill_link import resolve_skill_source_dir

    return resolve_skill_source_dir(skill_id)


def _strip_frontmatter(text: str) -> str:
    m = _FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


def _slugify(title: str, index: int) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", title.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or f"section-{index}"


def _parse_sections(body: str) -> list[dict]:
    """按 ## / ### 分章；# 标题与文首引言单独成节。"""
    lines = body.splitlines()
    sections: list[dict] = []
    preamble: list[str] = []
    current_title = ""
    current_level = 0
    current_lines: list[str] = []
    idx = 0
    seen_heading = False

    def flush() -> None:
        nonlocal idx
        if not current_title:
            return
        content = "\n".join(current_lines).strip()
        prefix = "#" * current_level + " "
        sections.append({
            "id": _slugify(current_title, idx),
            "title": current_title,
            "level": current_level,
            "content": f"{prefix}{current_title}\n\n{content}".strip() if content else f"{prefix}{current_title}",
        })
        idx += 1

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            if level == 1:
                if not seen_heading:
                    preamble.append(line)
                continue
            seen_heading = True
            flush()
            current_level = level
            current_title = m.group(2).strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)
        elif not seen_heading:
            preamble.append(line)

    flush()

    intro = "\n".join(preamble).strip()
    if intro:
        sections.insert(0, {
            "id": "overview",
            "title": "概述",
            "level": 1,
            "content": intro,
        })

    if not sections and body.strip():
        sections.append({
            "id": "overview",
            "title": "全文",
            "level": 1,
            "content": body.strip(),
        })
    return sections


def _list_skill_files(skill_dir: Path) -> list[dict]:
    """扁平文件列表（兼容旧客户端）。"""
    files: list[dict] = []

    def walk(dir_path: Path, rel_base: str) -> None:
        for p in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if p.name.startswith("."):
                continue
            rel = p.name if not rel_base else f"{rel_base}/{p.name}"
            if p.is_dir():
                walk(p, rel)
            elif p.is_file():
                ext = p.suffix.lower()
                files.append({
                    "path": rel,
                    "name": p.name,
                    "kind": _FILE_KIND.get(ext, "file"),
                    "size": p.stat().st_size,
                })

    walk(skill_dir, "")
    files.sort(key=lambda f: (0 if f["path"] == "SKILL.md" else 1, f["path"]))
    return files


def _list_skill_tree(skill_dir: Path) -> list[dict]:
    """按 skill 根目录真实结构返回树（仅展示根下有什么，目录可展开）。"""

    def build(dir_path: Path, rel_base: str) -> list[dict]:
        nodes: list[dict] = []
        for p in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if p.name.startswith("."):
                continue
            rel = p.name if not rel_base else f"{rel_base}/{p.name}"
            if p.is_dir():
                nodes.append({
                    "name": p.name,
                    "path": rel,
                    "type": "dir",
                    "children": build(p, rel),
                })
            elif p.is_file():
                ext = p.suffix.lower()
                nodes.append({
                    "name": p.name,
                    "path": rel,
                    "type": "file",
                    "kind": _FILE_KIND.get(ext, "file"),
                    "size": p.stat().st_size,
                })
        return nodes

    return build(skill_dir, "")


def _iter_skill_dirs():
    """遍历 business/skills 下所有含 SKILL.md 的叶子目录（含分类子目录）。"""
    from common.skill_categories import is_skill_category_dir

    if not SKILLS_DIR.is_dir():
        return
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir():
            continue
        if (p / "SKILL.md").is_file():
            yield p
            continue
        if is_skill_category_dir(p.name):
            for child in sorted(p.iterdir()):
                if child.is_dir() and (child / "SKILL.md").is_file():
                    yield child


def _skill_anchor_meta(skill_id: str) -> dict:
    """business/skills 挂载锚点信息（外部 skill 为软链）。"""
    import os

    from common.skill_link import business_skill_anchor

    anchor = business_skill_anchor((skill_id or "").strip())
    if anchor.is_symlink():
        return {"is_symlink": True, "link_target": os.readlink(anchor)}
    return {"is_symlink": False}


def _parse_meta_timestamp(meta: dict[str, str]) -> float | None:
    raw = (meta.get("updated_at") or meta.get("modified_at") or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _skill_dir_max_mtime(skill_dir: Path) -> float:
    mtimes: list[float] = []
    for p in skill_dir.rglob("*"):
        if not p.is_file() or p.name.startswith("."):
            continue
        try:
            mtimes.append(p.stat().st_mtime)
        except OSError:
            continue
    return max(mtimes) if mtimes else 0.0


def _resolve_updated_at(skill_dir: Path, meta: dict[str, str]) -> float:
    """frontmatter updated_at 与目录内最新文件 mtime 取较大值。"""
    meta_ts = _parse_meta_timestamp(meta)
    dir_ts = _skill_dir_max_mtime(skill_dir)
    if meta_ts is not None:
        return max(meta_ts, dir_ts)
    return dir_ts


def _frontmatter_line(key: str, value: str) -> str:
    if key in {"name", "description"}:
        return f'{key}: "{value}"'
    return f"{key}: {value}"


def _upsert_frontmatter_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    result = list(lines)
    for key, val in updates.items():
        line_val = _frontmatter_line(key, val)
        found = False
        for i, line in enumerate(result):
            if line.startswith(f"{key}:"):
                result[i] = line_val
                found = True
                break
        if not found:
            result.append(line_val)
    return result


def _rel_to_myteam(path: Path) -> str:
    try:
        return str(path.relative_to(MYTEAM_ROOT))
    except ValueError:
        return str(path)


def _read_skill_meta(skill_dir: Path, text: str) -> dict:
    from common.skill_categories import category_for_skill

    meta = _parse_frontmatter(text)
    sid = skill_dir.name
    is_draft = sid.startswith("auto-")
    raw_name = meta.get("name") or sid
    raw_desc = meta.get("description", "")
    gid = category_for_skill(sid)
    return {
        "id": sid,
        "name": resolve_skill_display_name(sid, raw_name),
        "description": resolve_skill_display_description(sid, raw_desc),
        "task_type": meta.get("task_type", ""),
        "path": _rel_to_myteam(skill_dir / "SKILL.md"),
        "updated_at": _resolve_updated_at(skill_dir, meta),
        "line_count": len(text.splitlines()),
        "is_draft": is_draft,
        "is_mountable": not is_draft,
        "group_id": gid,
        "category_dir": skill_dir.parent.name if gid and skill_dir.parent != SKILLS_DIR else "",
    }


def list_all_skills() -> list[dict]:
    """全部 Skill（含 auto-* 草案），供 Skill 页展示。"""
    items: list[dict] = []
    for p in _iter_skill_dirs():
        skill_md = p / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        items.append(_read_skill_meta(p, text))
    items.sort(key=lambda i: i.get("updated_at") or 0, reverse=True)
    return items


def list_skill_library() -> list[dict]:
    """所有可挂载的生产 Skill（排除 auto-* 草案目录）。"""
    items: list[dict] = []
    for p in _iter_skill_dirs():
        if not _is_production_skill_dir(p.name):
            continue
        skill_md = p / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(text)
        sid = p.name
        from common.skill_categories import category_for_skill

        gid = category_for_skill(sid)
        items.append({
            "id": sid,
            "name": resolve_skill_display_name(sid, meta.get("name") or sid),
            "description": resolve_skill_display_description(sid, meta.get("description", "")),
            "path": _rel_to_myteam(skill_md),
            "updated_at": _resolve_updated_at(p, meta),
            "line_count": len(text.splitlines()),
            "group_id": gid,
            "category_dir": p.parent.name if gid and p.parent != SKILLS_DIR else "",
        })
    items.sort(key=lambda i: i.get("updated_at") or 0, reverse=True)
    return items


def get_skill_entry(skill_id: str) -> Optional[dict]:
    """任意 Skill 目录（含 auto-*）。"""
    skill_dir = _skill_dir(skill_id)
    if not skill_dir:
        return None
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    body = _strip_frontmatter(text).strip()
    meta = _read_skill_meta(skill_dir, text)
    sid = meta["id"]
    return {
        **meta,
        **_skill_anchor_meta(sid),
        "content": text,
        "body": body,
        "sections": _parse_sections(body),
        "tree": _list_skill_tree(skill_dir),
        "files": _list_skill_files(skill_dir),
    }


def get_skill_library_entry(skill_id: str) -> Optional[dict]:
    sid = (skill_id or "").strip()
    if not sid or not _is_production_skill_dir(sid):
        return None
    from common.skill_categories import is_skill_category_dir

    if is_skill_category_dir(sid):
        return None
    return get_skill_entry(sid)


def get_skill_file(skill_id: str, rel_path: str) -> Optional[dict]:
    skill_dir = _skill_dir(skill_id)
    if not skill_dir:
        return None
    rel = (rel_path or "").strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    target = (skill_dir / rel).resolve()
    if not str(target).startswith(str(skill_dir.resolve())):
        return None
    if not target.is_file():
        return {"path": rel, "exists": False, "content": ""}
    text = target.read_text(encoding="utf-8", errors="replace")
    ext = target.suffix.lower()
    return {
        "path": rel,
        "name": target.name,
        "kind": _FILE_KIND.get(ext, "file"),
        "exists": True,
        "content": text,
        "size": target.stat().st_size,
    }


def update_skill_name(skill_id: str, name: str) -> dict:
    """更新 SKILL.md frontmatter 中的 name（展示名）。"""
    skill_dir = _skill_dir(skill_id)
    new_name = (name or "").strip()
    if not skill_dir:
        return {"success": False, "error": f"Skill 不存在：{skill_id}"}
    if not new_name:
        return {"success": False, "error": "名称不能为空"}
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER_RE.match(text)
    body = text[m.end() :] if m else text
    now = str(time.time())
    if m:
        lines = _upsert_frontmatter_lines(
            m.group(1).splitlines(),
            {"name": new_name, "updated_at": now},
        )
        new_text = "---\n" + "\n".join(lines) + "\n---\n" + body
    else:
        new_text = f'---\nname: "{new_name}"\nupdated_at: {now}\n---\n' + text
    skill_md.write_text(new_text, encoding="utf-8")
    return {"success": True, "skill_id": skill_dir.name, "name": new_name}


def validate_skill_ids(skill_ids: list[str]) -> tuple[list[str], list[str]]:
    """返回 (valid_ids, unknown_ids)。接受 Skill 组 id（如 officecli）。"""
    from common.skill_groups import is_skill_group

    valid: list[str] = []
    unknown: list[str] = []
    for raw in skill_ids:
        sid = str(raw).strip()
        if not sid:
            continue
        if is_skill_group(sid) or get_skill_library_entry(sid):
            valid.append(sid)
        else:
            unknown.append(sid)
    return valid, unknown


def delete_skill_library_entry(skill_id: str) -> dict:
    """删除 Skill 目录 business/skills 下挂载锚点（生产 Skill 与 auto-* 抽提均可删）。"""
    from common.skill_link import business_skill_anchor, remove_skill_entry

    sid = (skill_id or "").strip()
    if not sid:
        return {"success": False, "error": "skill_id 不能为空"}
    skill_dir = business_skill_anchor(sid)
    legacy = SKILLS_DIR / sid
    if not skill_dir.exists() and not skill_dir.is_symlink():
        if legacy != skill_dir and (legacy.exists() or legacy.is_symlink()):
            skill_dir = legacy
        else:
            return {"success": False, "error": f"Skill 不存在：{sid}"}
    if skill_dir.is_symlink():
        if not (skill_dir / "SKILL.md").is_file():
            return {"success": False, "error": f"Skill 不存在：{sid}"}
    elif not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
        return {"success": False, "error": f"Skill 不存在：{sid}"}
    try:
        remove_skill_entry(skill_dir)
    except OSError as e:
        return {"success": False, "error": f"删除失败：{e}"}
    return {"success": True, "skill_id": sid, "path": str(skill_dir.relative_to(MYTEAM_ROOT))}
