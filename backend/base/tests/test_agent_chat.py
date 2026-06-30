"""Agent 后端配置管理测试。

覆盖：get/set_agent_backend_config、_load/_save_agents_config、apply_model_to_all、
scan_agents（扫描 workspace 目录）、delete_agent_config。

用 tmp_path 隔离 agents_config.json（经 conftest 的 isolated_paths patch 到 tmp）。
不测 stream_chat（它委托 hub.services，已在 conftest mock）。
"""
from __future__ import annotations

import json

import base.agent_chat as ac
from base.agent_chat import (
    BackendConfig,
    apply_model_to_all,
    delete_agent_config,
    get_agent_backend_config,
    scan_agents,
    set_agent_backend_config,
)


# ============ _load / _save agents_config ============

def test_load_agents_config_empty_when_missing():
    assert ac._load_agents_config() == {}


def test_save_then_load_agents_config_roundtrip():
    cfg = {"alice": {"backend": "opencode", "model": "m1", "extra": {}}}
    ac._save_agents_config(cfg)
    assert ac._load_agents_config() == cfg


def test_save_agents_config_creates_file_under_tmp():
    ac._save_agents_config({"x": {"backend": "opencode", "model": "m"}})
    # AGENTS_CONFIG_FILE 已被 conftest patch 到 tmp_path 下
    assert ac.AGENTS_CONFIG_FILE.exists()
    data = json.loads(ac.AGENTS_CONFIG_FILE.read_text(encoding="utf-8"))
    assert "x" in data


def test_load_agents_config_swallows_bad_json(monkeypatch):
    # 写入损坏 JSON 时回退到空 dict（不抛异常）
    ac.AGENTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ac.AGENTS_CONFIG_FILE.write_text("{not json", encoding="utf-8")
    assert ac._load_agents_config() == {}


# ============ get / set_agent_backend_config ============

def test_set_then_get_agent_backend_config():
    set_agent_backend_config("alice", "opencode", "gpt-4", extra={"k": "v"}, name="爱丽丝")
    cfg = get_agent_backend_config("alice")
    assert isinstance(cfg, BackendConfig)
    assert cfg.backend_id == "opencode"
    assert cfg.model == "gpt-4"
    assert cfg.extra == {"k": "v"}
    assert cfg.model_override == "gpt-4"          # 显式 model
    assert cfg.uses_settings_default is False      # 有显式 model


def test_get_agent_backend_config_derives_default_when_absent():
    # 未配置的 agent 走 _derive_backend_config（system_config 已被 conftest stub）
    cfg = get_agent_backend_config("nobody")
    assert cfg.backend_id == "opencode"
    assert cfg.model == "stub-model"
    assert cfg.uses_settings_default is True


def test_set_agent_backend_config_persists_name_and_workspace():
    set_agent_backend_config("alice", "opencode", "gpt-4", name="爱丽丝", workspace="some/rel")
    raw = ac._load_agents_config()
    assert raw["alice"]["name"] == "爱丽丝"
    assert "workspace" in raw["alice"]


def test_set_agent_backend_config_extra_defaults_empty():
    set_agent_backend_config("bob", "claude", "claude-3")
    raw = ac._load_agents_config()
    assert raw["bob"]["extra"] == {}


# ============ delete_agent_config ============

def test_delete_agent_config_removes_entry():
    set_agent_backend_config("alice", "opencode", "gpt-4")
    set_agent_backend_config("bob", "claude", "claude-3")
    delete_agent_config("alice")
    cfg = ac._load_agents_config()
    assert "alice" not in cfg
    assert "bob" in cfg


def test_delete_agent_config_noop_when_absent():
    # 不存在时不报错、不影响其它条目
    set_agent_backend_config("bob", "claude", "claude-3")
    delete_agent_config("ghost")
    assert ac._load_agents_config() == {"bob": {"backend": "claude", "model": "claude-3", "extra": {}}}


# ============ scan_agents ============

def test_scan_agents_lists_workspaces(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n角色: 测试\n")
    make_workspace("bob", identity="名字: 鲍勃\n角色: 架构\n")
    agents = scan_agents()
    ids = [a["id"] for a in agents]
    assert ids == ["alice", "bob"]           # 按 workspace 目录名排序
    alice = next(a for a in agents if a["id"] == "alice")
    assert alice["name"] == "爱丽丝"
    assert alice["backend"] == "opencode"     # 未配置 → stub 默认后端
    assert alice["model"] == "stub-model"
    assert "workspace" in alice
    assert alice["uses_settings_default"] is True


def test_scan_agents_uses_config_name_override(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    set_agent_backend_config("alice", "opencode", "gpt-4", name="自定义名")
    agents = scan_agents()
    alice = next(a for a in agents if a["id"] == "alice")
    # agents_config 的 name 优先于 IDENTITY 提取名
    assert alice["name"] == "自定义名"
    assert alice["backend"] == "opencode"
    assert alice["model"] == "gpt-4"
    assert alice["uses_settings_default"] is False


def test_scan_agents_empty_when_no_workspaces():
    assert scan_agents() == []


# ============ apply_model_to_all ============

def test_apply_model_to_all_writes_and_migrates(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    make_workspace("bob", identity="名字: 鲍勃\n")
    # bob 已显式配置 claude → 切到 opencode 应记为 migrated
    set_agent_backend_config("bob", "claude", "old-claude", name="鲍勃")
    result = apply_model_to_all("opencode", "new-model")

    assert set(result["applied"]) == {"alice", "bob"}
    assert result["skipped"] == []
    assert result["migrated"] == ["bob"]

    cfg = ac._load_agents_config()
    assert cfg["alice"]["backend"] == "opencode"
    assert cfg["alice"]["model"] == "new-model"
    assert cfg["bob"]["backend"] == "opencode"
    assert cfg["bob"]["model"] == "new-model"
    assert cfg["bob"]["name"] == "鲍勃"           # 保留原字段


def test_apply_model_to_all_preserves_extra(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    set_agent_backend_config("alice", "opencode", "old", extra={"k": "v"})
    apply_model_to_all("opencode", "new-model")
    cfg = ac._load_agents_config()
    assert cfg["alice"]["extra"] == {"k": "v"}
    assert cfg["alice"]["model"] == "new-model"


def test_apply_model_to_all_returns_backend_and_model(make_workspace):
    make_workspace("alice", identity="名字: 爱丽丝\n")
    result = apply_model_to_all("claude", "claude-sonnet")
    assert result["backend"] == "claude"
    assert result["model"] == "claude-sonnet"
    assert result["applied"] == ["alice"]
    assert result["migrated"] == ["alice"]       # stub 默认 opencode → claude 迁移
