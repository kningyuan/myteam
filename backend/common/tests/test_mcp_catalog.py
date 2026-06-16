#!/usr/bin/env python3
"""mcp_catalog — MCP 服务目录与 validate_mcp_ids。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common import mcp_catalog  # noqa: E402


def test_validate_mcp_ids_filters_disabled_and_unknown(tmp_path, monkeypatch):
    registry_file = tmp_path / "mcp_registry.json"
    registry_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "servers": {
                    "enabled-one": {"name": "A", "enabled": True, "type": "local", "command": ["echo"]},
                    "disabled-one": {"name": "B", "enabled": False, "type": "local", "command": ["echo"]},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mcp_catalog, "MCP_REGISTRY_FILE", registry_file)

    valid, unknown = mcp_catalog.validate_mcp_ids(
        ["enabled-one", "disabled-one", "missing", "enabled-one"]
    )
    assert valid == ["enabled-one"]
    assert set(unknown) == {"disabled-one", "missing"}


def test_create_and_list_mcp_server(tmp_path, monkeypatch):
    registry_file = tmp_path / "mcp_registry.json"
    registry_file.write_text('{"version":"1.0","servers":{}}\n', encoding="utf-8")
    monkeypatch.setattr(mcp_catalog, "MCP_REGISTRY_FILE", registry_file)

    res = mcp_catalog.create_mcp_server(
        "test-browser",
        {"name": "Browser", "type": "local", "command": ["npx", "-y", "browser-mcp"], "enabled": True},
    )
    assert res["success"] is True
    assert res["server"]["id"] == "test-browser"

    items = mcp_catalog.list_mountable_mcp_servers()
    assert any(i["id"] == "test-browser" for i in items)
