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
    from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("需要安装依赖: pip install fastapi uvicorn")
    sys.exit(1)

from base.agent_chat import (
    _load_agents_config,
    delete_agent,
    get_agent_backend_config,
    scan_agents,
    set_agent_backend_config,
)
from base.agent_factory import generate_agent, suggest_agent_id
from hub.paths import FRONTEND_V2_DIST, resolve_workspace, to_relative_path
from hub.services.project_launch import (
    resume_kernel_bg,
    run_kernel_bg,
    start_kernel_job,
)
from hub.api.deps import we_store as _we_store
from hub.api.errors import APIError
from store.system_config import system_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan 上下文：启动恢复 + 关闭清理。"""
    import logging

    if system_config.get("system", "debug", default=False):
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("uvicorn").setLevel(logging.DEBUG)
    try:
        from common.agent_model import ensure_agents_config_entries

        touched = ensure_agents_config_entries(persist=True)
        if touched:
            print(f"[myteam] agents_config 已补全条目：{', '.join(touched)}")
    except Exception as exc:
        print(f"[myteam] agents_config 补全跳过：{exc}")
    try:
        from common.adapter_skill_registry import sync_all_agent_skill_mounts

        mount = sync_all_agent_skill_mounts()
        n_cli = mount.get("cli", {}).get("count", 0)
        n_md = len(mount.get("agents_md_stripped") or [])
        if n_cli or n_md:
            print(f"[myteam] Skill 挂载已同步：CLI {n_cli} 个 workspace，已清理 AGENTS.md Skill 节 {n_md} 个 Agent")
    except Exception as exc:
        print(f"[myteam] Skill 挂载同步跳过：{exc}")
    try:
        from common.adapter_mcp_registry import sync_all_agent_mcp_mounts

        mcp_mount = sync_all_agent_mcp_mounts()
        n_mcp = mcp_mount.get("cli", {}).get("count", 0)
        n_mcp_md = len(mcp_mount.get("agents_md_stripped") or [])
        if n_mcp or n_mcp_md:
            print(f"[myteam] MCP 挂载已同步：CLI {n_mcp} 个 workspace，已清理 AGENTS.md MCP 节 {n_mcp_md} 个 Agent")
    except Exception as exc:
        print(f"[myteam] MCP 挂载同步跳过：{exc}")
    threading.Thread(target=_auto_resume_on_startup, daemon=True).start()
    yield


def _auto_resume_on_startup() -> None:
    try:
        n_stale = _reconcile_stale_kernel_runs()
        if n_stale:
            print(f"[myteam] 清除 {n_stale} 个 Hub 重启残留的 kernel 运行标记")
        from common.agent_port import reconcile_on_start
        from common.project_runtime import get_project_runtime
        from common.store import Store
        from common.workspace_gc import gc_workspace
        store = Store()
        try:
            reconcile_on_start(store)  # 先对账再 gc，避免误删可采纳孤儿 .response
            gc_workspace(store)
            pending = [
                p for p in store.list_projects()
                if p.get("status") in ("in_progress", "paused")
            ]
        finally:
            store.close()
        runtime = get_project_runtime()
        resumed: list[str] = []
        for proj in pending:
            pid = proj["project_id"]
            if runtime.is_running(pid) or _is_kernel_running(pid):
                continue
            try:
                _set_kernel_run(pid, running=True)
                start_kernel_job(pid, resume_kernel_bg, pid)
                resumed.append(pid)
            except RuntimeError:
                _clear_kernel_run(pid)
        if resumed:
            print(f"[myteam] 自动续跑 {len(resumed)} 个中断项目: {', '.join(resumed)}")
        # 扫描 orphan job
        try:
            from common.job_supervisor import JobSupervisor

            orphan_store = Store()
            try:
                jsv = JobSupervisor(orphan_store)
                orphans = jsv.resume_orphans()
            finally:
                orphan_store.close()
            if orphans:
                print(f"[myteam] 标记 {len(orphans)} 个 orphan job: {[o['project_id'] for o in orphans]}")
        except Exception:
            pass
    except Exception as e:
        print(f"[myteam] 自动续跑失败: {e}")


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

_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("MYTEAM_CORS_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from hub.api.observability_api import router as observability_router
from hub.api.skills_api import router as skills_router
from hub.api.mcp_api import router as mcp_router
from hub.api.preferences_api import router as preferences_router
from hub.api.rules_api import router as rules_router
from hub.api.routes import api_router

app.include_router(observability_router)
app.include_router(skills_router)
app.include_router(mcp_router)
app.include_router(rules_router)
app.include_router(preferences_router)
app.include_router(api_router)


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


_V2_UI_READY = FRONTEND_V2_DIST.is_dir() and (FRONTEND_V2_DIST / "index.html").is_file()


@app.get("/")
async def index():
    if _V2_UI_READY:
        return RedirectResponse(url="/v2/", status_code=302)
    raise HTTPException(
        status_code=503,
        detail="Web UI 未就绪：请执行 cd frontend-v2 && npm install && npm run build",
    )


@app.get("/api/agents/{agent_id}/detail")
async def agent_detail(agent_id: str):
    from hub.paths import AGENT_WORKSPACE_FILES

    agent_cfg = _load_agents_config().get(agent_id, {})
    workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
    if not workspace.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 工作目录不存在")

    backend_cfg = get_agent_backend_config(agent_id)
    files = {}
    for fname in AGENT_WORKSPACE_FILES:
        fp = workspace / fname
        if fp.exists():
            files[fname] = fp.read_text(encoding="utf-8")
        else:
            files[fname] = ""

    task_types = agent_cfg.get("task_types") or []
    if not isinstance(task_types, list):
        task_types = [task_types] if task_types else []
    task_types = [str(t).strip() for t in task_types if str(t).strip()]

    from common.agent_registry import get_agent_info, get_agent_task_types
    from common.agent_skills import get_agent_skill_ids, skill_file_path
    from common.skill_groups import get_skill_group, group_member_ids, is_skill_group
    from common.agent_mcp import get_agent_mcp_ids
    from common.mcp_catalog import get_mcp_server
    from common.registry import get_spec
    from common.skill_catalog import get_skill_library_entry

    from common.shared_rules import list_shared_rule_files, read_all_shared_rules

    reg_info = get_agent_info(agent_id)
    if not task_types:
        task_types = get_agent_task_types(agent_id)

    task_type_labels: dict[str, str] = {}
    for tt in task_types:
        spec = get_spec(tt)
        task_type_labels[tt] = (spec.display_name if spec and spec.display_name else tt)

    skill_ids = get_agent_skill_ids(agent_id)
    skills = []
    for sid in skill_ids:
        if is_skill_group(sid):
            g = get_skill_group(sid) or {}
            skills.append(
                {
                    "skill_id": sid,
                    "name": g.get("name_zh") or g.get("name") or sid,
                    "available": True,
                    "is_group": True,
                    "member_ids": group_member_ids(sid),
                    "path": g.get("vendor_skills_root"),
                }
            )
            continue
        sp = skill_file_path(sid)
        entry = get_skill_library_entry(sid) or {}
        skills.append(
            {
                "skill_id": sid,
                "name": entry.get("name") or sid,
                "available": sp is not None,
                "path": to_relative_path(sp) if sp else None,
            }
        )

    deliverable_skills = []
    from common.skill_extract import SKILLS_DIR

    for tt in task_types:
        sp = SKILLS_DIR / tt / "SKILL.md"
        deliverable_skills.append(
            {
                "task_type": tt,
                "available": sp.is_file(),
                "path": to_relative_path(sp) if sp.is_file() else None,
            }
        )

    mcp_ids = get_agent_mcp_ids(agent_id)
    mcp_servers = []
    for mid in mcp_ids:
        entry = get_mcp_server(mid) or {}
        mcp_servers.append(
            {
                "server_id": mid,
                "name": entry.get("name") or mid,
                "enabled": bool(entry.get("enabled", True)),
                "type": entry.get("type") or "local",
            }
        )

    return {
        "agent_id": agent_id,
        "workspace": to_relative_path(workspace),
        "backend": backend_cfg.backend_id,
        "model": backend_cfg.model,
        "task_types": task_types,
        "task_type_labels": task_type_labels,
        "skills": skills,
        "deliverable_skills": deliverable_skills,
        "registry_skills": list(reg_info.get("skills") or []),
        "mcp_servers": mcp_servers,
        "registry_mcp_servers": list(reg_info.get("mcp_servers") or []),
        "files": files,
        "shared_rules": read_all_shared_rules(),
        "shared_rule_files": list_shared_rule_files(),
    }


@app.put("/api/agents/{agent_id}/files/{filename}")
async def update_agent_workspace_file(agent_id: str, filename: str, body: dict):
    from hub.paths import AGENT_WORKSPACE_FILES

    if filename not in AGENT_WORKSPACE_FILES:
        raise HTTPException(status_code=400, detail=f"不允许编辑的文件：{filename}")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    content = body.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="content 不能为空")
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail="content 须为字符串")

    agent_cfg = _load_agents_config().get(agent_id, {})
    workspace = resolve_workspace(agent_id, agent_cfg.get("workspace"))
    if not workspace.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 工作目录不存在")

    fp = workspace / filename
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")

    from common.hub_operation_meta import touch

    touch("agent", agent_id)
    return {"success": True, "agent_id": agent_id, "filename": filename}


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    ok, msg = delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    from common.hub_operation_meta import remove
    remove("agent", agent_id)
    return {"success": True, "message": msg}


@app.put("/api/agents/{agent_id}/manage")
async def manage_agent_config(agent_id: str, body: dict):
    from hub.services.agent_registry import update_agent_task_types, update_agent_skills, update_agent_mcp_servers

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
    if "skills" in body:
        sks = body.get("skills") or []
        if not isinstance(sks, list):
            raise HTTPException(status_code=400, detail="skills 须为数组")
        result = update_agent_skills(agent_id, [str(s).strip() for s in sks if str(s).strip()])
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "更新 skills 失败"))
    if "mcp_servers" in body:
        mcps = body.get("mcp_servers") or []
        if not isinstance(mcps, list):
            raise HTTPException(status_code=400, detail="mcp_servers 须为数组")
        result = update_agent_mcp_servers(agent_id, [str(m).strip() for m in mcps if str(m).strip()])
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "更新 MCP 失败"))
    from common.hub_operation_meta import touch
    touch("agent", agent_id)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


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


# ── 发起项目：UI → 编排内核（后台线程跑 run_kernel）──────────────
from hub.services.kernel_run import (  # noqa: E402
    _clear_kernel_run,
    _get_kernel_run,
    _is_kernel_running,
    _reconcile_stale_kernel_runs,
    _set_kernel_run,
)


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
    try:
        start_kernel_job(
            project_id, run_kernel_bg,
            project_id, demo_goal, "one_shot", 100000, "Demo 项目", False,
        )
    except RuntimeError:
        _clear_kernel_run(project_id)
        raise APIError("PROJECT_RUNNING", "Demo 项目已在运行")
    return {"project_id": project_id, "started": True}


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
    from common.hub_operation_meta import touch
    touch("task_type", task_type)
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
    from common.hub_operation_meta import touch
    touch("task_type", task_type)
    return {"success": True, **result}


@app.delete("/api/task-types/{task_type}")
async def api_delete_task_type(task_type: str):
    from common.task_type_store import delete_task_type

    try:
        delete_task_type(task_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from common.hub_operation_meta import remove
    remove("task_type", task_type)
    return {"success": True}


@app.get("/api/delivery-templates")
async def api_list_delivery_templates():
    """列出交付模板（含 task_types 绑定；按 Hub 操作时间排序）。"""
    from common.delivery_template_store import list_templates_for_api

    return {"templates": list_templates_for_api()}


@app.get("/api/delivery-templates/{template_id}")
async def api_get_delivery_template(template_id: str):
    from common.delivery_template_store import format_template_api, read_template_raw
    from common.delivery_templates import load_delivery_template

    import yaml

    try:
        tpl = load_delivery_template(template_id)
        raw = read_template_raw(template_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "template": format_template_api(tpl, raw),
        "yaml": yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False),
    }


@app.post("/api/delivery-templates")
async def api_create_delivery_template(body: dict):
    from common.delivery_template_store import save_template, validate_template_id
    from common.delivery_templates import DeliveryTemplateError, load_delivery_template
    from common.hub_operation_meta import touch

    import yaml

    tid = str(body.get("id") or body.get("template_id") or "").strip()
    if not tid and body.get("yaml"):
        parsed = yaml.safe_load(body.get("yaml") or "")
        if isinstance(parsed, dict):
            tid = str(parsed.get("id") or "").strip()
    tid = validate_template_id(tid)
    try:
        load_delivery_template(tid)
    except DeliveryTemplateError:
        pass
    else:
        raise HTTPException(status_code=409, detail=f"模板「{tid}」已存在")
    try:
        item = save_template(tid, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    touch("delivery_template", tid)
    return {"success": True, "template": item}


@app.put("/api/delivery-templates/{template_id}")
async def api_update_delivery_template(template_id: str, body: dict):
    from common.delivery_template_store import read_template_raw, save_template
    from common.hub_operation_meta import touch

    try:
        read_template_raw(template_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到模板「{template_id}」")
    new_id = str(body.get("id") or template_id).strip()
    try:
        item = save_template(new_id, body, update=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    touch("delivery_template", new_id)
    if new_id != template_id:
        from common.hub_operation_meta import remove
        remove("delivery_template", template_id)
    return {"success": True, "template": item}


@app.delete("/api/delivery-templates/{template_id}")
async def api_delete_delivery_template(template_id: str):
    from common.delivery_template_store import delete_template
    from common.hub_operation_meta import remove

    try:
        delete_template(template_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    remove("delivery_template", template_id)
    return {"success": True}


@app.get("/api/projects/run-status/{project_id}")
async def api_project_run_status(project_id: str):
    return _get_kernel_run(project_id)


@app.post("/api/projects/{project_id}/resume")
async def api_project_resume(project_id: str):
    """断点续跑：回收孤儿响应后继续 DAG，无需重发项目。"""
    from common.store import Store

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
    """取消项目：Store 置 cancelled + cancel_event 终止当前 CLI 子进程 + 停止后续派发。"""
    from common.project_runtime import get_project_runtime

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
    from common.hub_operation_meta import touch
    touch("agent", agent_id)
    return {"success": True, "agent": result}


@app.get("/api/agents/suggest-id")
async def api_suggest_id(description: str = Query("")):
    return {"suggested_id": suggest_agent_id(description)}


# SPA fallback for frontend-v2 — StaticFiles(html=True) does not serve index.html on deep links.
if _V2_UI_READY:
    _V2_INDEX = FRONTEND_V2_DIST / "index.html"

    @app.get("/v2", include_in_schema=False)
    @app.get("/v2/", include_in_schema=False)
    async def v2_index():
        return FileResponse(str(_V2_INDEX))

    @app.get("/v2/{rest_path:path}", include_in_schema=False)
    async def v2_spa(rest_path: str):
        candidate = FRONTEND_V2_DIST / rest_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_V2_INDEX))


def main():
    import logging

    port = int(os.environ.get("LOCAL_AGENT_PORT", "8765"))
    log_level = os.environ.get("MYTEAM_LOG_LEVEL", "info").lower()
    reload = os.environ.get("MYTEAM_RELOAD", "").lower() in ("1", "true", "yes")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    print("  Local Agent Chat v2")
    print(f"  UI:      http://localhost:{port}/v2/")
    print(f"  Local:   http://localhost:{port}/  → /v2/")
    print(f"  Network: http://0.0.0.0:{port}  (局域网设备通过本机 IP 访问)")
    print(f"  Agents:  http://localhost:{port}/api/agents")
    print(f"  Backends: http://localhost:{port}/api/backends")
    print(f"  Groups:  http://localhost:{port}/api/groups")
    if reload:
        print("  Reload:  enabled (MYTEAM_RELOAD=1)")
    uvicorn.run(
        "hub.api.server:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=reload,
    )


if __name__ == "__main__":
    main()
