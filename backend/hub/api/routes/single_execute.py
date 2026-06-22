"""单 Agent execute Hub API — Layer B 无 Workflow 任务。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from hub.services.single_execute_service import (
    finish_single_execute,
    get_single_execute_task,
    list_single_execute_projects,
    prepare_single_execute,
)

router = APIRouter(prefix="/api/single-execute", tags=["single-execute"])


@router.get("")
async def api_list_single_execute():
    return {"projects": list_single_execute_projects()}


@router.get("/{project_id}/{task_id}")
async def api_get_single_execute_task(project_id: str, task_id: str):
    detail = get_single_execute_task(project_id, task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    return detail


@router.post("/prepare")
async def api_prepare_single_execute(body: dict):
    project_id = (body.get("project_id") or "").strip()
    task_id = (body.get("task_id") or "").strip()
    if not project_id or not task_id:
        raise HTTPException(status_code=400, detail="project_id 与 task_id 必填")
    return prepare_single_execute(
        project_id=project_id,
        task_id=task_id,
        agent_id=str(body.get("agent_id") or "product"),
        task_type=str(body.get("task_type") or "research"),
        intent=str(body.get("intent") or "单 agent execute 质量验证任务"),
    )


@router.post("/finish")
async def api_finish_single_execute(body: dict):
    project_id = (body.get("project_id") or "").strip()
    task_id = (body.get("task_id") or "").strip()
    if not project_id or not task_id:
        raise HTTPException(status_code=400, detail="project_id 与 task_id 必填")
    result = finish_single_execute(
        project_id=project_id,
        task_id=task_id,
        agent_id=str(body.get("agent_id") or "product"),
        task_type=str(body.get("task_type") or "research"),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "finish 失败")
    return result
