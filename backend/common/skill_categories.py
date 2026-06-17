"""Skill 分类（标签）— 对应 business/skills/<category>/ 目录，成员 skill 在其子目录。"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Optional

import yaml

from common.paths import MYTEAM_ROOT
from common.skill_catalog import (
    SKILLS_DIR,
    _list_skill_tree,
    _parse_frontmatter,
    _read_skill_meta,
    _resolve_updated_at,
    get_skill_entry,
)
from common.skill_display_names import resolve_skill_display_description, resolve_skill_display_name
from common.skill_link import business_skill_anchor, remove_skill_entry, resolve_skill_source_dir

_CATEGORY_META = "category.yaml"
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _category_dir(category_id: str) -> Path:
    return SKILLS_DIR / (category_id or "").strip()


def _read_category_meta(cat_dir: Path) -> dict:
    fp = cat_dir / _CATEGORY_META
    if fp.is_file():
        try:
            data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                return {str(k): v for k, v in data.items()}
        except yaml.YAMLError:
            pass
    # vendor 套件默认元数据
    from common.skill_groups import SKILL_GROUPS

    cid = cat_dir.name
    if cid in SKILL_GROUPS:
        meta = SKILL_GROUPS[cid]
        return {
            "name": meta.get("name_zh") or meta.get("name") or cid,
            "description": meta.get("description", ""),
        }
    return {"name": cid, "description": ""}


def _write_category_meta(cat_dir: Path, *, name: str, description: str = "") -> None:
    cat_dir.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        {
            "name": name,
            "description": description,
            "updated_at": time.time(),
        },
        allow_unicode=True,
        sort_keys=False,
    )
    (cat_dir / _CATEGORY_META).write_text(text, encoding="utf-8")


def is_skill_category_dir(dirname: str) -> bool:
    """目录为分类：无根级 SKILL.md，且含 category.yaml 或至少一个子 skill。"""
    p = _category_dir(dirname)
    if not p.is_dir() or p.name.startswith("auto-"):
        return False
    if (p / "SKILL.md").is_file():
        return False
    if (p / _CATEGORY_META).is_file():
        return True
    for child in p.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "SKILL.md").is_file():
            return True
    return False


def category_for_skill(skill_id: str) -> str | None:
    """skill 所在分类目录名；顶层 skill 返回 None（直接扫盘，避免与 resolve 循环）。"""
    sid = (skill_id or "").strip()
    if not sid or not SKILLS_DIR.is_dir():
        return None
    top = SKILLS_DIR / sid
    if top.is_dir() and (top / "SKILL.md").is_file():
        return None
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if not is_skill_category_dir(p.name):
            continue
        nested = p / sid
        if nested.is_dir() and (nested / "SKILL.md").is_file():
            return p.name
    return None


def _rel_to_myteam(path: Path) -> str:
    try:
        return str(path.relative_to(MYTEAM_ROOT))
    except ValueError:
        return str(path)


def list_category_member_ids(category_id: str) -> list[str]:
    cat_dir = _category_dir(category_id)
    if not cat_dir.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(cat_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == _CATEGORY_META:
            continue
        if (child / "SKILL.md").is_file():
            ids.append(child.name)
    return ids


def list_skill_categories() -> list[dict]:
    if not SKILLS_DIR.is_dir():
        return []
    items: list[dict] = []
    for p in sorted(SKILLS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if not is_skill_category_dir(p.name):
            continue
        meta = _read_category_meta(p)
        members = list_category_member_ids(p.name)
        items.append({
            "id": p.name,
            "kind": "category",
            "name": str(meta.get("name") or p.name),
            "description": str(meta.get("description") or ""),
            "path": _rel_to_myteam(p),
            "member_count": len(members),
            "updated_at": p.stat().st_mtime,
        })
    items.sort(key=lambda i: (i.get("name") or i["id"]).lower())
    return items


def get_skill_category_entry(category_id: str) -> Optional[dict]:
    cid = (category_id or "").strip()
    if not cid or not is_skill_category_dir(cid):
        return None
    cat_dir = _category_dir(cid)
    meta = _read_category_meta(cat_dir)
    members: list[dict] = []
    tree: list[dict] = []
    for mid in list_category_member_ids(cid):
        skill_dir = cat_dir / mid
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        sm = _read_skill_meta(skill_dir, text)
        members.append({
            "id": mid,
            "name": sm["name"],
            "description": sm["description"],
        })
        subtree = _list_skill_tree(skill_dir)
        tree.append({
            "name": sm["name"] or mid,
            "path": mid,
            "type": "dir",
            "skill_id": mid,
            "children": _prefix_tree_paths(subtree, mid),
        })
    return {
        "id": cid,
        "kind": "category",
        "name": str(meta.get("name") or cid),
        "description": str(meta.get("description") or ""),
        "path": _rel_to_myteam(cat_dir),
        "members": members,
        "member_count": len(members),
        "tree": tree,
        "updated_at": cat_dir.stat().st_mtime,
    }


def _prefix_tree_paths(nodes: list[dict], prefix: str) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        path = f"{prefix}/{node['path']}" if prefix else node["path"]
        item = {**node, "path": path}
        if node.get("type") == "dir" and node.get("children"):
            item["children"] = _prefix_tree_paths(node["children"], prefix)
        out.append(item)
    return out


def create_skill_category(category_id: str, *, name: str, description: str = "") -> dict:
    cid = (category_id or "").strip().lower()
    if not cid or not _SLUG_RE.match(cid):
        return {"success": False, "error": "分类 id 须为小写英文、数字、连字符或下划线"}
    dest = _category_dir(cid)
    if dest.exists():
        if is_skill_category_dir(cid):
            return {"success": False, "error": f"分类已存在：{cid}"}
        return {"success": False, "error": f"路径已被占用：{cid}"}
    display = (name or "").strip() or cid
    _write_category_meta(dest, name=display, description=(description or "").strip())
    return {"success": True, "category": get_skill_category_entry(cid)}


def update_skill_category(
    category_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict:
    cid = (category_id or "").strip()
    if not is_skill_category_dir(cid):
        return {"success": False, "error": f"分类不存在：{cid}"}
    cat_dir = _category_dir(cid)
    meta = _read_category_meta(cat_dir)
    if name is not None:
        meta["name"] = name.strip() or cid
    if description is not None:
        meta["description"] = description.strip()
    _write_category_meta(cat_dir, name=str(meta.get("name") or cid), description=str(meta.get("description") or ""))
    return {"success": True, "category": get_skill_category_entry(cid)}


def move_skill_to_category(skill_id: str, category_id: str | None) -> dict:
    """变更 skill 标签：物理移动目录，skill id 不变。"""
    sid = (skill_id or "").strip()
    skill_dir = resolve_skill_source_dir(sid)
    if not skill_dir or not (skill_dir / "SKILL.md").is_file():
        return {"success": False, "error": f"Skill 不存在：{sid}"}

    target_cat = (category_id or "").strip() or None
    current_cat = category_for_skill(sid)

    if target_cat == current_cat:
        entry = get_skill_entry(sid)
        return {"success": True, "skill": entry, "category_id": current_cat}

    if target_cat:
        if not is_skill_category_dir(target_cat):
            return {"success": False, "error": f"分类不存在：{target_cat}"}
        dest = _category_dir(target_cat) / sid
    else:
        dest = SKILLS_DIR / sid

    if dest.exists() or dest.is_symlink():
        return {"success": False, "error": f"目标路径已存在：{_rel_to_myteam(dest)}"}

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(skill_dir), str(dest))
    except OSError as e:
        return {"success": False, "error": f"移动失败：{e}"}

    entry = get_skill_entry(sid)
    return {"success": True, "skill": entry, "category_id": target_cat}


def resolve_library_entry(entry_id: str) -> Optional[dict]:
    """Skill 页统一入口：分类或叶子 skill。"""
    eid = (entry_id or "").strip()
    if not eid:
        return None
    if is_skill_category_dir(eid):
        return get_skill_category_entry(eid)
    return get_skill_entry(eid)


def get_category_file(category_id: str, file_path: str) -> Optional[dict]:
    """分类详情树中的文件：path 形如 memberId/relative/path。"""
    from common.skill_catalog import get_skill_file

    rel = (file_path or "").strip().lstrip("/")
    if not rel or "/" not in rel:
        return None
    member_id, _, inner = rel.partition("/")
    if not member_id or not inner:
        return None
    if member_id not in list_category_member_ids(category_id):
        return None
    return get_skill_file(member_id, inner)
