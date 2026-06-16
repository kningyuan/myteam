"""MCP 服务目录 — business/config/mcp_registry.json 为 Hub 统一管理入口。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from common.paths import BUSINESS_CONFIG_DIR, MYTEAM_ROOT

MCP_REGISTRY_FILE = BUSINESS_CONFIG_DIR / "mcp_registry.json"
MCP_TEMPLATE_FILE = MYTEAM_ROOT / "business" / "templates" / "mcp_registry.template.json"

_SERVER_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _ensure_registry_file() -> None:
    if MCP_REGISTRY_FILE.is_file():
        return
    MCP_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if MCP_TEMPLATE_FILE.is_file():
        MCP_REGISTRY_FILE.write_text(MCP_TEMPLATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        MCP_REGISTRY_FILE.write_text(
            json.dumps({"version": "1.0", "servers": {}}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def load_mcp_registry() -> dict:
    _ensure_registry_file()
    try:
        with open(MCP_REGISTRY_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        raw = {"version": "1.0", "servers": {}}
    raw.setdefault("version", "1.0")
    raw.setdefault("servers", {})
    return raw


def save_mcp_registry(data: dict) -> None:
    MCP_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MCP_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _normalize_server_id(server_id: str) -> str:
    return (server_id or "").strip()


def validate_server_id(server_id: str) -> tuple[bool, str]:
    sid = _normalize_server_id(server_id)
    if not sid:
        return False, "server id 不能为空"
    if not _SERVER_ID_RE.match(sid):
        return False, "server id 须为小写字母开头，仅含 a-z、0-9、-、_"
    return True, ""


def _summarize_server(server_id: str, meta: dict) -> dict:
    stype = (meta.get("type") or "local").strip()
    return {
        "id": server_id,
        "name": (meta.get("name") or server_id).strip(),
        "description": (meta.get("description") or "").strip(),
        "enabled": bool(meta.get("enabled", True)),
        "type": stype if stype in ("local", "remote") else "local",
        "command": list(meta.get("command") or []) if stype != "remote" else [],
        "url": (meta.get("url") or "").strip(),
        "environment": dict(meta.get("environment") or meta.get("env") or {}),
        "headers": dict(meta.get("headers") or {}),
        "timeout": meta.get("timeout"),
        "is_mountable": bool(meta.get("enabled", True)),
    }


def list_all_mcp_servers(*, include_disabled: bool = True) -> list[dict]:
    raw = load_mcp_registry()
    items: list[dict] = []
    for sid, meta in sorted((raw.get("servers") or {}).items()):
        if not isinstance(meta, dict):
            continue
        row = _summarize_server(sid, meta)
        if not include_disabled and not row["enabled"]:
            continue
        items.append(row)
    return items


def list_mountable_mcp_servers() -> list[dict]:
    return [s for s in list_all_mcp_servers(include_disabled=False) if s.get("is_mountable")]


def get_mcp_server(server_id: str) -> Optional[dict]:
    sid = _normalize_server_id(server_id)
    if not sid:
        return None
    meta = (load_mcp_registry().get("servers") or {}).get(sid)
    if not isinstance(meta, dict):
        return None
    return _summarize_server(sid, meta)


def validate_mcp_ids(server_ids: list[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    catalog = load_mcp_registry().get("servers") or {}
    for raw in server_ids:
        sid = _normalize_server_id(raw)
        if not sid or sid in seen:
            continue
        seen.add(sid)
        meta = catalog.get(sid)
        if not isinstance(meta, dict):
            unknown.append(sid)
            continue
        if not meta.get("enabled", True):
            unknown.append(sid)
            continue
        valid.append(sid)
    return valid, unknown


def _validate_server_payload(payload: dict, *, server_id: str = "") -> tuple[dict, str]:
    stype = (payload.get("type") or "local").strip()
    if stype not in ("local", "remote"):
        return {}, "type 须为 local 或 remote"
    name = (payload.get("name") or server_id or "").strip()
    if not name:
        return {}, "name 不能为空"
    entry: dict[str, Any] = {
        "name": name,
        "description": (payload.get("description") or "").strip(),
        "enabled": bool(payload.get("enabled", True)),
        "type": stype,
    }
    if stype == "local":
        cmd = payload.get("command")
        if not isinstance(cmd, list) or not cmd:
            return {}, "local MCP 须提供 command 数组"
        entry["command"] = [str(c).strip() for c in cmd if str(c).strip()]
        if not entry["command"]:
            return {}, "command 不能为空"
        env = payload.get("environment") or payload.get("env") or {}
        if env:
            entry["environment"] = {str(k): str(v) for k, v in dict(env).items()}
    else:
        url = (payload.get("url") or "").strip()
        if not url:
            return {}, "remote MCP 须提供 url"
        entry["url"] = url
        headers = payload.get("headers") or {}
        if headers:
            entry["headers"] = {str(k): str(v) for k, v in dict(headers).items()}
    timeout = payload.get("timeout")
    if timeout is not None:
        try:
            entry["timeout"] = int(timeout)
        except (TypeError, ValueError):
            return {}, "timeout 须为整数"
    return entry, ""


def create_mcp_server(server_id: str, payload: dict) -> dict:
    ok, err = validate_server_id(server_id)
    if not ok:
        return {"success": False, "error": err}
    sid = _normalize_server_id(server_id)
    raw = load_mcp_registry()
    raw.setdefault("servers", {})
    if sid in raw["servers"]:
        return {"success": False, "error": f"MCP 已存在：{sid}"}
    entry, err = _validate_server_payload(payload, server_id=sid)
    if err:
        return {"success": False, "error": err}
    raw["servers"][sid] = entry
    save_mcp_registry(raw)
    return {"success": True, "server": get_mcp_server(sid)}


def update_mcp_server(server_id: str, payload: dict) -> dict:
    sid = _normalize_server_id(server_id)
    if not sid:
        return {"success": False, "error": "server id 不能为空"}
    raw = load_mcp_registry()
    raw.setdefault("servers", {})
    if sid not in raw["servers"]:
        return {"success": False, "error": f"MCP 不存在：{sid}"}
    merged = deepcopy(raw["servers"][sid])
    merged.update({k: v for k, v in payload.items() if v is not None})
    entry, err = _validate_server_payload(merged, server_id=sid)
    if err:
        return {"success": False, "error": err}
    raw["servers"][sid] = entry
    save_mcp_registry(raw)
    return {"success": True, "server": get_mcp_server(sid)}


def delete_mcp_server(server_id: str) -> dict:
    sid = _normalize_server_id(server_id)
    if not sid:
        return {"success": False, "error": "server id 不能为空"}
    raw = load_mcp_registry()
    raw.setdefault("servers", {})
    if sid not in raw["servers"]:
        return {"success": False, "error": f"MCP 不存在：{sid}"}
    del raw["servers"][sid]
    save_mcp_registry(raw)
    return {"success": True, "server_id": sid}
