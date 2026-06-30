#!/usr/bin/env python3
"""Claude Code adapter 命令行构建。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from adapter.core.protocol import RunRequest  # noqa: E402
from adapter.claude.adapter import ClaudeCodeAdapter, _runtime_settings_json  # noqa: E402


@pytest.fixture()
def adapter(monkeypatch):
    monkeypatch.setattr(
        ClaudeCodeAdapter,
        "_cli_available",
        lambda self: (True, "/usr/local/bin/claude"),
    )
    monkeypatch.setattr(ClaudeCodeAdapter, "_cli_command", lambda self: ["/usr/local/bin/claude"])
    return ClaudeCodeAdapter()


def test_build_run_command_includes_rules_and_mcp(tmp_path, adapter, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir()
    rules = tmp_path / "merged-rules.md"
    rules.write_text("# rules\n", encoding="utf-8")
    (ws / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")

    import common.agent.agent_skills as skills_mod
    monkeypatch.setattr(skills_mod, "get_agent_skill_ids", lambda aid: ["alpha"] if aid == "research" else [])

    cmd = adapter._build_run_command(RunRequest(
        workspace=str(ws),
        message="hi",
        model="claude-sonnet-4-6",
        rules_file=str(rules),
        agent_id="research",
    ))

    assert "--append-system-prompt-file" in cmd
    assert str(rules) in cmd
    assert "--strict-mcp-config" in cmd
    assert str(ws / ".mcp.json") in cmd
    assert "--setting-sources" in cmd
    assert "project" in cmd
    assert "-p" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--settings" in cmd
    settings_idx = cmd.index("--settings") + 1
    assert "showThinkingSummaries" in cmd[settings_idx]


def test_runtime_settings_includes_user_env(monkeypatch, tmp_path):
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({
            "env": {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
                "ANTHROPIC_AUTH_TOKEN": "PROXY_MANAGED",
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr("adapter.claude.adapter.Path.home", lambda: home)
    payload = json.loads(_runtime_settings_json())
    assert payload["showThinkingSummaries"] is True
    assert payload["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:15721"


def test_build_run_command_without_optional_flags(tmp_path, adapter, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir()
    import common.agent.agent_skills as skills_mod
    monkeypatch.setattr(skills_mod, "get_agent_skill_ids", lambda aid: [])

    cmd = adapter._build_run_command(RunRequest(
        workspace=str(ws),
        message="hi",
        model="claude-sonnet-4-6",
    ))

    assert "--append-system-prompt-file" not in cmd
    assert "--strict-mcp-config" not in cmd
    assert "--setting-sources" not in cmd
