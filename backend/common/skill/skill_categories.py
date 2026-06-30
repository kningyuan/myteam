"""Skill 分类（标签）— 元数据在 business/skills/categories.yaml；skill 目录始终扁平 business/skills/<id>/。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from common.paths import MYTEAM_ROOT
from common.skill.skill_catalog import (
    SKILLS_DIR,
    _list_skill_tree,
    _read_skill_meta,
)
from common.skill.skill_display_names import resolve_skill_display_description, resolve_skill_display_name
from common.skill.skill_link import resolve_skill_source_dir

_CATEGORIES_FILE = "categories.yaml"
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _categories_path() -> Path:
    return SKILLS_DIR / _CATEGORIES_FILE


def _empty_registry() -> dict[str, Any]:
    return {"version": "1", "categories": {}}


def _load_registry() -> dict[str, Any]:
    fp = _categories_path()
    if not fp.is_file():
        return _empty_registry()
    try:
        data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return _empty_registry()
    if not isinstance(data, dict):
        return _empty_registry()
    cats = data.get("categories")
    if not isinstance(cats, dict):
        data["categories"] = {}
    return data


def _save_registry(data: dict[str, Any]) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    _categories_path().write_text(text, encoding="utf-8")


def _categories_map() -> dict[str, dict[str, Any]]:
    data = _load_registry()
    raw = data.get("categories") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for cid, meta in raw.items():
        if not isinstance(meta, dict):
            meta = {}
        members = meta.get("members") or []
        if not isinstance(members, list):
            members = []
        out[str(cid)] = {
            "name": str(meta.get("name") or cid),
            "description": str(meta.get("description") or ""),
            "members": [str(m).strip() for m in members if str(m).strip()],
            "updated_at": meta.get("updated_at"),
        }
    return out


def _write_category(cid: str, *, name: str, description: str, members: list[str]) -> None:
    data = _load_registry()
    cats = data.setdefault("categories", {})
    cats[cid] = {
        "name": name,
        "description": description,
        "members": members,
        "updated_at": time.time(),
    }
    _save_registry(data)


def _skill_to_category_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for cid, meta in _categories_map().items():
        for mid in meta.get("members") or []:
            idx[mid] = cid
    return idx


def is_skill_category_dir(category_id: str) -> bool:
    """分类 id 是否在 categories.yaml 中注册（兼容旧名：不再检查物理目录）。"""
    return (category_id or "").strip() in _categories_map()


_AUTO_EXTRACTED_CATEGORY = "auto-extracted"


def category_for_skill(skill_id: str) -> str | None:
    """skill 所属展示分类；目录始终在 business/skills/<id>/ 顶层。

    auto-* 前缀的 Skill 草稿默认归入 "auto-extracted" 分类，
    除非已在 categories.yaml 中手动指定了其他分类。
    """
    sid = (skill_id or "").strip()
    manual = _skill_to_category_index().get(sid)
    if manual:
        return manual
    if sid.startswith("auto-") and is_skill_category_dir(_AUTO_EXTRACTED_CATEGORY):
        return _AUTO_EXTRACTED_CATEGORY
    return None


def _rel_to_myteam(path: Path) -> str:
    try:
        return str(path.relative_to(MYTEAM_ROOT))
    except ValueError:
        return str(path)


def list_category_member_ids(category_id: str) -> list[str]:
    cid = (category_id or "").strip()
    meta = _categories_map().get(cid)
    if not meta:
        return []
    members = list(meta.get("members") or [])
    # auto-extracted 分类：补充所有 auto-* 草稿（代码逻辑自动归入）
    if cid == _AUTO_EXTRACTED_CATEGORY:
        from common.skill.skill_catalog import _iter_skill_dirs

        for p in _iter_skill_dirs():
            if p.name.startswith("auto-") and p.name not in members:
                members.append(p.name)
    return members


def list_skill_categories() -> list[dict]:
    items: list[dict] = []
    for cid, meta in sorted(_categories_map().items(), key=lambda x: (x[1].get("name") or x[0]).lower()):
        members = list_category_member_ids(cid)
        updated = meta.get("updated_at")
        if updated is None:
            updated = _categories_path().stat().st_mtime if _categories_path().is_file() else 0.0
        items.append({
            "id": cid,
            "kind": "category",
            "name": meta.get("name") or cid,
            "description": meta.get("description") or "",
            "path": f"business/skills/{_CATEGORIES_FILE}#{cid}",
            "member_count": len(members),
            "updated_at": float(updated) if updated is not None else 0.0,
        })
    return items


def get_skill_category_entry(category_id: str) -> Optional[dict]:
    cid = (category_id or "").strip()
    if not is_skill_category_dir(cid):
        return None
    meta = _categories_map()[cid]
    members: list[dict] = []
    tree: list[dict] = []
    for mid in list_category_member_ids(cid):
        skill_dir = resolve_skill_source_dir(mid)
        if not skill_dir or not (skill_dir / "SKILL.md").is_file():
            continue
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
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
    updated = meta.get("updated_at")
    if updated is None:
        updated = _categories_path().stat().st_mtime if _categories_path().is_file() else 0.0
    return {
        "id": cid,
        "kind": "category",
        "name": meta.get("name") or cid,
        "description": meta.get("description") or "",
        "path": f"business/skills/{_CATEGORIES_FILE}#{cid}",
        "members": members,
        "member_count": len(members),
        "tree": tree,
        "updated_at": float(updated) if updated is not None else 0.0,
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
    if is_skill_category_dir(cid):
        return {"success": False, "error": f"分类已存在：{cid}"}
    display = (name or "").strip() or cid
    _write_category(cid, name=display, description=(description or "").strip(), members=[])
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
    meta = _categories_map()[cid]
    new_name = name.strip() if name is not None else str(meta.get("name") or cid)
    new_desc = description.strip() if description is not None else str(meta.get("description") or "")
    _write_category(cid, name=new_name or cid, description=new_desc, members=list(meta.get("members") or []))
    return {"success": True, "category": get_skill_category_entry(cid)}


def move_skill_to_category(skill_id: str, category_id: str | None) -> dict:
    """变更 skill 展示分类：只改 categories.yaml，不移动 business/skills/<id>/ 目录。"""
    from common.skill.skill_catalog import get_skill_entry

    sid = (skill_id or "").strip()
    skill_dir = resolve_skill_source_dir(sid)
    if not skill_dir or not (skill_dir / "SKILL.md").is_file():
        return {"success": False, "error": f"Skill 不存在：{sid}"}

    target_cat = (category_id or "").strip() or None
    current_cat = category_for_skill(sid)

    if target_cat == current_cat:
        entry = get_skill_entry(sid)
        return {"success": True, "skill": entry, "category_id": current_cat}

    data = _load_registry()
    cats: dict[str, Any] = data.setdefault("categories", {})

    if current_cat and current_cat in cats:
        cur = cats[current_cat]
        members = [m for m in (cur.get("members") or []) if m != sid]
        cur["members"] = members
        cur["updated_at"] = time.time()

    if target_cat:
        if not is_skill_category_dir(target_cat):
            return {"success": False, "error": f"分类不存在：{target_cat}"}
        block = cats.setdefault(target_cat, {"name": target_cat, "description": "", "members": []})
        members = list(block.get("members") or [])
        if sid not in members:
            members.append(sid)
        block["members"] = members
        block["updated_at"] = time.time()

    _save_registry(data)

    from common.agent.adapter_skill_registry import remount_skill_after_library_move

    remount = remount_skill_after_library_move(sid)
    entry = get_skill_entry(sid)
    return {
        "success": True,
        "skill": entry,
        "category_id": target_cat,
        "remount": remount,
    }


def delete_skill_category(category_id: str) -> dict:
    """删除分类标签：只从 categories.yaml 移除条目，不删除 skill 目录。"""
    cid = (category_id or "").strip()
    if not cid:
        return {"success": False, "error": "分类 id 不能为空"}
    if not is_skill_category_dir(cid):
        return {"success": False, "error": f"分类不存在：{cid}"}
    data = _load_registry()
    cats: dict[str, Any] = data.setdefault("categories", {})
    cats.pop(cid, None)
    _save_registry(data)
    return {"success": True, "deleted_id": cid}


def resolve_library_entry(entry_id: str) -> Optional[dict]:
    """Skill 页统一入口：分类或叶子 skill。"""
    eid = (entry_id or "").strip()
    if not eid:
        return None
    if is_skill_category_dir(eid):
        return get_skill_category_entry(eid)
    from common.skill.skill_catalog import get_skill_entry

    return get_skill_entry(eid)


def get_category_file(category_id: str, file_path: str) -> Optional[dict]:
    """分类详情树中的文件：path 形如 memberId/relative/path。"""
    from common.skill.skill_catalog import get_skill_file

    rel = (file_path or "").strip().lstrip("/")
    if not rel or "/" not in rel:
        return None
    member_id, _, inner = rel.partition("/")
    if not member_id or not inner:
        return None
    if member_id not in list_category_member_ids(category_id):
        return None
    return get_skill_file(member_id, inner)
