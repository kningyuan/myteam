#!/usr/bin/env python3
"""Claude Code 工作区 MCP 同步。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapter.claude.mcp_sync import sync_workspace_mcp  # noqa: E402


@pytest.fixture()
def mcp_env(tmp_path, monkeypatch):
    registry = {
        "version": "1.0",
        "servers": {
            "playwright": {
                "name": "Playwright",
                "enabled": True,
                "type": "local",
                "command": ["npx", "-y", "@playwright/mcp@latest"],
            },
            "sentry": {
                "name": "Sentry",
                "enabled": True,
                "type": "remote",
                "url": "https://mcp.sentry.dev/mcp",
                "headers": {"Authorization": "Bearer ${SENTRY_TOKEN}"},
            },
            "disabled-srv": {
                "enabled": False,
                "type": "local",
                "command": ["echo"],
            },
        },
    }
    monkeypatch.setattr(
        "adapter.claude.mcp_sync.load_mcp_registry",
        lambda: registry,
    )
    ws = tmp_path / "workspace-main"
    ws.mkdir()
    return ws


def test_sync_writes_mcp_json(mcp_env):
    ws = mcp_env
    result = sync_workspace_mcp(ws, ["playwright", "sentry"])
    assert result["success"] is True
    assert result["linked"] == ["playwright", "sentry"]

    cfg = json.loads((ws / ".mcp.json").read_text(encoding="utf-8"))
    assert cfg["mcpServers"]["playwright"]["command"] == "npx"
    assert cfg["mcpServers"]["playwright"]["args"] == ["-y", "@playwright/mcp@latest"]
    assert cfg["mcpServers"]["sentry"]["type"] == "http"
    assert cfg["mcpServers"]["sentry"]["url"] == "https://mcp.sentry.dev/mcp"


def test_sync_reports_missing_and_disabled(mcp_env):
    ws = mcp_env
    result = sync_workspace_mcp(ws, ["playwright", "missing", "disabled-srv"])
    assert result["success"] is True
    assert result["linked"] == ["playwright"]
    assert "missing" in result["missing"]
    assert "disabled-srv" in result["missing"]


def test_adapter_sync_agent_mcp(mcp_env):
    ws = mcp_env
    from adapter.claude.adapter import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    assert adapter.capabilities.native_mcp_registry is True
    out = adapter.sync_agent_mcp("main", str(ws), ["playwright"])
    assert out["success"] is True
    assert (ws / ".mcp.json").is_file()
