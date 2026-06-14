"""Projects 域路由（P3.1 Wave 2）。"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query

from hub.api.errors import APIError
from hub.services.kernel_run import (
    _clear_kernel_run,
    _is_kernel_running,
    _set_kernel_run,
)
from hub.services.project_launch import (
    persist_project_launch,
    run_kernel_bg,
    slug,
    start_kernel_job,
)
from hub.services.project_service import get_project, get_project_log, list_projects
from store.skill_config import skill_config
from store.system_config import system_config

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def api_list_projects():
    return {"projects": list_projects()}


@router.post("/run")
async def api_project_run(body: dict):
    """从 UI 发起一个项目：装配并在后台线程跑编排内核，立即返回 project_id。"""
    goal = (body.get("goal") or "").strip()
    if not goal:
        raise APIError("INVALID_GOAL", "Goal 不能为空", hint="填写项目目标")
    mode = body.get("mode") or "one_shot"
    if mode not in ("one_shot", "recurring"):
        raise APIError("INVALID_MODE", f"不支持的 mode: {mode}")
    try:
        budget = int(body.get("budget")) if body.get("budget") else None
    except (TypeError, ValueError):
        budget = None
    title = (body.get("title") or "").strip()
    review = bool(body.get("review"))
    split = bool(body.get("split"))
    workflow = (body.get("workflow") or "").strip() or None
    max_cycles = None
    if mode == "recurring" and body.get("max_cycles") is not None:
        try:
            max_cycles = int(body.get("max_cycles"))
            if max_cycles < 1:
                max_cycles = None
        except (TypeError, ValueError):
            max_cycles = None
    process_defaults = skill_config.get_all().get("process_defaults") or {}
    if workflow:
        from common.workflow_loader import load_workflow

        try:
            load_workflow(workflow)
        except (FileNotFoundError, ValueError) as e:
            raise APIError("INVALID_WORKFLOW", str(e), hint="选择有效的 workflow 或留空")
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        project_id = f"ui_{slug(title or goal)}_{time.strftime('%Y%m%d_%H%M%S')}"
    if _is_kernel_running(project_id):
        raise HTTPException(status_code=409, detail="该项目正在运行")
    backend = system_config.get("system", "default_backend", default="opencode")
    persist_project_launch(
        project_id,
        title=title or project_id,
        goal=goal,
        mode=mode,
        budget=budget,
        workflow=workflow,
        review=review,
        split=split,
        backend=backend,
        max_cycles=max_cycles,
    )
    _set_kernel_run(project_id, running=True)
    try:
        start_kernel_job(
            project_id,
            run_kernel_bg,
            project_id,
            goal,
            mode,
            budget,
            title,
            review,
            workflow,
            split,
            process_defaults,
            max_cycles,
        )
    except RuntimeError:
        _clear_kernel_run(project_id)
        raise HTTPException(status_code=409, detail="该项目正在运行")
    return {
        "project_id": project_id,
        "title": title or project_id,
        "started": True,
        "workflow": workflow,
    }


@router.get("/{project_id}")
async def api_get_project(project_id: str):
    p = get_project(project_id)
    if not p:
        raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
    return {"project": p}


@router.get("/{project_id}/log")
async def api_project_log(project_id: str, tail: int = Query(500, ge=1, le=5000)):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project_id, "log": get_project_log(project_id, tail=tail)}
