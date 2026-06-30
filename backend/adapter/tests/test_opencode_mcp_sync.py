#!/usr/bin/env python3
"""OpenCode 工作区 MCP 同步。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapter.opencode.mcp_sync import sync_workspace_mcp  # noqa: E402


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
                "environment": {"PLAYWRIGHT_HEADLESS": "1"},
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
        "adapter.opencode.mcp_sync.load_mcp_registry",
        lambda: registry,
    )
    ws = tmp_path / "workspace-main"
    ws.mkdir()
    return ws


def test_sync_writes_opencode_json(mcp_env):
    ws = mcp_env
    result = sync_workspace_mcp(ws, ["playwright", "sentry"])
    assert result["success"] is True
    assert result["linked"] == ["playwright", "sentry"]

    cfg = json.loads((ws / "opencode.json").read_text(encoding="utf-8"))
    # local → type + command + environment（command 为完整列表，区别于 claude 的 command+args）
    pw = cfg["mcp"]["playwright"]
    assert pw["type"] == "local"
    assert pw["enabled"] is True
    assert pw["command"] == ["npx", "-y", "@playwright/mcp@latest"]
    assert pw["environment"] == {"PLAYWRIGHT_HEADLESS": "1"}
    # remote → type + url + headers（type 为 "remote"，区别于 claude 的 "http"）
    st = cfg["mcp"]["sentry"]
    assert st["type"] == "remote"
    assert st["url"] == "https://mcp.sentry.dev/mcp"
    assert st["headers"] == {"Authorization": "Bearer ${SENTRY_TOKEN}"}


def test_sync_reports_missing_and_disabled(mcp_env):
    ws = mcp_env
    result = sync_workspace_mcp(ws, ["playwright", "missing", "disabled-srv"])
    assert result["success"] is True
    assert result["linked"] == ["playwright"]
    assert "missing" in result["missing"]
    assert "disabled-srv" in result["missing"]
    # missing 的不应进入 opencode.json 的 mcp 块
    cfg = json.loads((ws / "opencode.json").read_text(encoding="utf-8"))
    assert set(cfg["mcp"].keys()) == {"playwright"}


def test_sync_preserves_existing_schema(mcp_env):
    ws = mcp_env
    (ws / "opencode.json").write_text(
        json.dumps({"$schema": "https://custom.example/schema.json", "other": 1}),
        encoding="utf-8",
    )
    result = sync_workspace_mcp(ws, ["playwright"])
    assert result["success"] is True
    cfg = json.loads((ws / "opencode.json").read_text(encoding="utf-8"))
    assert cfg["$schema"] == "https://custom.example/schema.json"  # 保留已有 $schema
    assert cfg["other"] == 1  # 保留已有字段，仅覆写 mcp 块
    assert "playwright" in cfg["mcp"]


def test_sync_writes_manifest(mcp_env):
    ws = mcp_env
    result = sync_workspace_mcp(ws, ["playwright", "missing"])
    assert result["success"] is True
    manifest = json.loads(
        (ws / ".opencode" / ".myteam-mcp.json").read_text(encoding="utf-8")
    )
    assert manifest["server_ids"] == ["playwright", "missing"]
    assert manifest["linked"] == ["playwright"]
    assert manifest["missing"] == ["missing"]


def test_adapter_sync_agent_mcp(mcp_env):
    ws = mcp_env
    from adapter.opencode.adapter import OpenCodeAdapter

    adapter = OpenCodeAdapter()
    assert adapter.capabilities.native_mcp_registry is True
    out = adapter.sync_agent_mcp("main", str(ws), ["playwright"])
    assert out["success"] is True
    assert (ws / "opencode.json").is_file()
