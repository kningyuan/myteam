#!/usr/bin/env python3
"""有界 USER.md / MEMORY.md 同步到 agent workspace。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.paths import CONFIG_DIR, workspace_dir
from execution_harness.config import memory_char_limit, user_char_limit


def _clip(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _read_user_source(_owner_id: str) -> str:
    """团队偏好库 — 仅有界副本来源 config/USER.md。"""
    global_user = CONFIG_DIR / "USER.md"
    if global_user.is_file():
        return global_user.read_text(encoding="utf-8", errors="replace")
    return ""


def _read_memory_source(agent_id: str) -> str:
    ws = workspace_dir(agent_id)
    p = ws / "MEMORY.md"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def sync_bounded_identity(
    agent_id: str,
    *,
    owner_id: str = "",
    workspace: Optional[Path] = None,
) -> dict[str, str]:
    """刷新 workspace 内 USER.md / MEMORY.md（有界）。返回写入路径。"""
    ws = workspace or workspace_dir(agent_id)
    ws.mkdir(parents=True, exist_ok=True)
    owner = (owner_id or agent_id or "").strip()
    user_body = _clip(_read_user_source(owner), user_char_limit())
    mem_body = _clip(_read_memory_source(agent_id), memory_char_limit())
    written: dict[str, str] = {}
    if user_body:
        user_path = ws / "USER.md"
        user_path.write_text(user_body + "\n", encoding="utf-8")
        written["USER.md"] = str(user_path)
    if mem_body:
        mem_path = ws / "MEMORY.md"
        mem_path.write_text(mem_body + "\n", encoding="utf-8")
        written["MEMORY.md"] = str(mem_path)
    return written
