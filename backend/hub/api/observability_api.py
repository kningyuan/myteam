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


def _ensure_common_importable() -> None:
    # backend/hub/api/observability_api.py → parents[3] = myteam root
    team = Path(__file__).resolve().parents[3] / "skill" / "team"
    p = str(team)
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
