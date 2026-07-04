"""Projects 域路由（P3.1 Wave 2）。"""

from __future__ import annotations

import asyncio
import re
import time

from fastapi import APIRouter, HTTPException, Query

from hub.api.errors import APIError
from hub.services.kernel_run import (
    _clear_kernel_run,
    _get_kernel_run,
    _is_kernel_running,
    _set_kernel_run,
)
from hub.services.project_launch import (
    persist_project_launch,
    resume_kernel_bg,
    run_kernel_bg,
    slug,
    start_kernel_job,
)
from hub.services.project_service import get_project, get_project_log, list_projects
from config_store.skill_config import skill_config
from config_store.system_config import system_config

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
        from common.workflow.workflow_loader import load_workflow

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


@router.get("/run-status/{project_id}")
async def api_project_run_status(project_id: str):
    return _get_kernel_run(project_id)


@router.post("/{project_id}/dispatch")
async def api_project_dispatch(project_id: str, body: dict):
    agent_id = body.get("agent_id", "").strip()
    message = body.get("message", "").strip()
    task_id = body.get("task_id", "").strip()
    if not agent_id or not message:
        raise HTTPException(status_code=400, detail="agent_id 和 message 必填")

    from hub.services.notify_service import notify_via_project_group

    ok, msg = await asyncio.to_thread(
        notify_via_project_group, project_id, agent_id, message, task_id=task_id or None,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=msg or "dispatch 失败")
    return {"success": True, "message": msg}


@router.post("/{project_id}/resume")
async def api_project_resume(project_id: str):
    """断点续跑：回收孤儿响应后继续 DAG，无需重发项目。"""
    from common.store.store import Store

    store = Store()
    try:
        p = store.get_project(project_id)
    finally:
        store.close()
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    if _is_kernel_running(project_id):
        raise HTTPException(status_code=409, detail="该项目正在运行")
    status = p.get("status") or ""
    if status not in ("in_progress", "paused"):
        return {"resumed": False, "project_id": project_id, "reason": f"项目已终态（{status}）"}
    _set_kernel_run(project_id, running=True)
    try:
        start_kernel_job(project_id, resume_kernel_bg, project_id)
    except RuntimeError:
        _clear_kernel_run(project_id)
        raise HTTPException(status_code=409, detail="该项目正在运行")
    return {"resumed": True, "project_id": project_id}


@router.get("/{project_id}/deliverable/{task_id}")
async def api_project_deliverable(project_id: str, task_id: str):
    """任务交付物包：主文档 + workspace/legacy 文件清单（代码类任务产物在 agent workspace）。"""
    if not re.fullmatch(r"[\w-]{1,64}", task_id):
        raise HTTPException(status_code=400, detail="task_id 非法")
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise HTTPException(status_code=400, detail="project_id 非法")
    from common.project.project_artifacts import get_task_deliverable_bundle
    from common.store.store import Store

    bundle = get_task_deliverable_bundle(Store(), project_id, task_id)
    primary = bundle.get("primary") or {}
    # 兼容旧前端：保留 exists/content 顶栏字段
    bundle["exists"] = bool(primary.get("exists"))
    bundle["content"] = primary.get("content") or ""
    return bundle


@router.get("/{project_id}/deliverable/{task_id}/file")
async def api_project_deliverable_file(project_id: str, task_id: str, path: str = Query("")):
    """读取任务交付物包中的单个文件（workspace 或 legacy project 目录）。"""
    if not re.fullmatch(r"[\w-]{1,64}", task_id):
        raise APIError("INVALID_TASK_ID", "task_id 非法", status_code=400)
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise APIError("INVALID_PROJECT_ID", "project_id 非法", status_code=400)
    if not path or ".." in path:
        raise APIError("INVALID_PATH", "path 非法", status_code=400)
    from common.project.project_artifacts import read_task_artifact_file
    from common.store.store import Store

    return read_task_artifact_file(Store(), project_id, task_id, path)


