"""Agents 列表与活动态路由（P3.1 Wave 2）。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

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
