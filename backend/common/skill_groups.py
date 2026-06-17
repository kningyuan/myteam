"""Skill 组 — registry 可挂整组（分类）或组内单个 skill。"""

from __future__ import annotations

from common.skill_categories import (
    category_for_skill,
    is_skill_category_dir,
    list_category_member_ids,
    list_skill_categories,
)
from common.skill_display_names import (
    resolve_skill_display_description,
    resolve_skill_display_name,
)
from common.skill_link import OFFICECLI_SKILLS_ROOT, OFFICECLI_VENDOR_SKILL_IDS

OFFICECLI_CATEGORY_DIR = "officecli"

SKILL_GROUPS: dict[str, dict] = {
    "officecli": {
        "name": "OfficeCLI",
        "name_zh": "Office 文档套件",
        "description": (
            "OfficeCLI 上游 skills/ 目录全套：通用 officecli + docx/pptx/xlsx 及场景化子 skill。"
            "挂载整组时 Agent 可按任务自选子 skill。"
        ),
        "vendor_skills_root": OFFICECLI_SKILLS_ROOT,
        "storage_dir": OFFICECLI_CATEGORY_DIR,
    },
}


def skill_storage_dir(skill_id: str) -> str | None:
    return category_for_skill(skill_id)


def is_skill_group(skill_id: str) -> bool:
    gid = (skill_id or "").strip()
    if gid in SKILL_GROUPS:
        return True
    return is_skill_category_dir(gid)


def get_skill_group(skill_id: str) -> dict | None:
    gid = (skill_id or "").strip()
    if gid in SKILL_GROUPS:
        return SKILL_GROUPS[gid]
    if is_skill_category_dir(gid):
        from common.skill_categories import get_skill_category_entry

        entry = get_skill_category_entry(gid)
        if entry:
            return {
                "name": entry.get("name"),
                "name_zh": entry.get("name"),
                "description": entry.get("description", ""),
                "storage_dir": gid,
            }
    return None


def group_for_member(member_id: str) -> str | None:
    return category_for_skill(member_id)


def _group_member_ids(group_id: str) -> list[str]:
    meta = SKILL_GROUPS.get(group_id)
    storage = str(meta.get("storage_dir") or group_id) if meta else group_id
    if is_skill_category_dir(storage):
        return list_category_member_ids(storage)
    if meta:
        return list(OFFICECLI_VENDOR_SKILL_IDS)
    return []


def expand_skill_mounts(configured_ids: list[str]) -> list[str]:
    """将 registry 配置（组 id 或叶子 id）展开为 CLI 同步用的叶子 skill id 列表。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in configured_ids:
        sid = (raw or "").strip()
        if not sid or sid in seen:
            continue
        if is_skill_group(sid):
            for mid in _group_member_ids(sid):
                if mid not in seen:
                    seen.add(mid)
                    out.append(mid)
            seen.add(sid)
            continue
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def list_skill_groups() -> list[dict]:
    """供 API / Agent 挂载：分类组元数据 + 成员展示名。"""
    items: list[dict] = []
    seen_dirs: set[str] = set()
    for gid, meta in sorted(SKILL_GROUPS.items()):
        storage = str(meta.get("storage_dir") or gid)
        seen_dirs.add(storage)
        members = []
        for mid in _group_member_ids(gid):
            members.append({
                "id": mid,
                "name": resolve_skill_display_name(mid, mid),
                "description": resolve_skill_display_description(mid, ""),
            })
        items.append({
            "id": gid,
            "name": meta.get("name_zh") or meta.get("name") or gid,
            "description": meta.get("description", ""),
            "vendor_skills_root": meta.get("vendor_skills_root", ""),
            "storage_dir": storage,
            "members": members,
            "is_group": True,
        })
    for cat in list_skill_categories():
        cid = cat["id"]
        if cid in seen_dirs:
            continue
        members = []
        for mid in list_category_member_ids(cid):
            members.append({
                "id": mid,
                "name": resolve_skill_display_name(mid, mid),
                "description": resolve_skill_display_description(mid, ""),
            })
        items.append({
            "id": cid,
            "name": cat.get("name") or cid,
            "description": cat.get("description", ""),
            "storage_dir": cid,
            "members": members,
            "is_group": True,
        })
    return items
