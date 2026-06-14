"""Skill 草案只读 API — Hub 2.0 Skill 升级页。"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from common.paths import MYTEAM_ROOT
from common.skill_extract import SKILLS_DIR, list_skill_drafts

router = APIRouter(prefix="/api/skills", tags=["skills"])

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _draft_id_from_path(path: Path) -> str:
    return path.parent.name


def _production_skill_path(task_type: str) -> Path | None:
    if not task_type:
        return None
    p = SKILLS_DIR / task_type / "SKILL.md"
    return p if p.is_file() else None


def _summarize_draft(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = _parse_frontmatter(text)
    draft_id = _draft_id_from_path(path)
    task_type = meta.get("task_type", "")
    prod = _production_skill_path(task_type)
    return {
        "id": draft_id,
        "path": str(path.relative_to(MYTEAM_ROOT)),
        "task_type": task_type,
        "project_id": meta.get("project_id", ""),
        "task_id": meta.get("task_id", ""),
        "agent": meta.get("agent", ""),
        "description": meta.get("description", ""),
        "has_production_skill": prod is not None,
        "production_skill_path": str(prod.relative_to(MYTEAM_ROOT)) if prod else None,
        "updated_at": path.stat().st_mtime,
    }


@router.get("/drafts")
async def list_skill_draft_api():
    drafts = [_summarize_draft(p) for p in list_skill_drafts()]
    drafts.sort(key=lambda d: d.get("updated_at") or 0, reverse=True)
    return {"drafts": drafts, "count": len(drafts)}


@router.get("/drafts/{draft_id}")
async def get_skill_draft(draft_id: str):
    skill_path = SKILLS_DIR / draft_id / "SKILL.md"
    if not skill_path.is_file():
        raise HTTPException(status_code=404, detail=f"草案不存在：{draft_id}")
    text = skill_path.read_text(encoding="utf-8", errors="replace")
    summary = _summarize_draft(skill_path)
    return {**summary, "content": text}


@router.get("/drafts/{draft_id}/diff")
async def diff_skill_draft(draft_id: str):
    skill_path = SKILLS_DIR / draft_id / "SKILL.md"
    if not skill_path.is_file():
        raise HTTPException(status_code=404, detail=f"草案不存在：{draft_id}")
    draft_text = skill_path.read_text(encoding="utf-8", errors="replace")
    meta = _parse_frontmatter(draft_text)
    task_type = meta.get("task_type", "")
    prod_path = _production_skill_path(task_type)
    production_text = ""
    if prod_path:
        production_text = prod_path.read_text(encoding="utf-8", errors="replace")
    return {
        "draft_id": draft_id,
        "task_type": task_type,
        "draft_path": str(skill_path.relative_to(MYTEAM_ROOT)),
        "production_path": str(prod_path.relative_to(MYTEAM_ROOT)) if prod_path else None,
        "draft": draft_text,
        "production": production_text,
        "draft_lines": len(draft_text.splitlines()),
        "production_lines": len(production_text.splitlines()) if production_text else 0,
    }


@router.get("/matrix")
async def skill_matrix_audit():
    """catalog × templates 覆盖摘要（只读）。"""
    import yaml

    from common.task_type_store import list_task_types_for_api

    catalog_path = MYTEAM_ROOT / "business/skills/catalog.yaml"
    catalog_types: set[str] = set()
    if catalog_path.is_file():
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        for item in data.get("skills") or []:
            for tt in item.get("task_types") or []:
                catalog_types.add(tt)

    registered = {t["task_type"] for t in list_task_types_for_api()}
    skill_dirs = {
        p.name
        for p in SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file() and not p.name.startswith("auto-")
    }

    missing_router = sorted(registered - skill_dirs - catalog_types)
    missing_catalog = sorted(skill_dirs - catalog_types)

    return {
        "registered_task_types": len(registered),
        "catalog_task_types": len(catalog_types),
        "skill_router_dirs": len(skill_dirs),
        "draft_count": len(list_skill_drafts()),
        "missing_router_skill_md": missing_router,
        "in_skill_dir_not_catalog": missing_catalog,
    }
