"""只读可观测路由（D17）—— 把 skill/team 的 observability 查询暴露为 HTTP + run_event SSE。

数据全部来自 SQLite 真相库（D13，tasks/state.db）。本模块只读、非破坏性：
新内核写、Hub 读，复用既有 SSE 模式（keepalive + 断连感知）推 run_event。

common 包（skill/team）按需惰性导入，避免缺依赖时拖垮 Hub 启动。
"""

import asyncio
import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/obs", tags=["observability"])

_TERMINAL = {"done", "failed", "timed_out", "cancelled"}
_PROJECT_TERMINAL = {
    "completed", "failed", "partially_failed", "aborted",
    "cancelled", "paused", "timed_out",
}


def _ensure_common_importable() -> None:
    # backend/hub/api/observability_api.py → parents[2] = backend（含 common 内核包）
    backend = Path(__file__).resolve().parents[2]
    p = str(backend)
    if p not in sys.path:
        sys.path.insert(0, p)


def _obs():
    _ensure_common_importable()
    from common import observability  # noqa: WPS433
    return observability


def _store():
    _ensure_common_importable()
    from common.store import Store  # noqa: WPS433
    return Store()


@router.get("/projects")
async def list_projects():
    """从 SQLite 真相库列出项目（新内核写入），供 UI 项目列表使用。"""
    store = _store()
    obs = _obs()
    try:
        out = []
        for p in store.list_projects():
            pid = p["project_id"]
            ov = obs.project_overview(store, pid)
            out.append({
                "id": pid,
                "title": p.get("title") or pid,
                "status": p.get("status"),
                "mode": p.get("mode"),
                "progress": ov.get("progress", 0),
                "task_count": len(ov.get("tasks", [])),
                "updated_at": p.get("updated_at"),
            })
        return {"projects": out}
    finally:
        store.close()


@router.get("/summary")
async def summary():
    """全局总览（Dashboard）：项目卡片数据 + 全局总计（项目数/运行中/总 token）。"""
    store = _store()
    try:
        return _obs().projects_summary(store)
    finally:
        store.close()


@router.get("/task-types")
async def list_task_types():
    """只读：业务任务类型注册表（与 /api/task-types 同源）。"""
    _ensure_common_importable()
    from common.task_type_store import list_task_types_for_api  # noqa: WPS433

    return {"task_types": list_task_types_for_api()}


@router.get("/memory")
async def list_memory(project_id: str | None = None, text: str = "", limit: int = 50):
    """只读：知识库（KB）条目列表，正文截断为预览。"""
    store = _store()
    try:
        rows = store.memory_search(project_id=project_id, text=text)
        out = []
        for r in rows[: max(1, min(limit, 200))]:
            content = r.get("content") or ""
            out.append({
                "id": r.get("id"),
                "project_id": r.get("project_id"),
                "task_id": r.get("task_id"),
                "title": r.get("title"),
                "tags": r.get("tags") or [],
                "created_at": r.get("created_at"),
                "preview": content[:200],
            })
        return {"memory": out, "total": len(rows)}
    finally:
        store.close()


@router.get("/projects/{project_id}/overview")
async def project_overview(project_id: str):
    store = _store()
    try:
        return _obs().project_overview(store, project_id)
    finally:
        store.close()


@router.get("/projects/{project_id}/cost")
async def project_cost(project_id: str):
    store = _store()
    try:
        return _obs().cost(store, project_id)
    finally:
        store.close()


@router.get("/projects/{project_id}/events")
async def project_events(project_id: str):
    """项目执行过程事件流（交互骨架 + 门禁/评审/skill/消息/阻塞/预算里程碑）。"""
    store = _store()
    try:
        return {"events": _obs().project_events(store, project_id)}
    finally:
        store.close()


