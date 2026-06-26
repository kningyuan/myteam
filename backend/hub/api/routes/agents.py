"""Agents 列表与活动态路由（P3.1 Wave 2）。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from base.agent_chat import scan_agents
from common.hub_operation_meta import attach_operated_at
from hub.api.deps import we_store
from hub.services.agent_registry import get_agents_registry

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _activity_unix_ts(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:
            return v / 1000.0
        return v
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


@router.get("")
async def list_agents():
    """扫描 workspace 并与注册表合并，UI 显示名优先用注册表中文 name。"""
    reg = get_agents_registry()
    scanned = {a["id"]: a for a in scan_agents()}
    activity: dict[str, dict] = {}
    store = we_store()
    for conv in store.list_all_conversations():
        cid = conv.get("conversation_id", "")
        if not str(cid).startswith("dm:"):
            continue
        aid = cid[3:] if str(cid).startswith("dm:") else str(cid)
        updated = _activity_unix_ts(conv.get("updated_at"))
        preview = ""
        recent = store.recent_messages(cid, 1)
        if recent:
            preview = (recent[0].get("text") or "").replace("\n", " ").strip()[:120]
        activity[aid] = {"last_message_at": updated, "last_message_preview": preview}

    agents = []
    for aid, info in reg["agents"].items():
        if not info.get("available"):
            continue
        scan = scanned.get(aid) or {}
        act = activity.get(aid, {})
        agents.append({
            "id": aid,
            "name": (info.get("name") or scan.get("name") or aid).strip(),
            "role": info.get("role") or "worker",
            "description": info.get("description") or "",
            "capabilities": info.get("capabilities") or [],
            "task_types": info.get("task_types") or [],
            "skills": info.get("skills") if isinstance(info.get("skills"), list) else [],
            "mcp_servers": info.get("mcp_servers") if isinstance(info.get("mcp_servers"), list) else [],
            "backend": scan.get("backend") or info.get("backend") or "",
            "model": scan.get("model") or info.get("model") or "",
            "model_override": scan.get("model_override") or "",
            "uses_settings_default": bool(scan.get("uses_settings_default")),
            "workspace": scan.get("workspace") or info.get("workspace") or "",
            "last_message_at": act.get("last_message_at", 0),
            "last_message_preview": act.get("last_message_preview", ""),
        })
    agents = attach_operated_at(agents, "agent", id_key="id")
    agents.sort(
        key=lambda a: max(
            _activity_unix_ts(a.get("operated_at")),
            float(a.get("last_message_at") or 0),
        ),
        reverse=True,
    )
    return {"agents": agents}


# ── Agent 详情、管理、通知、事件流（从 server.py 迁移） ──────────


@router.get("/{agent_id}/detail")
async def agent_detail(agent_id: str):
    from hub.paths import AGENT_WORKSPACE_FILES, resolve_workspace, to_relative_path

    from base.agent_chat import _load_agents_config, get_agent_backend_config

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


@router.put("/{agent_id}/files/{filename}")
async def update_agent_workspace_file(agent_id: str, filename: str, body: dict):
    from hub.paths import AGENT_WORKSPACE_FILES
    from base.agent_chat import _load_agents_config

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


@router.delete("/{agent_id}")
async def api_delete_agent(agent_id: str):
    from base.agent_chat import delete_agent

    ok, msg = delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    from common.hub_operation_meta import remove

    remove("agent", agent_id)
    return {"success": True, "message": msg}


@router.put("/{agent_id}/manage")
async def manage_agent_config(agent_id: str, body: dict):
    from hub.services.agent_registry import (
        update_agent_task_types,
        update_agent_skills,
        update_agent_mcp_servers,
    )
    from base.agent_chat import set_agent_backend_config

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


@router.post("/{agent_id}/notify")
async def api_agent_notify(agent_id: str, body: dict):
    import asyncio
    import threading

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


@router.get("/{agent_id}/events")
async def agent_events_stream(request: Request, agent_id: str):
    """订阅 Agent 后台任务执行流（对标 openclaw send_to_user 私信流）。"""
    import asyncio

    from hub.services.agent_broadcast import subscribe, unsubscribe
    from base.agent_chat import scan_agents

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


@router.get("/{agent_id}/chats")
async def api_agent_background_chats(agent_id: str):
    """获取 Agent 的后台执行私聊记录（持久化的 .chat 文件）。"""
    import json

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


@router.post("/create")
async def api_create_agent(body: dict):
    from base.agent_factory import generate_agent, suggest_agent_id
    from store.system_config import system_config

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


@router.get("/suggest-id")
async def api_suggest_id(description: str = Query("")):
    from base.agent_factory import suggest_agent_id

    return {"suggested_id": suggest_agent_id(description)}


# ── Agent Registry CRUD（直接编辑 agents_registry.json 元数据） ──────────


@router.post("/registry")
async def api_create_agent_registry(body: dict):
    """在注册表中创建新 agent 条目（不创建 workspace）。"""
    from hub.services.agent_registry import register_agent

    agent_id = str(body.get("agent_id") or "").strip()
    name = str(body.get("name") or agent_id).strip()
    role = str(body.get("role") or "worker").strip()
    description = str(body.get("description") or "").strip()
    capabilities = body.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [x.strip() for x in capabilities.replace("，", ",").split(",") if x.strip()]
    capabilities = [str(c).strip() for c in capabilities if c]
    task_types = body.get("task_types") or []
    if isinstance(task_types, str):
        task_types = [x.strip() for x in task_types.replace("，", ",").split(",") if x.strip()]
    task_types = [str(t).strip() for t in task_types if t]
    skills = body.get("skills") or []
    if isinstance(skills, str):
        skills = [x.strip() for x in skills.replace("，", ",").split(",") if x.strip()]
    skills = [str(s).strip() for s in skills if s]
    mcp_servers = body.get("mcp_servers") or []
    if isinstance(mcp_servers, str):
        mcp_servers = [x.strip() for x in mcp_servers.replace("，", ",").split(",") if x.strip()]
    mcp_servers = [str(m).strip() for m in mcp_servers if m]

    result = register_agent(
        agent_id, name=name, role=role, description=description,
        capabilities=capabilities, task_types=task_types,
        skills=skills, skills_explicit=bool(skills),
        mcp_servers=mcp_servers, mcp_explicit=bool(mcp_servers),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    from common.hub_operation_meta import touch
    touch("agent", agent_id)
    return {"success": True, "agent_id": agent_id}


@router.put("/registry/{agent_id}")
async def api_update_agent_registry(agent_id: str, body: dict):
    """更新注册表中 agent 的元数据（role / task_types / capabilities 等）。"""
    from hub.services.agent_registry import register_agent

    reg = get_agents_registry()["agents"].get(agent_id) or {}
    name = str(body.get("name") or reg.get("name", agent_id)).strip()
    role = str(body.get("role") or reg.get("role", "worker")).strip()
    description = str(body.get("description") or reg.get("description", "")).strip()
    capabilities = body.get("capabilities")
    if capabilities is None:
        capabilities = reg.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [x.strip() for x in capabilities.replace("，", ",").split(",") if x.strip()]
    capabilities = [str(c).strip() for c in capabilities if c]
    task_types = body.get("task_types")
    if task_types is None:
        task_types = reg.get("task_types") or []
    if isinstance(task_types, str):
        task_types = [x.strip() for x in task_types.replace("，", ",").split(",") if x.strip()]
    task_types = [str(t).strip() for t in task_types if t]
    skills = body.get("skills")
    if skills is not None:
        if isinstance(skills, str):
            skills = [x.strip() for x in skills.replace("，", ",").split(",") if x.strip()]
        skills = [str(s).strip() for s in skills if s]
    mcp_servers = body.get("mcp_servers")
    if mcp_servers is not None:
        if isinstance(mcp_servers, str):
            mcp_servers = [x.strip() for x in mcp_servers.replace("，", ",").split(",") if x.strip()]
        mcp_servers = [str(m).strip() for m in mcp_servers if m]

    kwargs: dict = dict(name=name, role=role, description=description, capabilities=capabilities, task_types=task_types)
    if body.get("skills") is not None:
        kwargs["skills"] = skills
        kwargs["skills_explicit"] = True
    if body.get("mcp_servers") is not None:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["mcp_explicit"] = True

    result = register_agent(agent_id, **kwargs)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失败"))
    from common.hub_operation_meta import touch
    touch("agent", agent_id)
    return {"success": True, "agent_id": agent_id}


# ── Agent Runtime 可观测（/api/obs/agents） ──────────────────

obs_router = APIRouter(tags=["obs-agents"])


@obs_router.get("/api/obs/agents")
async def api_list_agent_runtimes():
    store = we_store()
    runtimes = store.list_agent_runtimes()
    return {"agents": runtimes}


@obs_router.get("/api/obs/agents/{agent_id}")
async def api_get_agent_runtime(agent_id: str):
    store = we_store()
    rt = store.get_agent_runtime(agent_id)
    if not rt:
        # fallback: return offline status
        rt = {"agent_id": agent_id, "status": "offline", "workspace_ok": 1}
    return rt
