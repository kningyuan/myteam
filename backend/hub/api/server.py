"""FastAPI 入口 — 薄路由层，业务逻辑在 base/ 与 hub/services/。"""

import asyncio
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import FileResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("需要安装依赖: pip install fastapi uvicorn")
    sys.exit(1)

from base.agent_chat import (
    _load_agents_config,
    clear_agent_chat_context,
    delete_agent,
    get_agent_backend_config,
    list_all_backends_with_models,
    scan_agents,
    set_agent_backend_config,
    stream_chat,
)
from base.agent_factory import generate_agent, suggest_agent_id
from base.group_manager import (
    add_member,
    bind_group_project,
    clear_group_messages,
    create_group,
    delete_group,
    dissolve_group,
    find_group_by_project,
    get_group,
    list_groups,
    remove_member,
    restore_group,
    search_groups,
    send_group_message,
)
from hub.paths import STATIC_DIR, resolve_workspace, to_relative_path
from hub.services.project_service import get_project, get_project_log, list_projects
from store.system_config import system_config
from store.skill_config import skill_config

app = FastAPI(title="Local Agent Chat v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from hub.api.observability_api import router as observability_router

app.include_router(observability_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    idx = STATIC_DIR / "index.html"
    return FileResponse(str(idx)) if idx.exists() else {"error": "no index"}


@app.get("/api/agents")
async def list_agents():
    return {"agents": scan_agents()}


@app.get("/api/agents/{agent_id}/config")
async def agent_config(agent_id: str):
    cfg = get_agent_backend_config(agent_id)
    return {"agent_id": agent_id, "backend": cfg.backend_id, "model": cfg.model}


@app.post("/api/agents/{agent_id}/config")
async def update_agent_config(agent_id: str, body: dict):
    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    set_agent_backend_config(agent_id, backend, model)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


@app.get("/api/backends")
async def list_backends():
    return {"backends": list_all_backends_with_models()}


@app.get("/api/config")
async def get_system_config():
    return {"config": system_config.get_all()}


@app.put("/api/config")
async def update_system_config(body: dict):
    config_data = body.get("config", {})
    if config_data:
        system_config.update_all(config_data)
    return {"success": True, "config": system_config.get_all()}


@app.get("/api/skill-config")
async def get_skill_config_api():
    return {"config": skill_config.get_all()}


@app.put("/api/skill-config")
async def update_skill_config_api(body: dict):
    config_data = body.get("config", {})
    if config_data:
        skill_config.update_all(config_data)
    return {"success": True, "config": skill_config.get_all()}


@app.get("/api/agents/registry")
async def get_agents_registry_api():
    from hub.services.agent_registry import get_agents_registry

    return get_agents_registry()


@app.post("/api/projects/{project_id}/setup-group")
async def api_setup_project_group(project_id: str, body: dict):
    from hub.services.project_group_service import setup_project_group

    team = body.get("team") or []
    project_name = body.get("project_name") or project_id
    ok, msg, group_id = await asyncio.to_thread(
        setup_project_group, project_id, team, project_name=project_name,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "group_id": group_id}


@app.post("/api/projects/{project_id}/group-message")
async def api_project_group_message(project_id: str, body: dict):
    from hub.services.project_group_service import format_progress_message, post_project_progress

    event_type = body.get("event_type", "group_notify")
    agent_id = body.get("agent_id", "")
    task_id = body.get("task_id", "")
    message = body.get("message", "").strip()
    extra = body.get("extra", "")

    if not message:
        message = format_progress_message(event_type, project_id, agent_id, task_id, extra)

    ok, result = await asyncio.to_thread(
        post_project_progress, project_id, message, sender=body.get("sender", "system"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail=result)
    return {"success": True, "group_id": result, "message": message}


@app.get("/api/agents/{agent_id}/detail")
async def agent_detail(agent_id: str):
    agent_cfg = _load_agents_config().get(agent_id, {})
    workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
    if not workspace.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 工作目录不存在")

    backend_cfg = get_agent_backend_config(agent_id)
    files = {}
    for fname in ["IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "HEARTBEAT.md"]:
        fp = workspace / fname
        if fp.exists():
            files[fname] = fp.read_text(encoding="utf-8")

    return {
        "agent_id": agent_id,
        "workspace": to_relative_path(workspace),
        "backend": backend_cfg.backend_id,
        "model": backend_cfg.model,
        "files": files,
    }


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    ok, msg = delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.put("/api/agents/{agent_id}/manage")
async def manage_agent_config(agent_id: str, body: dict):
    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    name = body.get("name")
    workspace = body.get("workspace")
    set_agent_backend_config(agent_id, backend, model, name=name, workspace=workspace)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


@app.get("/api/chat/{agent_id}")
async def chat(request: Request, agent_id: str, message: str = Query(..., description="用户消息")):
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    from hub.services.sse_bridge import stream_with_cancel

    def produce(cancel):
        try:
            for event_json in stream_chat(agent_id, message.strip(), cancel_event=cancel):
                yield event_json
        except Exception as e:
            yield json.dumps({"event": "error", "data": {"message": str(e)}}, ensure_ascii=False)

    async def event_stream():
        try:
            async for event_json in stream_with_cancel(request, produce):
                yield f"data: {event_json}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/{agent_id}/clear")
async def api_clear_chat(agent_id: str):
    ok, msg = clear_agent_chat_context(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/chat/{agent_id}/archive")
async def api_archive_chat(agent_id: str, body: dict):
    from hub.services.chat_archive import hide_chat

    snapshot = body.get("snapshot")
    entry = hide_chat(agent_id, snapshot)
    return {"success": True, "entry": entry}


@app.post("/api/chat/{agent_id}/restore")
async def api_restore_chat(agent_id: str):
    from hub.services.chat_archive import restore_chat

    ok, msg, snapshot = restore_chat(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg, "snapshot": snapshot}


@app.get("/api/chat/archives/search")
async def api_search_chat_archives(q: str = Query("")):
    from hub.services.chat_archive import search_archives

    return {"results": search_archives(q)}


@app.get("/api/groups/search")
async def api_search_groups(q: str = Query(""), include_dissolved: bool = True):
    return {"groups": search_groups(q, include_dissolved=include_dissolved)}


@app.post("/api/groups/{group_id}/dissolve")
async def api_dissolve_group(group_id: str):
    ok, msg = dissolve_group(group_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/groups/{group_id}/restore")
async def api_restore_group(group_id: str):
    ok, msg = restore_group(group_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/groups")
async def list_all_groups():
    return {"groups": list_groups()}


@app.post("/api/groups")
async def api_create_group(body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="群组名不能为空")
    group = create_group(name, body.get("description", ""), body.get("project_id"))
    return {"success": True, "group": group}


@app.post("/api/groups/{group_id}/bind-project")
async def api_bind_group_project(group_id: str, body: dict):
    project_id = body.get("project_id", "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")
    ok, msg = bind_group_project(group_id, project_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/agents/{agent_id}/notify")
async def api_agent_notify(agent_id: str, body: dict):
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    from hub.services.notify_service import notify_agent_sync, notify_via_project_group

    timeout = int(body.get("timeout", 1800))
    wait_response = bool(body.get("wait_response", body.get("deliver", False)))
    project_id = body.get("project_id") or None
    task_id = body.get("task_id") or None
    response_file = body.get("response_file") or None

    # 后台通知：异步发送消息，agent 回复直接写入 response_file
    if not wait_response and response_file:
        import threading
        from hub.services.notify_service import _collect_text_and_write_file
        t = threading.Thread(
            target=_collect_text_and_write_file,
            args=(agent_id, message, response_file, timeout),
            daemon=True,
        )
        t.start()
        return {"success": True, "response": "", "async": True}

    if project_id and task_id and not wait_response:
        ok, resp = await asyncio.to_thread(
            notify_via_project_group, project_id, agent_id, message, task_id=task_id,
        )
    else:
        ok, resp = await asyncio.to_thread(
            notify_agent_sync,
            agent_id,
            message,
            timeout=timeout,
            project_id=project_id,
            task_id=task_id,
            wait_response=wait_response,
        )

    if not ok:
        raise HTTPException(status_code=502, detail=resp or "Agent 通知失败")
    return {"success": True, "response": resp}


@app.post("/api/projects/{project_id}/dispatch")
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


@app.delete("/api/groups/{group_id}")
async def api_delete_group(group_id: str):
    if not delete_group(group_id):
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"success": True}


@app.get("/api/groups/{group_id}")
async def api_get_group(group_id: str):
    g = get_group(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"group": g}


@app.post("/api/groups/{group_id}/members")
async def api_add_member(group_id: str, body: dict):
    agent_id = body.get("agent_id", "")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id 不能为空")
    ok, msg = add_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.delete("/api/groups/{group_id}/members/{agent_id}")
async def api_remove_member(group_id: str, agent_id: str):
    ok, msg = remove_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/groups/{group_id}/clear")
async def api_clear_group(group_id: str):
    ok, msg = clear_group_messages(group_id)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/groups/{group_id}/chat")
async def group_chat(
    request: Request,
    group_id: str,
    sender: str = Query("user", description="发送者"),
    text: str = Query(..., description="消息内容"),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    from hub.services.sse_bridge import stream_with_cancel

    def produce(cancel):
        try:
            for evt in send_group_message(group_id, sender, text, cancel_event=cancel):
                yield json.dumps(evt, ensure_ascii=False)
        except Exception as e:
            yield json.dumps({"event": "error", "data": {"message": str(e)}}, ensure_ascii=False)

    async def event_stream():
        try:
            async for event_json in stream_with_cancel(request, produce):
                yield f"data: {event_json}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/groups/{group_id}/events")
async def group_events_stream(request: Request, group_id: str):
    """订阅群组实时事件（任务 dispatch 时推送 agent_thinking）。"""
    from hub.services.group_broadcast import subscribe, unsubscribe

    if not get_group(group_id):
        raise HTTPException(status_code=404, detail="群组不存在")

    queue = subscribe(group_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            unsubscribe(group_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/agents/{agent_id}/events")
async def agent_events_stream(request: Request, agent_id: str):
    """订阅 Agent 后台任务执行流（对标 openclaw send_to_user 私信流）。"""
    from hub.services.agent_broadcast import subscribe, unsubscribe

    if agent_id not in {a["id"] for a in scan_agents()}:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    queue = subscribe(agent_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            unsubscribe(agent_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/projects")
async def api_list_projects():
    return {"projects": list_projects()}


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: str):
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": p}


@app.get("/api/projects/{project_id}/log")
async def api_project_log(project_id: str, tail: int = Query(500, ge=1, le=5000)):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project_id, "log": get_project_log(project_id, tail=tail)}


# ── 发起项目：UI → 编排内核（后台线程跑 run_kernel）──────────────
_KERNEL_RUNS: dict[str, dict] = {}  # project_id -> {running, error}


def _slug(text: str, limit: int = 24) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]", "", (text or "").strip().replace(" ", "_"))
    return s[:limit] or "project"


def _run_kernel_bg(project_id: str, goal: str, mode: str, budget, title: str,
                   review: bool = False) -> None:
    try:
        from common.run_kernel import run_project
        run_project(project_id, goal=goal, title=title, mode=mode, token_budget=budget,
                    review=review)
    except Exception as e:  # noqa: BLE001 — 后台线程，错误回灌给状态查询
        _KERNEL_RUNS[project_id] = {"running": False, "error": str(e)}
    else:
        _KERNEL_RUNS[project_id] = {"running": False, "error": None}


@app.post("/api/projects/run")
async def api_project_run(body: dict):
    """从 UI 发起一个项目：装配并在后台线程跑编排内核，立即返回 project_id。"""
    goal = (body.get("goal") or "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="goal 必填")
    mode = body.get("mode") or "one_shot"
    if mode not in ("one_shot", "recurring"):
        raise HTTPException(status_code=400, detail="mode 非法")
    try:
        budget = int(body.get("budget")) if body.get("budget") else None
    except (TypeError, ValueError):
        budget = None
    title = (body.get("title") or "").strip()
    review = bool(body.get("review"))
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        project_id = f"ui_{_slug(title or goal)}_{time.strftime('%Y%m%d_%H%M%S')}"
    if _KERNEL_RUNS.get(project_id, {}).get("running"):
        raise HTTPException(status_code=409, detail="该项目正在运行")
    _KERNEL_RUNS[project_id] = {"running": True, "error": None}
    threading.Thread(
        target=_run_kernel_bg, args=(project_id, goal, mode, budget, title, review),
        daemon=True
    ).start()
    return {"project_id": project_id, "title": title or project_id, "started": True}


@app.get("/api/projects/run-status/{project_id}")
async def api_project_run_status(project_id: str):
    return _KERNEL_RUNS.get(project_id, {"running": False, "error": None})


@app.get("/api/projects/{project_id}/deliverable/{task_id}")
async def api_project_deliverable(project_id: str, task_id: str):
    """读取某任务的交付物正文（business/tasks/project/<id>/deliverables/<task>_deliverable.md）。"""
    if not re.fullmatch(r"[\w-]{1,64}", task_id):
        raise HTTPException(status_code=400, detail="task_id 非法")
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise HTTPException(status_code=400, detail="project_id 非法")
    from hub.paths import PROJECTS_DIR
    path = PROJECTS_DIR / project_id / "deliverables" / f"{task_id}_deliverable.md"
    if not path.is_file():
        return {"task_id": task_id, "exists": False, "content": ""}
    try:
        return {"task_id": task_id, "exists": True, "content": path.read_text(encoding="utf-8")}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


_PROJECT_TERMINAL = {"completed", "failed", "partially_failed", "aborted", "cancelled", "paused"}


@app.post("/api/projects/{project_id}/cancel")
async def api_project_cancel(project_id: str):
    """协作式取消：把项目状态置 cancelled，运行中的内核在任务间隙观察后停止派发。

    注意：正在执行的当前任务（opencode 子进程）会自然跑完，之后不再派发新任务。
    """
    from common.store import Store
    store = Store()
    try:
        proj = store.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")
        if proj.get("status") in _PROJECT_TERMINAL:
            return {"success": False, "status": proj.get("status"), "message": "项目已结束"}
        store.set_project_status(project_id, "cancelled")
    finally:
        store.close()
    return {"success": True, "project_id": project_id, "status": "cancelled"}


@app.delete("/api/projects/{project_id}")
async def api_project_delete(project_id: str):
    """彻底删除项目：清 state.db 5 表 + agent 工作目录临时件 + 项目目录。运行中需先取消。"""
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise HTTPException(status_code=400, detail="project_id 非法")
    if _KERNEL_RUNS.get(project_id, {}).get("running"):
        raise HTTPException(status_code=409, detail="项目运行中，请先取消再删除")
    from common.store import Store
    store = Store()
    try:
        if not store.get_project(project_id):
            raise HTTPException(status_code=404, detail="项目不存在")
    finally:
        store.close()
    from common.project_admin import delete_project
    summary = delete_project(project_id)
    _KERNEL_RUNS.pop(project_id, None)
    return {"success": True, "project_id": project_id, **summary}


@app.get("/api/agents/{agent_id}/chats")
async def api_agent_background_chats(agent_id: str):
    """获取 Agent 的后台执行私聊记录（持久化的 .chat 文件）。"""
    from hub.paths import WORKSPACES_DIR
    chat_dir = WORKSPACES_DIR / f"workspace-{agent_id}" / ".chats"
    msgs = []
    if chat_dir.is_dir():
        for f in sorted(chat_dir.iterdir(), key=lambda p: p.stat().st_mtime):
            if f.suffix == ".chat":
                try:
                    msgs.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    pass
    return {"messages": msgs}


@app.post("/api/agents/create")
async def api_create_agent(body: dict):
    description = body.get("description", "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="Agent 描述不能为空")

    agent_id = body.get("agent_id", "").strip() or suggest_agent_id(description)
    result = generate_agent(
        agent_id,
        description,
        body.get("backend", "opencode"),
        body.get("model", ""),
        body.get("chinese_name", ""),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return {"success": True, "agent": result}


@app.get("/api/agents/suggest-id")
async def api_suggest_id(description: str = Query("")):
    return {"suggested_id": suggest_agent_id(description)}


def main():
    port = int(os.environ.get("LOCAL_AGENT_PORT", "8765"))
    print("  Local Agent Chat v2")
    print(f"  http://localhost:{port}")
    print(f"  Agents: http://localhost:{port}/api/agents")
    print(f"  Backends: http://localhost:{port}/api/backends")
    print(f"  Groups: http://localhost:{port}/api/groups")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
