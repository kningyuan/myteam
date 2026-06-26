"""Task types 域路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/task-types", tags=["task-types"])


@router.get("")
async def api_list_task_types():
    """任务类型注册表（templates.yaml），供管理 Tab 与 Workflow 编辑器使用。"""
    from common.task_type_store import list_task_types_for_api

    return {"task_types": list_task_types_for_api()}


@router.get("/outcome-kinds")
async def api_task_type_outcome_kinds():
    """产出形态目录（Gate 支持的三种 outcome_kind + 现实任务覆盖说明）。"""
    from common.task_type_suggest import list_outcome_kind_catalog

    return {"outcome_kinds": list_outcome_kind_catalog()}


@router.post("/suggest")
async def api_suggest_task_type(body: dict):
    """根据描述规则推导任务类型草稿（无 LLM/CLI）。"""
    from common.task_type_suggest import suggest_task_type_from_description

    desc = (body.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="description 不能为空")
    try:
        return suggest_task_type_from_description(desc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
async def api_create_task_type(body: dict):
    from common.task_type_store import get_task_type_raw, upsert_task_type, validate_task_type_id

    task_type = validate_task_type_id(body.get("task_type") or "")
    if get_task_type_raw(task_type):
        raise HTTPException(status_code=409, detail=f"task_type「{task_type}」已存在")
    try:
        result = upsert_task_type(task_type, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from common.hub_operation_meta import touch

    touch("task_type", task_type)
    return {"success": True, **result}


@router.put("/{task_type}")
async def api_update_task_type(task_type: str, body: dict):
    from common.task_type_store import get_task_type_raw, upsert_task_type

    if not get_task_type_raw(task_type):
        raise HTTPException(status_code=404, detail=f"task_type「{task_type}」不存在")
    try:
        result = upsert_task_type(task_type, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from common.hub_operation_meta import touch

    touch("task_type", task_type)
    return {"success": True, **result}


@router.delete("/{task_type}")
async def api_delete_task_type(task_type: str):
    from common.task_type_store import delete_task_type

    try:
        delete_task_type(task_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from common.hub_operation_meta import remove

    remove("task_type", task_type)
    return {"success": True}
