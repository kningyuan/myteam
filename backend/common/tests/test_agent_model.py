#!/usr/bin/env python3
"""Agent model 解析与 agents_config 修复。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.agent_model import (  # noqa: E402
    agent_model_override,
    default_model_for_backend,
    ensure_agents_config_entries,
    resolve_agent_backend,
    resolve_agent_model,
    uses_settings_default,
    write_agents_config,
)


def test_resolve_uses_explicit_model(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr("common.agent_model.BUSINESS_CONFIG_DIR", cfg_dir)
    write_agents_config({"research": {"backend": "opencode", "model": "custom/m1"}})
    assert resolve_agent_model("research") == "custom/m1"
    assert not uses_settings_default("research")


def test_resolve_falls_back_to_settings_default(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr("common.agent_model.BUSINESS_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("common.agent_model.system_default_backend", lambda: "opencode")
    write_agents_config({"research": {"backend": "opencode", "model": ""}})
    monkeypatch.setattr(
        "store.system_config.system_config.get_default_model",
        lambda backend: "settings/default-model",
    )
    assert agent_model_override("research") == ""
    assert resolve_agent_model("research") == "settings/default-model"
    assert uses_settings_default("research")


def test_resolve_backend_from_settings_when_empty(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr("common.agent_model.BUSINESS_CONFIG_DIR", cfg_dir)
    write_agents_config({"research": {"model": "m1"}})
    monkeypatch.setattr("common.agent_model.system_default_backend", lambda: "claude")
    assert resolve_agent_backend("research") == "claude"


def test_ensure_entries_does_not_write_model(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    ws = tmp_path / "workspaces" / "workspace-research"
    ws.mkdir(parents=True)
    cfg_dir.mkdir()
    monkeypatch.setattr("common.agent_model.BUSINESS_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("common.agent_model.WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr("common.agent_model.WORKSPACE_PREFIX", "workspace-")
    monkeypatch.setattr("common.agent_model.system_default_backend", lambda: "opencode")
    write_agents_config({})
    touched = ensure_agents_config_entries(persist=True)
    assert "research" in touched
    saved = json.loads((cfg_dir / "agents_config.json").read_text(encoding="utf-8"))
    assert saved["research"]["backend"] == "opencode"
    assert saved["research"].get("model", "") == ""


def test_default_model_for_backend_uses_system_config(monkeypatch):
    monkeypatch.setattr(
        "store.system_config.system_config.get_default_model",
        lambda backend: "m-default",
    )
    assert default_model_for_backend("opencode") == "m-default"
