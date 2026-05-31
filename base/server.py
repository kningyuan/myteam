"""
Local Agent Chat Web Server v2
Multi-backend, Group chat, Agent Factory
"""

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("需要安装依赖: pip install fastapi uvicorn")
    sys.exit(1)

from agent_chat import (
    scan_agents, stream_chat,
    get_agent_backend_config, set_agent_backend_config,
    delete_agent, delete_agent_config,
    list_all_backends_with_models,
)
from group_manager import (
    create_group, delete_group, list_groups, get_group,
    add_member, remove_member, send_group_message,
)
from agent_factory import generate_agent, suggest_agent_id
from system_config import system_config

HERE = Path(__file__).parent  # base/
STATIC_DIR = HERE.parent / "static"  # myteam/static/

app = FastAPI(title="Local Agent Chat v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============ 首页 ============

@app.get("/")
async def index():
    idx = STATIC_DIR / "index.html"
    return FileResponse(str(idx)) if idx.exists() else {"error": "no index"}


# ============ Agent 管理 ============

@app.get("/api/agents")
async def list_agents():
    """Agent 列表（含 backend/model 信息）"""
    return {"agents": scan_agents()}


@app.get("/api/agents/{agent_id}/config")
async def agent_config(agent_id: str):
    """获取 Agent 后端配置"""
    cfg = get_agent_backend_config(agent_id)
    return {"agent_id": agent_id, "backend": cfg.backend_id, "model": cfg.model}


@app.post("/api/agents/{agent_id}/config")
async def update_agent_config(agent_id: str, body: dict):
    """设置 Agent 后端配置"""
    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    set_agent_backend_config(agent_id, backend, model)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


# ============ 后端管理 ============

@app.get("/api/backends")
async def list_backends():
    """列出所有 CLI 后端及可用模型"""
    return {"backends": list_all_backends_with_models()}


# ============ 系统配置 ============

@app.get("/api/config")
async def get_system_config():
    """获取系统配置"""
    return {"config": system_config.get_all()}


@app.put("/api/config")
async def update_system_config(body: dict):
    """更新系统配置"""
    config_data = body.get("config", {})
    if config_data:
        system_config.update_all(config_data)
    return {"success": True, "config": system_config.get_all()}


# ============ Agent 管理 ============

@app.get("/api/agents/{agent_id}/detail")
async def agent_detail(agent_id: str):
    """Agent 详情（含身份文件内容）"""
    from agent_chat import WORKSPACES_DIR, WORKSPACE_PREFIX
    workspace = WORKSPACES_DIR / f"{WORKSPACE_PREFIX}{agent_id}"
    if not workspace.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' 工作目录不存在")

    backend_cfg = get_agent_backend_config(agent_id)

    # 读取身份文件
    files = {}
    for fname in ["IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "HEARTBEAT.md"]:
        fp = workspace / fname
        if fp.exists():
            files[fname] = fp.read_text(encoding="utf-8")

    return {
        "agent_id": agent_id,
        "workspace": str(workspace),
        "backend": backend_cfg.backend_id,
        "model": backend_cfg.model,
        "files": files,
    }


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    """删除 Agent"""
    ok, msg = delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.put("/api/agents/{agent_id}/manage")
async def manage_agent_config(agent_id: str, body: dict):
    """管理 Agent 配置（后端、模型、名称、工作目录）"""
    backend = body.get("backend", "opencode")
    model = body.get("model", "")
    name = body.get("name")
    workspace = body.get("workspace")
    set_agent_backend_config(agent_id, backend, model, name=name, workspace=workspace)
    return {"success": True, "agent_id": agent_id, "backend": backend, "model": model}


# ============ 对话 ============

@app.get("/api/chat/{agent_id}")
async def chat(agent_id: str, message: str = Query(..., description="用户消息")):
    """SSE 流式对话"""
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def event_stream():
        try:
            for event_json in stream_chat(agent_id, message.strip()):
                yield f"data: {event_json}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache", "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============ 群组管理 ============

@app.get("/api/groups")
async def list_all_groups():
    """群组列表"""
    return {"groups": list_groups()}


@app.post("/api/groups")
async def api_create_group(body: dict):
    """创建群组"""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="群组名不能为空")
    desc = body.get("description", "")
    group = create_group(name, desc)
    return {"success": True, "group": group}


@app.delete("/api/groups/{group_id}")
async def api_delete_group(group_id: str):
    """删除群组"""
    ok = delete_group(group_id)
    if not ok:
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"success": True}


@app.get("/api/groups/{group_id}")
async def api_get_group(group_id: str):
    """群组详情（含最近消息）"""
    g = get_group(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="群组不存在")
    return {"group": g}


@app.post("/api/groups/{group_id}/members")
async def api_add_member(group_id: str, body: dict):
    """添加 Agent 到群组"""
    agent_id = body.get("agent_id", "")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id 不能为空")
    ok, msg = add_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.delete("/api/groups/{group_id}/members/{agent_id}")
async def api_remove_member(group_id: str, agent_id: str):
    """从群组移除 Agent"""
    ok, msg = remove_member(group_id, agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/groups/{group_id}/chat")
async def group_chat(
    group_id: str,
    sender: str = Query("user", description="发送者"),
    text: str = Query(..., description="消息内容"),
):
    """群组聊天 - 自动处理 @mention 路由，SSE 流式返回"""
    if not text.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def event_stream():
        try:
            for evt in send_group_message(group_id, sender, text):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache", "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============ Agent 创建 ============

@app.post("/api/agents/create")
async def api_create_agent(body: dict):
    """一键创建 Agent"""
    description = body.get("description", "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="Agent 描述不能为空")

    agent_id = body.get("agent_id", "").strip()
    if not agent_id:
        agent_id = suggest_agent_id(description)

    chinese_name = body.get("chinese_name", "")
    backend_id = body.get("backend", "opencode")
    model = body.get("model", "")

    result = generate_agent(agent_id, description, backend_id, model, chinese_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))

    return {"success": True, "agent": result}


@app.get("/api/agents/suggest-id")
async def api_suggest_id(description: str = Query("")):
    """建议 agent_id"""
    return {"suggested_id": suggest_agent_id(description)}


# ============ 启动 ============

def main():
    port = int(os.environ.get("LOCAL_AGENT_PORT", "8765"))
    print(f"  Local Agent Chat v2")
    print(f"  http://localhost:{port}")
    print(f"  Agents: http://localhost:{port}/api/agents")
    print(f"  Backends: http://localhost:{port}/api/backends")
    print(f"  Groups: http://localhost:{port}/api/groups")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()