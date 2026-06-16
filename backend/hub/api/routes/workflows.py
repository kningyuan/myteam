"""PGD workflow profile CRUD routes (P3.1 Wave 4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from hub.api.errors import APIError

router = APIRouter(tags=["workflows"])


@router.get("/api/workflows")
async def api_list_workflows():
    """列出 PGD workflow profile（阶段闸门项目模板）。"""
    from common.workflow_bootstrap import list_workflow_summaries

    return {"workflows": list_workflow_summaries()}


@router.post("/api/workflows/suggest")
async def api_suggest_workflow(body: dict):
    """根据描述确定性推导任务 DAG（供 Workflow 编辑页「自动推导」）。"""
    from common.workflow_suggest import suggest_workflow_from_description
    from hub.services.agent_registry import sync_missing_agent_task_types

    desc = (body.get("description") or "").strip()
    if not desc:
        raise APIError("INVALID_BODY", "description 不能为空")
    try:
        sync_missing_agent_task_types(only_empty=True)
        return suggest_workflow_from_description(desc)
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))


@router.get("/api/workflows/{workflow_id}")
async def api_get_workflow(workflow_id: str):
    from common.workflow_loader import read_workflow_raw

    try:
        return {"workflow": read_workflow_raw(workflow_id)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))


@router.post("/api/workflows")
async def api_create_workflow(body: dict):
    from common.workflow_loader import allocate_workflow_id, list_workflows, write_workflow_raw
    from common.workflow_validate import validate_workflow_payload

    data = body.get("workflow") if isinstance(body.get("workflow"), dict) else body
    if not isinstance(data, dict):
        raise APIError("INVALID_BODY", "需要 workflow 对象")
    name = str(data.get("name") or data.get("display_name") or "").strip()
    if not name:
        raise APIError("INVALID_WORKFLOW", "workflow.name 不能为空")
    data = dict(data)
    data["name"] = name
    wid = (data.get("id") or "").strip()
    if not wid:
        wid = allocate_workflow_id()
        data["id"] = wid
    if wid in list_workflows():
        raise APIError("WORKFLOW_EXISTS", f"workflow「{wid}」已存在", hint="换 id 或使用 PUT 更新")
    errors = validate_workflow_payload(data)
    if errors:
        raise APIError("INVALID_WORKFLOW", "；".join(errors))
    try:
        write_workflow_raw(data)
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))
    from common.hub_operation_meta import touch

    touch("workflow", wid)
    return {"success": True, "id": wid}


@router.put("/api/workflows/{workflow_id}")
async def api_update_workflow(workflow_id: str, body: dict):
    from common.workflow_loader import delete_workflow, write_workflow_raw
    from common.workflow_validate import validate_workflow_payload

    data = body.get("workflow") if isinstance(body.get("workflow"), dict) else body
    if not isinstance(data, dict):
        raise APIError("INVALID_BODY", "需要 workflow 对象")
    name = str(data.get("name") or data.get("display_name") or "").strip()
    if name:
        data = dict(data)
        data["name"] = name
    new_id = (data.get("id") or workflow_id).strip()
    errors = validate_workflow_payload(data)
    if errors:
        raise APIError("INVALID_WORKFLOW", "；".join(errors))
    try:
        write_workflow_raw(data, workflow_id=workflow_id)
        if new_id != workflow_id:
            try:
                delete_workflow(workflow_id)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到 workflow「{workflow_id}」")
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))
    from common.hub_operation_meta import remove, touch

    touch("workflow", new_id)
    if new_id != workflow_id:
        remove("workflow", workflow_id)
    return {"success": True, "id": new_id}


@router.delete("/api/workflows/{workflow_id}")
async def api_delete_workflow(workflow_id: str):
    from common.workflow_loader import delete_workflow

    try:
        delete_workflow(workflow_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    from common.hub_operation_meta import remove

    remove("workflow", workflow_id)
    return {"success": True}
