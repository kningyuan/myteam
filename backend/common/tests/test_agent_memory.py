#!/usr/bin/env python3
"""Agent 外挂记忆 — session 隔离与清空群消息行为。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent_memory import (  # noqa: E402
    NativeAgentMemory,
    clear_group_agent_memory,
    get_agent_memory_provider,
    memory_scope_dm,
    memory_scope_group,
    memory_scope_roundtable,
)
from store.sessions import SessionStore  # noqa: E402


def test_native_session_key_isolates_group_from_dm():
    provider = NativeAgentMemory()
    dm = provider.session_key(memory_scope_dm("cto"))
    grp = provider.session_key(memory_scope_group("g1", "cto"))
    rt = provider.session_key(memory_scope_roundtable("g1", "cto"))
    assert dm == "workspace-cto"
    assert grp == "group:g1:cto"
    assert rt == "group:g1:cto"
    assert dm != grp


def test_get_agent_memory_provider_native():
    p = get_agent_memory_provider("native")
    assert p.name == "native"


def test_clear_group_does_not_touch_dm_session(tmp_path, monkeypatch):
    store = SessionStore(tmp_path / "sessions.json")
    monkeypatch.setattr("store.sessions.session_store", store)
    dm_key = "workspace-agent_a"
    grp_key = "group:g_test:agent_a"
    store.set("opencode", "agent_a", dm_key, "sess-dm")
    store.set("opencode", "agent_a", grp_key, "sess-grp")

    clear_group_agent_memory("g_test", ["agent_a", "user"])

    assert store.get("opencode", "agent_a", dm_key) == "sess-dm"
    assert store.get("opencode", "agent_a", grp_key) is None


def test_remove_for_agent_workspace(tmp_path):
    store = SessionStore(tmp_path / "sessions.json")
    store.set("opencode", "a1", "group:g1:a1", "s1")
    store.set("claude", "a1", "group:g1:a1", "s2")
    n = store.remove_for_agent_workspace("a1", "group:g1:a1")
    assert n == 2
    assert store.get("opencode", "a1", "group:g1:a1") is None
