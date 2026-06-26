"""FastAPI 入口 — 薄路由层，业务逻辑在 base/ 与 hub/services/。"""

import asyncio
import os
import sys
import threading
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
from hub.paths import FRONTEND_DIST, resolve_workspace, to_relative_path
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


# ── 发起项目：UI → 编排内核（后台线程跑 run_kernel）──────────────
from hub.services.kernel_run import (  # noqa: E402
    _clear_kernel_run,
    _get_kernel_run,
    _is_kernel_running,
    _reconcile_stale_kernel_runs,
    _set_kernel_run,
)


_V2_UI_READY = FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").is_file()


@app.get("/")
async def index():
    if _V2_UI_READY:
        return RedirectResponse(url="/v2/", status_code=302)
    raise HTTPException(
        status_code=503,
        detail="Web UI 未就绪：请执行 cd frontend && npm install && npm run build",
    )


# SPA fallback for frontend — StaticFiles(html=True) does not serve index.html on deep links.
if _V2_UI_READY:
    _V2_INDEX = FRONTEND_DIST / "index.html"

    @app.get("/v2", include_in_schema=False)
    @app.get("/v2/", include_in_schema=False)
    async def v2_index():
        return FileResponse(str(_V2_INDEX))

    @app.get("/v2/{rest_path:path}", include_in_schema=False)
    async def v2_spa(rest_path: str):
        candidate = FRONTEND_DIST / rest_path
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