def _project_signature(project_id: str) -> tuple[str, str | None]:
    """计算项目变更签名（状态 + 进度 + 任务 + token + 执行事件），用于 SSE 去抖。"""
    store = _store()
    try:
        ov = _obs().project_overview(store, project_id)
        ev = _obs().project_events(store, project_id)
        status = ov.get("status")
        ev_fp = [
            (e.get("ts"), e.get("category"), e.get("kind"), e.get("interaction_id"),
             e.get("status"), e.get("attempt"))
            for e in ev
        ]
        # 运行中 interaction 的时间线尾部：text/step 等不进 project_events，但需触发 SSE 刷新钻取视图
        tl_fp = []
        for i in store.list_interactions(project_id):
            iid = i.get("interaction_id")
            if not iid or i.get("status") != "running":
                continue
            events = store.list_run_events(iid)
            if events:
                last = events[-1]
                tl_fp.append((iid, len(events), last["seq"], last["kind"]))
            else:
                tl_fp.append((iid, 0, 0, ""))
        tl_fp.sort()
        sig = json.dumps(
            {
                "s": status,
                "p": ov.get("progress"),
                "t": sorted((t.get("id"), t.get("status")) for t in ov.get("tasks", [])),
                "tok": ov.get("tokens"),
                "ev": ev_fp,
                "tl": tl_fp,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return sig, status
    finally:
        store.close()


@router.get("/projects/{project_id}/stream")
async def project_stream(request: Request, project_id: str):
    """项目级 SSE：服务端轮询真相库，仅在状态/任务/token 变化时推一帧 tick，
    前端据此刷新（替代固定 2.5s 客户端轮询）。终态后收尾关闭。"""
    async def event_stream():
        last_sig = None
        while True:
            if await request.is_disconnected():
                break
            try:
                sig, status = await asyncio.to_thread(_project_signature, project_id)
            except Exception:  # noqa: BLE001 - 真相库瞬时不可用时降级为 keepalive
                yield ": keepalive\n\n"
                await asyncio.sleep(2.0)
                continue
            if sig != last_sig:
                last_sig = sig
                yield "data: " + json.dumps({"status": status}, ensure_ascii=False) + "\n\n"
            else:
                yield ": keepalive\n\n"
            if status in _PROJECT_TERMINAL:
                yield "data: [DONE]\n\n"
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/projects/{project_id}/fleet")
async def project_fleet(project_id: str):
    store = _store()
    try:
        return {"fleet": _obs().fleet_status(store, project_id)}
    finally:
        store.close()


@router.get("/projects/{project_id}/tasks/{task_id}")
async def task_detail(project_id: str, task_id: str):
    store = _store()
    try:
        detail = _obs().task_detail(store, project_id, task_id)
        if detail["task"]["status"] is None and not detail["interactions"]:
            raise HTTPException(status_code=404, detail="任务不存在")
        return detail
    finally:
        store.close()


@router.get("/interactions/{interaction_id}/timeline")
async def interaction_timeline(interaction_id: str):
    store = _store()
    try:
        return {"interaction_id": interaction_id,
                "timeline": _obs().timeline(store, interaction_id)}
    finally:
        store.close()


@router.get("/interactions/{interaction_id}/events")
async def interaction_events_stream(request: Request, interaction_id: str):
    """订阅一次 interaction 的 run_event 实时流（SSE）。

    轮询真相库新事件（seq 增量），终态且无新事件后收尾。复用 Hub 既有 SSE 约定。
    """
    store = _store()

    async def event_stream():
        last_seq = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                events = await asyncio.to_thread(store.list_run_events, interaction_id)
                fresh = [e for e in events if e["seq"] > last_seq]
                for e in fresh:
                    last_seq = e["seq"]
                    yield "data: " + json.dumps(
                        {"seq": e["seq"], "kind": e["kind"],
                         "payload": e["payload"], "ts": e["ts"]},
                        ensure_ascii=False) + "\n\n"
                inter = await asyncio.to_thread(store.get_interaction, interaction_id)
                status = inter.get("status") if inter else None
                if status in _TERMINAL and not fresh:
                    yield "data: [DONE]\n\n"
                    break
                if not fresh:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1.0)
        finally:
            store.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
