"""OpenCode 工作区 MCP 同步 — 将 myteam 挂载的 MCP 写入 opencode.json。"""

from __future__ import annotations

import json
from pathlib import Path

from common.mcp_catalog import load_mcp_registry

OPENCODE_CONFIG_NAME = "opencode.json"
MANIFEST_NAME = ".myteam-mcp.json"


def _to_opencode_mcp_entry(meta: dict) -> dict:
    """将 Hub registry 条目转为 OpenCode 工作区 MCP 配置项（仅 OpenCode 适配器使用）。"""
    stype = (meta.get("type") or "local").strip()
    out: dict = {
        "type": stype,
        "enabled": True,
    }
    if stype == "remote":
        out["url"] = meta.get("url") or ""
        headers = meta.get("headers") or {}
        if headers:
            out["headers"] = dict(headers)
    else:
        cmd = meta.get("command") or []
        out["command"] = list(cmd)
        env = meta.get("environment") or meta.get("env") or {}
        if env:
            out["environment"] = dict(env)
    timeout = meta.get("timeout")
    if timeout is not None:
        out["timeout"] = int(timeout)
    return out


def _manifest_path(workspace: Path) -> Path:
    return workspace / ".opencode" / MANIFEST_NAME


def _config_path(workspace: Path) -> Path:
    return workspace / OPENCODE_CONFIG_NAME


def sync_workspace_mcp(workspace: str | Path, server_ids: list[str]) -> dict:
    ws = Path(workspace).resolve()
    if not ws.is_dir():
        return {"success": False, "error": f"workspace 不存在: {ws}"}

    desired: list[str] = []
    seen: set[str] = set()
    for raw in server_ids:
        sid = (raw or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            desired.append(sid)

    catalog = load_mcp_registry().get("servers") or {}
    mcp_block: dict = {}
    linked: list[str] = []
    missing: list[str] = []

    for sid in desired:
        meta = catalog.get(sid)
        if not isinstance(meta, dict) or not meta.get("enabled", True):
            missing.append(sid)
            continue
        mcp_block[sid] = _to_opencode_mcp_entry(meta)
        linked.append(sid)

    cfg_path = _config_path(ws)
    data: dict = {}
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["$schema"] = data.get("$schema") or "https://opencode.ai/config.json"
    data["mcp"] = mcp_block
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest = {
        "version": 1,
        "server_ids": desired,
        "linked": linked,
        "missing": missing,
    }
    _manifest_path(ws).parent.mkdir(parents=True, exist_ok=True)
    _manifest_path(ws).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "success": True,
        "workspace": str(ws),
        "config_path": str(cfg_path),
        "linked": linked,
        "missing": missing,
    }
