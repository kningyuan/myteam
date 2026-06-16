"""Claude Code 工作区 MCP 同步 — 将 myteam 挂载的 MCP 写入 .mcp.json。"""

from __future__ import annotations

import json
from pathlib import Path

from common.mcp_catalog import load_mcp_registry

MCP_CONFIG_NAME = ".mcp.json"
MANIFEST_NAME = ".myteam-mcp.json"
CLAUDE_DIR_NAME = ".claude"


def _to_claude_mcp_entry(meta: dict) -> dict:
    """将 Hub registry 条目转为 Claude Code 项目级 .mcp.json 配置项。"""
    stype = (meta.get("type") or "local").strip()
    if stype == "remote":
        out: dict = {
            "type": "http",
            "url": meta.get("url") or "",
        }
        headers = meta.get("headers") or {}
        if headers:
            out["headers"] = dict(headers)
        return out

    cmd = list(meta.get("command") or [])
    if not cmd:
        return {}
    out = {"command": cmd[0]}
    if len(cmd) > 1:
        out["args"] = cmd[1:]
    env = meta.get("environment") or meta.get("env") or {}
    if env:
        out["env"] = dict(env)
    return out


def _manifest_path(workspace: Path) -> Path:
    return workspace / CLAUDE_DIR_NAME / MANIFEST_NAME


def _config_path(workspace: Path) -> Path:
    return workspace / MCP_CONFIG_NAME


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
        if sid == "workspace":
            missing.append(sid)
            continue
        meta = catalog.get(sid)
        if not isinstance(meta, dict) or not meta.get("enabled", True):
            missing.append(sid)
            continue
        entry = _to_claude_mcp_entry(meta)
        if not entry:
            missing.append(sid)
            continue
        mcp_block[sid] = entry
        linked.append(sid)

    cfg_path = _config_path(ws)
    data = {"mcpServers": mcp_block}
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
