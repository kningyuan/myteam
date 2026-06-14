#!/usr/bin/env python3
"""群消息 Store 读回与合并测试。"""
from __future__ import annotations

import pytest

from common.group_message_store import (
    hub_group_read_store_enabled,
    merge_json_messages_with_store,
    persist_group_message_entry,
    resolve_group_messages_for_api,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    from common.store import Store

    s = Store(tmp_path / "state.db")
    monkeypatch.setattr("common.store.Store", lambda db_path=None: s)
    yield s
    s.close()


def test_persist_full_group_entry_roundtrip(store):
    entry = {
        "id": "m_test_round_1",
        "sender": "research",
        "text": "hello from store",
        "timestamp": 1000.0,
        "mentions": [],
        "in_reply_to": "m_user_1",
        "roundtable": True,
        "roundtable_phase": "thinking",
        "roundtable_round": 0,
        "turn_meta": {"phase": "thinking", "status": "ok"},
        "thinking": [{"type": "tool_use", "name": "Read", "status": "completed"}],
    }
    persist_group_message_entry("g_rt", entry, project_id="p1")
    msgs = store.recent_messages("group:g_rt", 10)
    assert msgs
    meta = msgs[-1]["meta"]
    assert meta["group_entry"]["id"] == "m_test_round_1"
    assert meta["thinking"][0]["name"] == "Read"


def test_merge_json_with_store_thinking_overlay():
    json_msgs = [
        {
            "id": "m_user_1",
            "sender": "user",
            "text": "question",
            "timestamp": 1,
        },
        {
            "id": "m_agent_1",
            "sender": "arch",
            "text": "answer",
            "timestamp": 2,
            "in_reply_to": "m_user_1",
            "roundtable": True,
        },
    ]
    store_msgs = [
        {
            "id": "m_agent_1",
            "sender": "arch",
            "text": "answer",
            "timestamp": 2,
            "in_reply_to": "m_user_1",
            "thinking": [{"type": "step_start"}],
        }
    ]
    merged = merge_json_messages_with_store(json_msgs, store_msgs)
    agent = merged[-1]
    assert agent["roundtable"] is True
    assert agent["thinking"][0]["type"] == "step_start"


def test_resolve_group_messages_flag_off(monkeypatch, store):
    monkeypatch.delenv("MYTEAM_HUB_GROUP_READ_STORE", raising=False)
    assert hub_group_read_store_enabled() is False
    json_msgs = [{"id": "m1", "sender": "user", "text": "x", "timestamp": 1}]
    out = resolve_group_messages_for_api("g1", json_msgs)
    assert out == json_msgs


def test_resolve_group_messages_flag_on_merge(monkeypatch, store):
    monkeypatch.setenv("MYTEAM_HUB_GROUP_READ_STORE", "1")
    entry = {
        "id": "m_agent_x",
        "sender": "main",
        "text": "reply",
        "timestamp": 5,
        "in_reply_to": "m_u",
        "thinking": [{"type": "text", "content": "trace"}],
    }
    persist_group_message_entry("g_merge", entry)
    json_msgs = [
        {"id": "m_u", "sender": "user", "text": "hi", "timestamp": 1},
        {
            "id": "m_agent_x",
            "sender": "main",
            "text": "reply",
            "timestamp": 5,
            "in_reply_to": "m_u",
        },
    ]
    out = resolve_group_messages_for_api("g_merge", json_msgs)
    assert out[-1]["thinking"][0]["content"] == "trace"


def test_resolve_prefers_store_when_full_entries(monkeypatch, store):
    monkeypatch.setenv("MYTEAM_HUB_GROUP_READ_STORE", "1")
    for i in range(3):
        persist_group_message_entry(
            "g_full",
            {
                "id": f"m_{i}",
                "sender": "user" if i == 0 else "main",
                "text": f"t{i}",
                "timestamp": float(i),
            },
        )
    json_msgs = [{"id": "legacy", "sender": "user", "text": "old", "timestamp": 0}]
    out = resolve_group_messages_for_api("g_full", json_msgs, limit=50)
    assert len(out) >= 3
    assert all(str(m.get("id", "")).startswith("m_") for m in out)
