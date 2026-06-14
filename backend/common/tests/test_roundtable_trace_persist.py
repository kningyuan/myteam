#!/usr/bin/env python3
"""圆桌 turn 轨迹持久化测试。"""
from __future__ import annotations

import json
from unittest.mock import patch

from common.roundtable_runtime import collect_roundtable_reply


def test_collect_roundtable_reply_accumulates_tool_trace():
    def fake_stream(*_args, **_kwargs):
        chunks = [
            {"event": "thinking", "data": {"type": "step_start", "name": "analyze"}},
            {"event": "thinking", "data": {"type": "tool_use", "name": "Read", "input": "{}"}},
            {"event": "thinking", "data": {"type": "text", "content": "## 观点\n- 支持撤回\n"}},
            {"event": "done", "data": {}},
        ]
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False)

    with patch("base.agent_chat.stream_chat", fake_stream):
        result = collect_roundtable_reply("research", "prompt", None)

    assert result.ok is True
    assert "撤回" in result.text
    assert result.parts
    assert any(p.get("type") == "tool_use" for p in result.parts)
    assert any(p.get("type") == "stream_text" for p in result.parts)


def test_collect_roundtable_reply_text_only_turn_skips_stream_trace():
    def fake_stream(*_args, **_kwargs):
        chunks = [
            {"event": "thinking", "data": {"type": "text", "content": "纯文本发言\n"}},
            {"event": "done", "data": {}},
        ]
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False)

    with patch("base.agent_chat.stream_chat", fake_stream):
        result = collect_roundtable_reply("arch", "prompt", None)

    assert result.ok is True
    assert result.parts == []


def test_collect_roundtable_reply_failure_keeps_partial_and_trace():
    def fake_stream(*_args, **_kwargs):
        chunks = [
            {"event": "thinking", "data": {"type": "tool_use", "name": "Grep", "input": "{}"}},
            {"event": "done", "data": {}},
        ]
        for chunk in chunks:
            yield json.dumps(chunk, ensure_ascii=False)

    with patch("base.agent_chat.stream_chat", fake_stream):
        result = collect_roundtable_reply("research", "prompt", None, max_attempts=1)

    assert result.ok is False
    assert result.error_code == "EMPTY_REPLY"
    assert result.parts
    assert result.partial_text == ""


def test_fanout_includes_reply_to():
    from hub.services.stream_fanout import fanout_stream_event

    published: list[tuple] = []

    with patch("hub.services.stream_fanout.publish_group", lambda gid, p: published.append((gid, p))):
        with patch("hub.services.stream_fanout.publish_agent", lambda *_a, **_k: None):
            fanout_stream_event(
                "arch",
                json.dumps({"event": "thinking", "data": {"type": "step_start"}}),
                group_id="g_test",
                reply_to="m_user_1",
            )

    assert published
    data = published[0][1]["data"]
    assert data["reply_to"] == "m_user_1"
    assert data["agent_id"] == "arch"