@router.post("/{project_id}/pause")
async def api_project_pause(project_id: str):
    """暂停项目：停 CLI 子进程 + 调度，置 paused（可 resume 恢复，不丢上下文）。"""
    from common.project.project_runtime import get_project_runtime

    ok, msg = get_project_runtime().pause(project_id)
    if not ok:
        if msg == "项目不存在":
            raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
        if msg.startswith("项目已终态"):
            status = msg.split("：", 1)[-1] if "：" in msg else "unknown"
            return {"success": False, "status": status, "message": "项目已结束"}
        return {"success": False, "message": msg}
    _clear_kernel_run(project_id)
    return {"success": True, "project_id": project_id, "status": "paused"}


@router.post("/{project_id}/cancel")
async def api_project_cancel(project_id: str):
    """取消项目：Store 置 cancelled + cancel_event 终止当前 CLI 子进程 + 停止后续派发。"""
    from common.project.project_runtime import get_project_runtime

    ok, msg = get_project_runtime().cancel(project_id)
    if not ok:
        if msg == "项目不存在":
            raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
        if msg.startswith("项目已终态"):
            status = msg.split("：", 1)[-1] if "：" in msg else "unknown"
            return {"success": False, "status": status, "message": "项目已结束"}
        return {"success": False, "message": msg}
    _clear_kernel_run(project_id)
    return {"success": True, "project_id": project_id, "status": "cancelled"}


@router.delete("/{project_id}")
async def api_project_delete(project_id: str):
    """彻底删除项目：清 state.db 5 表 + agent 工作目录临时件 + 项目目录。运行中需先取消。"""
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise APIError("INVALID_PROJECT_ID", "project_id 非法")
    if _is_kernel_running(project_id):
        raise APIError("PROJECT_RUNNING", "项目运行中，请先取消再删除", status_code=409)
    from common.store.store import Store

    store = Store()
    try:
        if not store.get_project(project_id):
            raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
    finally:
        store.close()
    from common.project.project_admin import delete_project

    summary = delete_project(project_id)
    _clear_kernel_run(project_id)
    return {"success": True, "project_id": project_id, **summary}


# ── 项目初始化 / Demo / OBS 交付物（无 /api/projects 前缀） ─────

_extra_router = APIRouter(tags=["projects-extra"])


@_extra_router.post("/api/init")
async def api_init():
    """初始化所有 Agent 工作空间（幂等）。"""
    try:
        from common.runtime.run_kernel import cmd_init

        count = cmd_init()
        return {"success": True, "message": f"已完成 {count} 个 Agent 工作空间初始化"}
    except Exception as e:
        raise APIError("INIT_FAILED", f"初始化失败：{e}", hint="检查 agents_registry.json 配置")


@_extra_router.post("/api/demo")
async def api_demo():
    """在后台线程运行 demo 项目。"""
    from common.runtime.run_kernel import _read_demo_goal, _system_default_backend

    project_id = f"demo-ui-{int(time.time())}"
    if _is_kernel_running(project_id):
        raise APIError("PROJECT_RUNNING", "Demo 项目已在运行")
    demo_goal = _read_demo_goal()
    _system_default_backend()
    _set_kernel_run(project_id, running=True)
    try:
        start_kernel_job(
            project_id, run_kernel_bg,
            project_id, demo_goal, "one_shot", 100000, "Demo 项目", False,
        )
    except RuntimeError:
        _clear_kernel_run(project_id)
        raise APIError("PROJECT_RUNNING", "Demo 项目已在运行")
    return {"project_id": project_id, "started": True}


@_extra_router.get("/api/obs/projects/{project_id}/deliverables")
async def api_project_deliverables(project_id: str):
    """项目级交付物聚合列表：合并所有任务的 deliverable 文件树。"""
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise APIError("INVALID_PROJECT_ID", "project_id 非法")
    from common.project.project_artifacts import get_task_deliverable_bundle
    from common.store.store import Store

    store = Store()
    try:
        tasks = store.list_tasks(project_id)
        result = {}
        for t in tasks:
            tid = t["task_id"]
            bundle = get_task_deliverable_bundle(store, project_id, tid)
            files = bundle.get("files", [])
            primary = bundle.get("primary", {})
            result[tid] = {
                "task_id": tid,
                "name": t.get("name", ""),
                "agent": t.get("agent", ""),
                "status": t.get("status", ""),
                "deliverables": files,
                "primary": primary.get("content", "")[:200] if primary.get("exists") else "",
            }
        return {"project_id": project_id, "tasks": result}
    finally:
        store.close()
