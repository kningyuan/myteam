"""Skill API — Hub 2.0 Skill 页。"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common.paths import MYTEAM_ROOT
from common.skill.skill_catalog import (
    create_skill,
    delete_skill_library_entry,
    get_skill_entry,
    get_skill_file,
    get_skill_library_entry,
    list_all_skills,
    update_skill_content,
    update_skill_name,
)
from common.skill.skill_extract import SKILLS_DIR, list_skill_drafts
from common.skill.skill_link import iter_business_skill_dir_names

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


class SkillNameUpdate(BaseModel):
    name: str


class SkillCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    task_types: list[str] = []
    content: str = ""


class SkillContentUpdate(BaseModel):
    content: str


class SkillCategoryCreate(BaseModel):
    id: str
    name: str
    description: str = ""


class SkillCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class SkillCategoryMove(BaseModel):
    category_id: str | None = None


@router.get("/categories")
async def list_skill_categories_api():
    from common.skill.skill_categories import list_skill_categories

    cats = list_skill_categories()
    return {"categories": cats, "count": len(cats)}


@router.post("/categories")
async def create_skill_category_api(body: SkillCategoryCreate):
    from common.skill.skill_categories import create_skill_category

    result = create_skill_category(body.id, name=body.name, description=body.description)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return result


@router.patch("/categories/{category_id}")
async def patch_skill_category_api(category_id: str, body: SkillCategoryUpdate):
    from common.skill.skill_categories import update_skill_category

    result = update_skill_category(
        category_id,
        name=body.name,
        description=body.description,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失败"))
    return result


@router.delete("/categories/{category_id}")
async def delete_skill_category_api(category_id: str):
    from common.skill.skill_categories import delete_skill_category

    result = delete_skill_category(category_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "删除失败"))
    return result


@router.get("/groups")
async def list_skill_groups_api():
    """Skill 组（vendor 套件），Agent 可挂整组或组内单个 skill。"""
    from common.skill.skill_groups import list_skill_groups

    groups = list_skill_groups()
    return {"groups": groups, "count": len(groups)}


@router.get("/library")
async def list_skill_library_api():
    """全部 Skill（生产 + auto-* 草案）。"""
    items = list_all_skills()
    return {"skills": items, "count": len(items)}


@router.post("/library")
async def create_skill_api(body: SkillCreate):
    """创建新 Skill 目录 + SKILL.md。"""
    result = create_skill(
        body.id,
        name=body.name,
        description=body.description,
        task_types=body.task_types,
        content=body.content,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return result


@router.get("/library/{skill_id}")
async def get_skill_library_item(skill_id: str):
    from common.skill.skill_categories import resolve_library_entry

    entry = resolve_library_entry(skill_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Skill 不存在：{skill_id}")
    return entry


@router.get("/library/{skill_id}/file")
async def get_skill_library_file(skill_id: str, path: str):
    from common.skill.skill_categories import get_category_file, is_skill_category_dir

    if is_skill_category_dir(skill_id):
        entry = get_category_file(skill_id, path)
    else:
        entry = get_skill_file(skill_id, path)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Skill 或文件不存在：{skill_id}/{path}")
    return entry


@router.patch("/library/{skill_id}/category")
async def patch_skill_category_assignment(skill_id: str, body: SkillCategoryMove):
    from common.skill.skill_categories import move_skill_to_category

    result = move_skill_to_category(skill_id, body.category_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "移动失败"))
    return result


@router.patch("/library/{skill_id}")
async def patch_skill_library_item(skill_id: str, body: SkillNameUpdate):
    result = update_skill_name(skill_id, body.name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失败"))
    entry = get_skill_entry(skill_id)
    return {"success": True, "skill": entry}


@router.put("/library/{skill_id}/content")
async def update_skill_content_api(skill_id: str, body: SkillContentUpdate):
    """覆盖写入 SKILL.md 全文内容。"""
    result = update_skill_content(skill_id, body.content)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失败"))
    return result


@router.delete("/library/{skill_id}")
async def delete_skill_library_item(skill_id: str):
    """删除 Skill 目录；生产 Skill 会同时从所有 Agent 挂载列表中移除。"""
    from hub.services.agent_registry import remove_skill_from_all_agents

    entry = get_skill_entry(skill_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Skill 不存在：{skill_id}")
    unmounted: list[str] = []
    if entry.get("is_mountable"):
        unmounted = remove_skill_from_all_agents(skill_id)
    result = delete_skill_library_entry(skill_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "删除失败"))
    return {
        "success": True,
        "skill_id": skill_id,
        "deleted_path": result.get("path"),
        "unmounted_from": unmounted,
        "unmounted_count": len(unmounted),
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

    from common.skill.skill_catalog import audit_catalog_router_paths
    from common.skill.skill_link import iter_business_skill_dir_names
    from common.gate.task_type_store import list_task_types_for_api

    catalog_path = MYTEAM_ROOT / "business/skills/catalog.yaml"
    catalog_types: set[str] = set()
    if catalog_path.is_file():
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        for item in data.get("skills") or []:
            for tt in item.get("task_types") or []:
                catalog_types.add(tt)

    registered = {t["task_type"] for t in list_task_types_for_api()}
    skill_dirs = set(iter_business_skill_dir_names(SKILLS_DIR))

    missing_router = sorted(registered - skill_dirs - catalog_types)
    missing_catalog = sorted(skill_dirs - catalog_types)
    router_audit = audit_catalog_router_paths(catalog_path)

    return {
        "registered_task_types": len(registered),
        "catalog_task_types": len(catalog_types),
        "skill_router_dirs": len(skill_dirs),
        "draft_count": len(list_skill_drafts()),
        "missing_router_skill_md": missing_router,
        "in_skill_dir_not_catalog": missing_catalog,
        "catalog_router_total": router_audit["router_total"],
        "catalog_router_ok": router_audit["router_ok"],
        "catalog_missing_routers": router_audit["missing_routers"],
    }


@router.get("/pending")
async def list_skill_pending_api():
    """Skill review 待审批包（_pending/）。"""
    from execution_harness.post.pending import list_pending

    items = list_pending()
    return {"pending": items, "count": len(items)}


@router.get("/pending/{pending_id}")
async def get_skill_pending_api(pending_id: str):
    from execution_harness.post.pending import get_pending

    item = get_pending(pending_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"pending 不存在：{pending_id}")
    return item


@router.post("/pending/{pending_id}/approve")
async def approve_skill_pending_api(pending_id: str):
    from execution_harness.post.pending import approve_pending

    result = approve_pending(pending_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "批准失败")
    return result


@router.post("/pending/{pending_id}/reject")
async def reject_skill_pending_api(pending_id: str):
    from execution_harness.post.pending import reject_pending

    result = reject_pending(pending_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "拒绝失败")
    return result


@router.get("/library/{skill_id}/references")
async def list_skill_references_api(skill_id: str):
    """列出 umbrella skill 的 references/ 目录。"""
    from common.skill.skill_catalog import SKILLS_DIR

    ref_dir = SKILLS_DIR / skill_id / "references"
    refs: list[dict] = []
    if ref_dir.is_dir():
        for fp in sorted(ref_dir.glob("*.md")):
            refs.append({
                "path": f"references/{fp.name}",
                "name": fp.name,
                "size": fp.stat().st_size,
                "updated_at": fp.stat().st_mtime,
            })
    return {"skill_id": skill_id, "references": refs, "count": len(refs)}


# ── 导出 / 导入 ──────────────────────────────────────────────


@router.get("/library/{skill_id}/export")
async def export_skill_api(skill_id: str):
    """导出单个 Skill 为 zip 包（含 SKILL.md + references/）。"""
    from common.skill.skill_catalog import SKILLS_DIR

    skill_dir = SKILLS_DIR / skill_id
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill 不存在")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in skill_dir.rglob("*"):
            if fp.is_file():
                # 加一层 skill_id 包裹，使 zip 顶层为唯一 skill 目录，与 import 端点契约一致
                zf.write(fp, f"{skill_id}/{fp.relative_to(skill_dir).as_posix()}")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="skill-{skill_id}.zip"'},
    )


@router.post("/library/import")
async def import_skill_api(request: Request):
    """导入 Skill zip 包：解压到 SKILLS_DIR，目录名即 skill_id。冲突时返回 409。"""
    import shutil

    from common.skill.skill_catalog import SKILLS_DIR

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="未上传文件")
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 zip 文件")
    # 第一层目录名作为 skill_id
    names = zf.namelist()
    top_dirs = {n.split("/")[0] for n in names if n and not n.startswith("__MACOSX")}
    if len(top_dirs) != 1:
        raise HTTPException(status_code=400, detail="zip 包应仅含一个顶层 skill 目录")
    skill_id = top_dirs.pop()
    if not re.match(r"^[a-zA-Z0-9_-]+$", skill_id):
        raise HTTPException(status_code=400, detail=f"非法 skill_id: {skill_id}")
    target = SKILLS_DIR / skill_id
    if target.is_dir():
        raise HTTPException(status_code=409, detail=f"Skill 已存在: {skill_id}（请先删除或重命名）")
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    zf.extractall(SKILLS_DIR)
    # 清理 __MACOSX
    macosx = SKILLS_DIR / "__MACOSX"
    if macosx.is_dir():
        shutil.rmtree(macosx)
    # 必须有 SKILL.md
    if not (target / "SKILL.md").is_file():
        shutil.rmtree(target)
        raise HTTPException(status_code=400, detail="zip 包根目录缺少 SKILL.md")
    return {"success": True, "skill_id": skill_id}
