"""stream_fanout 单元测试 — 验证 adapter 隔离：只处理标准化 thinking 事件，不解析 opencode 原始字段。"""

import json
import pytest
from unittest.mock import patch

from hub.services.stream_fanout import sse_to_thinking, fanout_stream_event


def test_sse_to_thinking_returns_data_for_thinking_event():
    evt = {"event": "thinking", "data": {"type": "text", "content": "hello"}}
    assert sse_to_thinking(evt) == {"type": "text", "content": "hello"}


def test_sse_to_thinking_ignores_non_thinking_events():
    assert sse_to_thinking({"event": "raw", "data": {"opencode": {"type": "text"}}}) is None
    assert sse_to_thinking({"event": "done", "data": {}}) is None
    assert sse_to_thinking({"event": "error", "data": {}}) is None
    assert sse_to_thinking({}) is None


def test_sse_to_thinking_no_opencode_access():
    """raw 事件中包含 opencode 字段时，必须被忽略而不是被解析。"""
    evt = {"event": "raw", "data": {"opencode": {"type": "text", "part": {"text": "leak"}}}}
    assert sse_to_thinking(evt) is None


def test_fanout_thinking_event_broadcasts(monkeypatch):
    published = []
    monkeypatch.setattr("hub.services.stream_fanout.publish_agent", lambda aid, p: published.append(p))
    monkeypatch.setattr("hub.services.stream_fanout.publish_group", lambda gid, p: None)

    sse = json.dumps({"event": "thinking", "data": {"type": "text", "content": "hi"}})
    fanout_stream_event("agent1", sse)

    assert len(published) == 1
    assert published[0]["event"] == "agent_thinking"
    assert published[0]["data"]["agent_id"] == "agent1"
    assert published[0]["data"]["type"] == "text"


def test_fanout_raw_event_dropped(monkeypatch):
    """raw/opencode 事件不应广播任何内容。"""
    published = []
    monkeypatch.setattr("hub.services.stream_fanout.publish_agent", lambda aid, p: published.append(p))
    monkeypatch.setattr("hub.services.stream_fanout.publish_group", lambda gid, p: None)

    sse = json.dumps({"event": "raw", "data": {"opencode": {"type": "text", "part": {"text": "x"}}}})
    fanout_stream_event("agent1", sse)

    assert published == []
