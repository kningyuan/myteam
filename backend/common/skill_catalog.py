"""Skill 库 — 扫描 business/skills 下 Skill（生产 + auto-* 草案，单一出处）。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from common.paths import MYTEAM_ROOT

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
    sid = (skill_id or "").strip()
    if not sid:
        return None
    d = SKILLS_DIR / sid
    if d.is_dir() and (d / "SKILL.md").is_file():
        return d
    return None


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
    files: list[dict] = []
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(skill_dir).as_posix()
        ext = p.suffix.lower()
        files.append({
            "path": rel,
            "name": p.name,
            "kind": _FILE_KIND.get(ext, "file"),
            "size": p.stat().st_size,
        })
    files.sort(key=lambda f: (0 if f["path"] == "SKILL.md" else 1, f["path"]))
    return files


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


def _read_skill_meta(skill_dir: Path, text: str) -> dict:
    meta = _parse_frontmatter(text)
    sid = skill_dir.name
    is_draft = sid.startswith("auto-")
    return {
        "id": sid,
        "name": meta.get("name") or sid,
        "description": meta.get("description", ""),
        "task_type": meta.get("task_type", ""),
        "path": str((skill_dir / "SKILL.md").relative_to(MYTEAM_ROOT)),
        "updated_at": _resolve_updated_at(skill_dir, meta),
        "line_count": len(text.splitlines()),
        "is_draft": is_draft,
        "is_mountable": not is_draft,
    }


def list_all_skills() -> list[dict]:
    """全部 Skill（含 auto-* 草案），供 Skill 页展示。"""
    if not SKILLS_DIR.is_dir():
        return []
    items: list[dict] = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir():
            continue
        skill_md = p / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        items.append(_read_skill_meta(p, text))
    items.sort(key=lambda i: i.get("updated_at") or 0, reverse=True)
    return items


def list_skill_library() -> list[dict]:
    """所有可挂载的生产 Skill（排除 auto-* 草案目录）。"""
    if not SKILLS_DIR.is_dir():
        return []
    items: list[dict] = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or not _is_production_skill_dir(p.name):
            continue
        skill_md = p / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(text)
        items.append({
            "id": p.name,
            "name": meta.get("name") or p.name,
            "description": meta.get("description", ""),
            "path": str(skill_md.relative_to(MYTEAM_ROOT)),
            "updated_at": _resolve_updated_at(p, meta),
            "line_count": len(text.splitlines()),
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
    return {
        **meta,
        "content": text,
        "body": body,
        "sections": _parse_sections(body),
        "files": _list_skill_files(skill_dir),
    }


def get_skill_library_entry(skill_id: str) -> Optional[dict]:
    sid = (skill_id or "").strip()
    if not sid or not _is_production_skill_dir(sid):
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
    """返回 (valid_ids, unknown_ids)。"""
    valid: list[str] = []
    unknown: list[str] = []
    for raw in skill_ids:
        sid = str(raw).strip()
        if not sid:
            continue
        if get_skill_library_entry(sid):
            valid.append(sid)
        else:
            unknown.append(sid)
    return valid, unknown


def delete_skill_library_entry(skill_id: str) -> dict:
    """删除 Skill 目录 business/skills/<id>/（生产 Skill 与 auto-* 抽提均可删）。"""
    import shutil

    sid = (skill_id or "").strip()
    if not sid:
        return {"success": False, "error": "skill_id 不能为空"}
    skill_dir = SKILLS_DIR / sid
    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
        return {"success": False, "error": f"Skill 不存在：{sid}"}
    try:
        shutil.rmtree(skill_dir)
    except OSError as e:
        return {"success": False, "error": f"删除失败：{e}"}
    return {"success": True, "skill_id": sid, "path": str(skill_dir.relative_to(MYTEAM_ROOT))}
