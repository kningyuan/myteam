"""FastAPI 入口 — 薄路由层，业务逻辑在 base/ 与 hub/services/。"""

import asyncio
import json
import os
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("需要安装依赖: pip install fastapi uvicorn")
    sys.exit(1)

from base.agent_chat import (
    _load_agents_config,
    apply_model_to_all,
    clear_agent_chat_context,
    delete_agent,
    get_agent_backend_config,
    get_backend_models,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan 上下文：启动恢复 + 关闭清理。"""
    threading.Thread(target=_auto_resume_on_startup, daemon=True).start()
    yield


def _auto_resume_on_startup() -> None:
    try:
        n_stale = _reconcile_stale_kernel_runs()
        if n_stale:
            print(f"[myteam] 清除 {n_stale} 个 Hub 重启残留的 kernel 运行标记")
        from common.agent_port import reconcile_on_start
        from common.store import Store
        from common.workspace_gc import gc_workspace
        from common.run_kernel import resume_in_progress_projects
        store = Store()
        try:
            reconcile_on_start(store)  # 先对账再 gc，避免误删可采纳孤儿 .response
            gc_workspace(store)
        finally:
            store.close()
        # 续跑期间同步运行态：让 run-status 在自动续跑时正确报 running=true，
        # 并使续跑端点的并发守卫生效（堵住启动线程 vs 用户点击的二次续跑）。
        def _mark_run(pid):
            _set_kernel_run(pid, running=True)

        def _clear_run(pid, err):
            _set_kernel_run(pid, running=False, error=str(err) if err else None)

        resumed = resume_in_progress_projects(on_start=_mark_run, on_end=_clear_run)
        if resumed:
            print(f"[myteam] 自动续跑 {len(resumed)} 个中断项目: {', '.join(resumed)}")
        # 扫描 orphan job
        try:
            from common.job_supervisor import JobSupervisor
            jsv = JobSupervisor(store)
            orphans = jsv.resume_orphans()
            if orphans:
                print(f"[myteam] 标记 {len(orphans)} 个 orphan job: {[o['project_id'] for o in orphans]}")
        except Exception:
            pass
    except Exception as e:
        print(f"[myteam] 自动续跑失败: {e}")


class APIError(Exception):
    """统一 API 错误，含机器可读 code、人话 message、建议动作 hint、排查链接 doc_url。"""
    def __init__(self, code: str, message: str, hint: str = "", doc_url: str = "", status_code: int = 400):
        self.code = code
        self.message = message
        self.hint = hint
        self.doc_url = doc_url
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "hint": self.hint,
                "doc_url": self.doc_url,
            }
        }


ERROR_CODES = {
    "WORKSPACE_NOT_FOUND":     (404, "找不到 agent 工作空间", "执行 --init"),
    "CONFIG_NOT_FOUND":        (404, "缺少配置文件", "执行 --init"),
    "PLAN_OUT_OF_BOUNDS":      (400, "规划分配了名册外 agent", "检查 registry"),
    "CLI_EXECUTION_FAILED":    (502, "CLI 后端执行失败", "检查 CLI 安装"),
    "PROJECT_NOT_FOUND":       (404, "项目不存在", "检查项目 ID"),
    "PROJECT_RUNNING":         (409, "项目正在运行中", "等待完成或先取消"),
    "DELIVERABLE_NOT_FOUND":   (404, "交付物不存在或尚未就绪", "等待任务完成"),
    "INVALID_GOAL":            (400, "Goal 不能为空", "填写项目目标"),
}


app = FastAPI(title="Local Agent Chat v2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from hub.api.observability_api import router as observability_router

app.include_router(observability_router)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(HTTPException)
async def http_exception_envelope(request: Request, exc: HTTPException):
    """手抛的 fastapi.HTTPException 归一化为统一 error 信封（落实 api-reference.md 附录 B），
    同时保留 detail 向后兼容。仅接管代码里手抛的 fastapi 异常；Starlette 路由 404 /
    校验 422（RequestValidationError）是不同异常类，仍走默认形状，不误伤。"""
    return JSONResponse(status_code=exc.status_code, content={
        "error": {"code": f"HTTP_{exc.status_code}", "message": exc.detail,
                  "hint": "", "doc_url": ""},
        "detail": exc.detail,  # 向后兼容：旧前端 / 现有测试仍读 detail
    })


# ── 系统状态（R3-3 Home 趋势微标） ──────────────────
@app.get("/api/status")
async def api_status():
    from common.paths import WORKSPACES_DIR
    initialized = WORKSPACES_DIR.is_dir() and any(WORKSPACES_DIR.iterdir())
    store = _we_store()
    projects = store.list_projects()
    total = len(projects)
    running = sum(1 for p in projects if p.get("status") == "in_progress")
    monthly_tokens = sum(p.get("meta", {}).get("tokens", 0) if isinstance(p.get("meta"), dict) else 0 for p in projects)
    return {
        "status": "ok",
        "initialized": initialized,
        "project_count": total,
        "running_count": running,
        "version": "1.0.0",
        "trends": {
            "project_count": {"direction": "up" if total > 0 else "flat", "value": total},
            "running_count": {"direction": "flat", "value": running},
            "monthly_tokens": {"direction": "up" if monthly_tokens > 0 else "flat", "value": 0},
            "cumulative_cost": {"direction": "flat", "value": 0},
        },
    }


# ── WorkspaceEvent（R2-1） ─────────────────────────────
from common.store import Store as _Store

_WE_STORE = None

def _we_store():
    global _WE_STORE
    if _WE_STORE is None:
        _WE_STORE = _Store()
    return _WE_STORE


@app.get("/api/workspace/events")
async def api_workspace_events(project_id: str = "", type: str = "", limit: int = 50):
    store = _we_store()
    events = store.list_workspace_events(
        project_id=project_id or None,
        type=type or None,
        limit=min(limit, 200),
    )
    return {"events": events}


@app.get("/api/workspace/events/stream")
async def api_workspace_events_stream(request: Request, project_id: str = ""):
    """WorkspaceEvent SSE 流。轮询最新事件推送到前端。"""
    async def event_stream():
        last_id = ""
        while True:
            if await request.is_disconnected():
                break
            store = _we_store()
            events = store.list_workspace_events(
                project_id=project_id or None,
                limit=20,
            )
            fresh = [e for e in events if e["id"] != last_id]
            if fresh:
                last_id = fresh[0]["id"]
                for e in reversed(fresh):
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Channels（R2-2） ─────────────────────────────────
@app.get("/api/workspace/channels")
async def api_list_channels(project_id: str = ""):
    store = _we_store()
    if project_id:
        conv = store.get_conversation(f"channel/project-{project_id}")
        channels = [conv] if conv else []
    else:
        # fallback: scan conversations via raw query
        rows = store._conn.execute(
            "SELECT * FROM conversation ORDER BY updated_at DESC"
        ).fetchall()
        channels = [dict(r) for r in rows]
    return {"channels": [
        {
            "channel_id": c.get("conversation_id", c.get("conversation_id", "")),
            "kind": c.get("kind", ""),
            "project_id": c.get("project_id", ""),
            "title": c.get("title", ""),
            "last_activity": c.get("updated_at", ""),
        }
        for c in channels
    ]}


@app.post("/api/workspace/channels")
async def api_create_channel(body: dict):
    kind = body.get("kind", "project")
    project_id = body.get("project_id", "")
    title = body.get("title", "新频道")
    channel_id = f"channel/project-{project_id}" if kind == "project" else f"direct/{body.get('agent_id', '')}"
    store = _we_store()
    store.create_conversation(
        channel_id,
        kind=kind,
        participants=body.get("members", []),
        project_id=project_id,
        title=title,
    )
    return {"channel_id": channel_id, "created": True}


@app.get("/api/workspace/channels/{channel_id}/messages")
async def api_channel_messages(channel_id: str, limit: int = 50):
    if ".." in channel_id or "/" in channel_id.strip("/"):
        raise APIError("INVALID_CHANNEL", "channel_id 非法")
    store = _we_store()
    msgs = store.list_messages(channel_id, limit=limit)
    return {"messages": msgs}


@app.post("/api/workspace/channels/{channel_id}/messages")
async def api_channel_post_message(channel_id: str, body: dict):
    if ".." in channel_id or "/" in channel_id.strip("/"):
        raise APIError("INVALID_CHANNEL", "channel_id 非法")
    store = _we_store()
    from common.store import _now
    seq = store.append_message(
        channel_id,
        role="user" if body.get("author") != "agent" else "agent",
        author=body.get("author", "user"),
        text=body.get("content", ""),
    )
    # @mention → WorkspaceEvent
    content = body.get("content", "")
    mentions = [w.lstrip("@") for w in content.split() if w.startswith("@") and len(w) > 1]
    if mentions:
        store.append_workspace_event({
            "type": "chat.message.posted",
            "source": "hub/channel",
            "target": channel_id,
            "payload": json.dumps({"author": body.get("author"), "text": content, "mentions": mentions}),
            "metadata": json.dumps({"channel_id": channel_id}),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    return {"message_id": seq, "seq": seq, "created_at": _now()}


# ── Jobs（R2-3） ─────────────────────────────────
@app.get("/api/jobs")
async def api_list_jobs(status: str = ""):
    store = _we_store()
    jobs = store.list_jobs(status=status)
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    store = _we_store()
    row = store._conn.execute(
        "SELECT * FROM job WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        raise APIError("JOB_NOT_FOUND", f"Job {job_id} 不存在", status_code=404)
    return dict(row)


# ── Agent Runtime（R2-3） ─────────────────────────
@app.get("/api/obs/agents")
async def api_list_agent_runtimes():
    store = _we_store()
    runtimes = store.list_agent_runtimes()
    return {"agents": runtimes}


@app.get("/api/obs/agents/{agent_id}")
async def api_get_agent_runtime(agent_id: str):
    store = _we_store()
    rt = store.get_agent_runtime(agent_id)
    if not rt:
        # fallback: return offline status
        rt = {"agent_id": agent_id, "status": "offline", "workspace_ok": 1}
    return rt


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


@app.post("/api/agents/apply-model")
async def api_apply_model(body: dict):
    backend = body.get("backend", "opencode")
    model = (body.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    result = apply_model_to_all(backend, model)
    return {"success": True, **result}


@app.get("/api/backends")
async def list_backends():
    return {"backends": list_all_backends_with_models()}


@app.get("/api/backends/{backend_id}/models")
async def list_backend_models(backend_id: str, refresh: bool = False):
    try:
        models = get_backend_models(backend_id, refresh=refresh)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"unknown backend: {backend_id}")
    return {"backend_id": backend_id, "models": models, "refreshed": bool(refresh)}


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
@app.get("/api/skill_config")
async def get_skill_config_api():
    return {"config": skill_config.get_all()}


@app.put("/api/skill-config")
@app.put("/api/skill_config")
async def update_skill_config_api(body: dict):
    config_data = body.get("config", {})
    if config_data:
        skill_config.update_all(config_data)
        from common.skill_settings import reload_skill_settings

        reload_skill_settings()
    return {"success": True, "config": skill_config.get_all()}


@app.get("/api/agents/registry")
async def get_agents_registry_api():
    from hub.services.agent_registry import get_agents_registry

    return get_agents_registry()


@app.post("/api/agents/sync-task-types")
async def api_sync_agent_task_types():
    """为未配置 task_types 的 Agent 从名册/PGD/描述规则补全。"""
    from hub.services.agent_registry import sync_missing_agent_task_types

    return sync_missing_agent_task_types(only_empty=True)


@app.post("/api/agents/suggest-task-types")
async def api_suggest_agent_task_types(body: dict):
    from common.agent_task_type_suggest import suggest_task_types_for_agent

    desc = (body.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="description 不能为空")
    try:
        return suggest_task_types_for_agent(
            desc,
            name=(body.get("name") or "").strip(),
            agent_id=(body.get("agent_id") or "").strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    from hub.services.agent_registry import update_agent_task_types

    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    name = body.get("name")
    workspace = body.get("workspace")
    set_agent_backend_config(agent_id, backend, model, name=name, workspace=workspace)
    if "task_types" in body:
        tts = body.get("task_types") or []
        if not isinstance(tts, list):
            raise HTTPException(status_code=400, detail="task_types 须为数组")
        result = update_agent_task_types(agent_id, [str(t).strip() for t in tts if str(t).strip()])
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "更新 task_types 失败"))
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


@app.get("/api/chat/{agent_id}")
async def chat(request: Request, agent_id: str, message: str = Query(..., description="用户消息")):
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    from hub.services.sse_bridge import stream_with_cancel

    def produce(cancel):
        try:
            for event_json in stream_chat(agent_id, message.strip(), cancel_event=cancel,
                                          use_memory=True):
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


@app.get("/api/chat/{agent_id}/messages")
async def api_chat_messages(agent_id: str, limit: int = Query(200, ge=1, le=2000)):
    """DM 会话历史（P0 记忆地基）——从 Store 的 message 表读，前端据此渲染对话流。"""
    from common.store import Store
    store = Store()
    try:
        conv_id = f"dm:{agent_id}"
        msgs = store.list_messages(conv_id)
        if limit and len(msgs) > limit:
            msgs = msgs[-limit:]
        out = [{
            "seq": m["seq"], "role": m["role"], "author": m.get("author", ""),
            "text": m.get("text", ""), "parts": m.get("parts"),
            "created_at": m.get("created_at", ""),
        } for m in msgs]
    finally:
        store.close()
    return {"agent_id": agent_id, "conversation_id": conv_id, "messages": out}


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
        raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
    return {"project": p}


@app.get("/api/projects/{project_id}/log")
async def api_project_log(project_id: str, tail: int = Query(500, ge=1, le=5000)):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project_id, "log": get_project_log(project_id, tail=tail)}


# ── 发起项目：UI → 编排内核（后台线程跑 run_kernel）──────────────
_KERNEL_RUNS: dict[str, dict] = {}  # project_id -> {running, error}（进程内缓存）


def _set_kernel_run(project_id: str, *, running: bool, error: Optional[str] = None) -> None:
    """内存态 + project.meta.hub_kernel_run 双写，Hub 重启后可 reconcile。"""
    _KERNEL_RUNS[project_id] = {"running": running, "error": error}
    try:
        from common.store import Store

        store = Store()
        try:
            if store.get_project(project_id):
                store.update_project_meta(
                    project_id,
                    hub_kernel_run={"running": running, "error": error},
                )
        finally:
            store.close()
    except Exception:
        pass


def _get_kernel_run(project_id: str) -> dict:
    cached = _KERNEL_RUNS.get(project_id)
    if cached is not None:
        return cached
    try:
        from common.store import Store

        store = Store()
        try:
            proj = store.get_project(project_id) or {}
            meta = proj.get("meta") or {}
            hub = meta.get("hub_kernel_run") or {}
            err = hub.get("error") or meta.get("launch_error")
            if hub.get("running") or err:
                return {"running": bool(hub.get("running")), "error": err}
        finally:
            store.close()
    except Exception:
        pass
    return {"running": False, "error": None}


def _is_kernel_running(project_id: str) -> bool:
    return bool(_get_kernel_run(project_id).get("running"))


def _clear_kernel_run(project_id: str) -> None:
    _KERNEL_RUNS.pop(project_id, None)
    try:
        from common.store import Store

        store = Store()
        try:
            if store.get_project(project_id):
                store.update_project_meta(
                    project_id,
                    hub_kernel_run={"running": False, "error": None},
                )
        finally:
            store.close()
    except Exception:
        pass


def _reconcile_stale_kernel_runs() -> int:
    """Hub 重启：清除 meta 中残留的 running=true。"""
    cleared = 0
    try:
        from common.store import Store

        store = Store()
        try:
            for proj in store.list_projects():
                meta = proj.get("meta") or {}
                hub_run = meta.get("hub_kernel_run") or {}
                if hub_run.get("running"):
                    store.update_project_meta(
                        proj["project_id"],
                        hub_kernel_run={"running": False, "error": "hub_restarted"},
                    )
                    cleared += 1
        finally:
            store.close()
    except Exception:
        pass
    return cleared


@app.post("/api/init")
async def api_init():
    """初始化所有 Agent 工作空间（幂等）。"""
    try:
        from common.run_kernel import cmd_init
        count = cmd_init()
        return {"success": True, "message": f"已完成 {count} 个 Agent 工作空间初始化"}
    except Exception as e:
        raise APIError("INIT_FAILED", f"初始化失败：{e}", hint="检查 agents_registry.json 配置")


@app.post("/api/demo")
async def api_demo():
    """在后台线程运行 demo 项目。"""
    from common.run_kernel import _read_demo_goal, _system_default_backend
    project_id = f"demo-ui-{int(time.time())}"
    if _is_kernel_running(project_id):
        raise APIError("PROJECT_RUNNING", "Demo 项目已在运行")
    demo_goal = _read_demo_goal()
    backend = _system_default_backend()
    _set_kernel_run(project_id, running=True)
    threading.Thread(
        target=_run_kernel_bg, args=(project_id, demo_goal, "one_shot", 100000, "Demo 项目", False),
        daemon=True
    ).start()
    return {"project_id": project_id, "started": True}


def _slug(text: str, limit: int = 24) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]", "", (text or "").strip().replace(" ", "_"))
    return s[:limit] or "project"


def _persist_project_launch(
    project_id: str,
    *,
    title: str,
    goal: str,
    mode: str,
    budget,
    workflow: Optional[str] = None,
) -> None:
    """发起瞬间写入 SQLite，避免仅后台线程落库导致刷新后项目列表为空。"""
    from common.store import Store

    meta: dict = {
        "goal": goal,
        "token_budget": budget,
        "hub_kernel_run": {"running": True, "error": None},
    }
    if workflow:
        meta["workflow"] = workflow
    store = Store()
    try:
        store.upsert_project(
            project_id,
            title=title or project_id,
            mode=mode,
            status="in_progress",
            meta=meta,
        )
    finally:
        store.close()


def _mark_project_kernel_failed(project_id: str, error: str) -> None:
    from common.store import Store

    store = Store()
    try:
        if store.get_project(project_id):
            store.set_project_status(project_id, "failed")
            store.update_project_meta(project_id, launch_error=error)
    finally:
        store.close()


def _run_kernel_bg(project_id: str, goal: str, mode: str, budget, title: str,
                   review: bool = False, workflow: Optional[str] = None,
                   split: bool = False, process_defaults: Optional[dict] = None) -> None:
    try:
        from common.kernel_config import kernel_configs_for_run
        from common.run_kernel import run_project
        defaults = process_defaults or {}
        backend = system_config.get("system", "default_backend", default="opencode")
        proc_cfg, wdog_cfg = kernel_configs_for_run(
            defaults, mode=mode, token_budget=budget, review=review,
            split=split, backend=backend,
        )
        run_project(project_id, goal=goal, title=title, mode=mode, token_budget=budget,
                    review=review, workflow=workflow, split=split,
                    config=proc_cfg, watchdog=wdog_cfg, backend=backend)
    except Exception as e:  # noqa: BLE001 — 后台线程，错误回灌给状态查询
        _set_kernel_run(project_id, running=False, error=str(e))
        _mark_project_kernel_failed(project_id, str(e))
    else:
        _set_kernel_run(project_id, running=False)


def _resume_kernel_bg(project_id: str) -> None:
    try:
        from common.kernel_config import kernel_configs_for_run
        from common.run_kernel import resume_project
        from common.store import Store

        defaults = skill_config.get_all().get("process_defaults") or {}
        backend = system_config.get("system", "default_backend", default="opencode")
        store = Store()
        try:
            meta = (store.get_project(project_id) or {}).get("meta") or {}
            proc_cfg, wdog_cfg = kernel_configs_for_run(
                defaults,
                mode=meta.get("mode") or "one_shot",
                token_budget=meta.get("token_budget"),
                backend=backend,
            )
        finally:
            store.close()
        resume_project(project_id, config=proc_cfg, watchdog=wdog_cfg, backend=backend)
    except Exception as e:  # noqa: BLE001
        _set_kernel_run(project_id, running=False, error=str(e))
    else:
        _set_kernel_run(project_id, running=False)


@app.get("/api/task-types")
async def api_list_task_types():
    """任务类型注册表（templates.yaml），供管理 Tab 与 Workflow 编辑器使用。"""
    from common.task_type_store import list_task_types_for_api

    return {"task_types": list_task_types_for_api()}


@app.get("/api/task-types/outcome-kinds")
async def api_task_type_outcome_kinds():
    """产出形态目录（Gate 支持的三种 outcome_kind + 现实任务覆盖说明）。"""
    from common.task_type_suggest import list_outcome_kind_catalog

    return {"outcome_kinds": list_outcome_kind_catalog()}


@app.post("/api/task-types/suggest")
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


@app.post("/api/task-types")
async def api_create_task_type(body: dict):
    from common.task_type_store import get_task_type_raw, upsert_task_type, validate_task_type_id

    task_type = validate_task_type_id(body.get("task_type") or "")
    if get_task_type_raw(task_type):
        raise HTTPException(status_code=409, detail=f"task_type「{task_type}」已存在")
    try:
        result = upsert_task_type(task_type, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, **result}


@app.put("/api/task-types/{task_type}")
async def api_update_task_type(task_type: str, body: dict):
    from common.task_type_store import get_task_type_raw, upsert_task_type

    if not get_task_type_raw(task_type):
        raise HTTPException(status_code=404, detail=f"task_type「{task_type}」不存在")
    try:
        result = upsert_task_type(task_type, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, **result}


@app.delete("/api/task-types/{task_type}")
async def api_delete_task_type(task_type: str):
    from common.task_type_store import delete_task_type

    try:
        delete_task_type(task_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@app.get("/api/workflows")
async def api_list_workflows():
    """列出 PGD workflow profile（阶段闸门项目模板）。"""
    from common.workflow_bootstrap import list_workflow_summaries
    return {"workflows": list_workflow_summaries()}


@app.post("/api/workflows/suggest")
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


@app.get("/api/workflows/{workflow_id}")
async def api_get_workflow(workflow_id: str):
    from common.workflow_loader import read_workflow_raw
    try:
        return {"workflow": read_workflow_raw(workflow_id)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))


@app.post("/api/workflows")
async def api_create_workflow(body: dict):
    from common.workflow_loader import list_workflows, write_workflow_raw
    data = body.get("workflow") if isinstance(body.get("workflow"), dict) else body
    if not isinstance(data, dict):
        raise APIError("INVALID_BODY", "需要 workflow 对象")
    wid = (data.get("id") or "").strip()
    if not wid:
        raise APIError("INVALID_WORKFLOW", "workflow.id 不能为空")
    if wid in list_workflows():
        raise APIError("WORKFLOW_EXISTS", f"workflow「{wid}」已存在", hint="换 id 或使用 PUT 更新")
    try:
        write_workflow_raw(data)
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))
    return {"success": True, "id": wid}


@app.put("/api/workflows/{workflow_id}")
async def api_update_workflow(workflow_id: str, body: dict):
    from common.workflow_loader import delete_workflow, write_workflow_raw
    data = body.get("workflow") if isinstance(body.get("workflow"), dict) else body
    if not isinstance(data, dict):
        raise APIError("INVALID_BODY", "需要 workflow 对象")
    new_id = (data.get("id") or workflow_id).strip()
    try:
        write_workflow_raw(data, workflow_id=workflow_id)
        if new_id != workflow_id:
            old_fp_deleted = workflow_id
            try:
                delete_workflow(old_fp_deleted)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到 workflow「{workflow_id}」")
    except ValueError as e:
        raise APIError("INVALID_WORKFLOW", str(e))
    return {"success": True, "id": new_id}


@app.delete("/api/workflows/{workflow_id}")
async def api_delete_workflow(workflow_id: str):
    from common.workflow_loader import delete_workflow
    try:
        delete_workflow(workflow_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True}


@app.post("/api/projects/run")
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
    process_defaults = skill_config.get_all().get("process_defaults") or {}
    if workflow:
        from common.workflow_loader import load_workflow
        try:
            load_workflow(workflow)
        except (FileNotFoundError, ValueError) as e:
            raise APIError("INVALID_WORKFLOW", str(e), hint="选择有效的 workflow 或留空")
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        slug = _slug(title or goal)
        project_id = f"ui_{slug}_{time.strftime('%Y%m%d_%H%M%S')}"
    if _is_kernel_running(project_id):
        raise HTTPException(status_code=409, detail="该项目正在运行")
    _persist_project_launch(
        project_id, title=title or project_id, goal=goal, mode=mode,
        budget=budget, workflow=workflow,
    )
    _set_kernel_run(project_id, running=True)
    threading.Thread(
        target=_run_kernel_bg,
        args=(project_id, goal, mode, budget, title, review, workflow, split, process_defaults),
        daemon=True,
    ).start()
    return {
        "project_id": project_id,
        "title": title or project_id,
        "started": True,
        "workflow": workflow,
    }


@app.get("/api/projects/run-status/{project_id}")
async def api_project_run_status(project_id: str):
    return _get_kernel_run(project_id)


@app.post("/api/projects/{project_id}/resume")
async def api_project_resume(project_id: str):
    """断点续跑：回收孤儿响应后继续 DAG，无需重发项目。"""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    if _is_kernel_running(project_id):
        raise HTTPException(status_code=409, detail="该项目正在运行")
    if p.get("status") not in ("in_progress", "paused"):
        return {"resumed": False, "project_id": project_id, "reason": "项目已终态"}
    _set_kernel_run(project_id, running=True)
    threading.Thread(target=_resume_kernel_bg, args=(project_id,), daemon=True).start()
    return {"resumed": True, "project_id": project_id}


@app.get("/api/projects/{project_id}/deliverable/{task_id}")
async def api_project_deliverable(project_id: str, task_id: str):
    """任务交付物包：主文档 + workspace/legacy 文件清单（代码类任务产物在 agent workspace）。"""
    if not re.fullmatch(r"[\w-]{1,64}", task_id):
        raise HTTPException(status_code=400, detail="task_id 非法")
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise HTTPException(status_code=400, detail="project_id 非法")
    from common.project_artifacts import get_task_deliverable_bundle
    from common.store import Store

    bundle = get_task_deliverable_bundle(Store(), project_id, task_id)
    primary = bundle.get("primary") or {}
    # 兼容旧前端：保留 exists/content 顶栏字段
    bundle["exists"] = bool(primary.get("exists"))
    bundle["content"] = primary.get("content") or ""
    return bundle


@app.get("/api/projects/{project_id}/deliverable/{task_id}/file")
async def api_project_deliverable_file(project_id: str, task_id: str, path: str = Query("")):
    """读取任务交付物包中的单个文件（workspace 或 legacy project 目录）。"""
    if not re.fullmatch(r"[\w-]{1,64}", task_id):
        raise APIError("INVALID_TASK_ID", "task_id 非法", status_code=400)
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise APIError("INVALID_PROJECT_ID", "project_id 非法", status_code=400)
    if not path or ".." in path:
        raise APIError("INVALID_PATH", "path 非法", status_code=400)
    from common.project_artifacts import read_task_artifact_file
    from common.store import Store

    return read_task_artifact_file(Store(), project_id, task_id, path)


@app.get("/api/obs/projects/{project_id}/deliverables")
async def api_project_deliverables(project_id: str):
    """项目级交付物聚合列表：合并所有任务的 deliverable 文件树。"""
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        raise APIError("INVALID_PROJECT_ID", "project_id 非法")
    from common.store import Store
    from common.project_artifacts import get_task_deliverable_bundle
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
            raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
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
        raise APIError("INVALID_PROJECT_ID", "project_id 非法")
    if _is_kernel_running(project_id):
        raise APIError("PROJECT_RUNNING", "项目运行中，请先取消再删除", status_code=409)
    from common.store import Store
    store = Store()
    try:
        if not store.get_project(project_id):
            raise APIError("PROJECT_NOT_FOUND", "项目不存在", status_code=404)
    finally:
        store.close()
    from common.project_admin import delete_project
    summary = delete_project(project_id)
    _clear_kernel_run(project_id)
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
    default_backend = system_config.get("system", "default_backend", default="opencode")
    result = generate_agent(
        agent_id, description,
        backend_id=body.get("backend") or default_backend,
        model=body.get("model", ""),
        chinese_name=body.get("chinese_name", ""),
        role=body.get("role", "worker"),
        task_types=body.get("task_types"),
        capabilities=body.get("capabilities"),
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
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://0.0.0.0:{port}  (局域网设备通过本机 IP 访问)")
    print(f"  Agents:  http://localhost:{port}/api/agents")
    print(f"  Backends: http://localhost:{port}/api/backends")
    print(f"  Groups:  http://localhost:{port}/api/groups")
    uvicorn.run("hub.api.server:app", host="0.0.0.0", port=port, log_level="info", reload=True)


if __name__ == "__main__":
    main()
