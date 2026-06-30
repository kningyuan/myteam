"""agent_broadcast 单元测试 — Agent 实时事件 pub/sub。

覆盖：subscribe / unsubscribe / publish、多订阅者、满队列(maxsize=300)自动剔除、
unsubscribe 后不收、空 agent_id 安全短路。验证 adapter 隔离链下游广播的纯逻辑。
"""

import json

import pytest

import hub.services.agent_broadcast as ab
from hub.services.agent_broadcast import publish, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def _clean_listeners():
    """每个测试前后清空模块级订阅表，保证用例隔离。"""
    with ab._lock:
        ab._listeners.clear()
    yield
    with ab._lock:
        ab._listeners.clear()


def test_subscribe_returns_queue_and_publish_delivers():
    q = subscribe("agent-1")
    publish("agent-1", {"event": "agent_thinking", "data": {"type": "text", "content": "hi"}})

    assert q.qsize() == 1
    payload = json.loads(q.get_nowait())
    assert payload["event"] == "agent_thinking"
    assert payload["data"]["type"] == "text"
    assert payload["data"]["content"] == "hi"


def test_publish_serializes_with_ensure_ascii_false():
    """中文内容应原样序列化（ensure_ascii=False），不被 \\uXXXX 转义。"""
    q = subscribe("agent-cn")
    publish("agent-cn", {"event": "thinking", "data": {"text": "你好世界"}})

    raw = q.get_nowait()
    assert "你好世界" in raw


def test_multiple_subscribers_all_receive():
    q1 = subscribe("agent-multi")
    q2 = subscribe("agent-multi")

    publish("agent-multi", {"event": "agent_thinking", "data": {"type": "text"}})

    assert q1.qsize() == 1
    assert q2.qsize() == 1
    assert json.loads(q1.get_nowait())["event"] == "agent_thinking"
    assert json.loads(q2.get_nowait())["event"] == "agent_thinking"


def test_unsubscribe_stops_delivery():
    """退订后 publish 不再向该队列投递。"""
    q = subscribe("agent-stop")
    unsubscribe("agent-stop", q)

    publish("agent-stop", {"event": "agent_thinking", "data": {}})

    assert q.qsize() == 0


def test_unsubscribe_only_removes_target_queue():
    """退订一个订阅者不影响同 agent 的其他订阅者。"""
    q1 = subscribe("agent-pair")
    q2 = subscribe("agent-pair")
    unsubscribe("agent-pair", q1)

    publish("agent-pair", {"event": "agent_thinking", "data": {}})

    assert q1.qsize() == 0
    assert q2.qsize() == 1


def test_unsubscribe_unknown_queue_is_safe():
    """退订一个未注册的队列不抛错。"""
    q = subscribe("agent-safe")
    other = subscribe("agent-other")
    # 退订不属于本 agent 的队列，不应抛异常
    unsubscribe("agent-safe", other)
    # 原订阅仍在
    publish("agent-safe", {"event": "agent_thinking", "data": {}})
    assert q.qsize() == 1


def test_publish_empty_agent_id_is_noop():
    """空 agent_id 直接短路返回，不创建订阅、不抛错。"""
    publish("", {"event": "agent_thinking", "data": {}})
    with ab._lock:
        assert "" not in ab._listeners


def test_publish_to_agent_without_listeners_is_safe():
    """向无订阅者的 agent 发布不抛错。"""
    publish("agent-nobody", {"event": "agent_thinking", "data": {}})
    with ab._lock:
        assert ab._listeners.get("agent-nobody", []) == []


def test_full_queue_evicts_subscriber():
    """队列满（maxsize=300）后 publish 触发 put_nowait QueueFull，该订阅者被自动剔除。"""
    q = subscribe("agent-full")
    # 直接填满队列到 maxsize=300
    for i in range(300):
        q.put_nowait({"seq": i})
    assert q.full()

    # 再 publish 一条 -> put_nowait 抛 QueueFull -> q 被移出订阅表
    publish("agent-full", {"event": "agent_thinking", "data": {"overflow": True}})

    # 订阅表中不再有该队列
    with ab._lock:
        assert q not in ab._listeners.get("agent-full", [])
    # 被剔除的队列不会收到溢出事件（仍 300 条）
    assert q.qsize() == 300


def test_full_queue_eviction_does_not_block_other_subscribers():
    """满队列剔除不影响同 agent 的其他正常订阅者。"""
    full_q = subscribe("agent-mix")
    ok_q = subscribe("agent-mix")
    for _ in range(300):
        full_q.put_nowait("fill")
    assert full_q.full()

    # 这条 publish 会让 full_q 触发 QueueFull 被剔除，但 ok_q 仍应收到
    publish("agent-mix", {"event": "agent_thinking", "data": {"after": "full"}})

    assert ok_q.qsize() == 1
    payload = json.loads(ok_q.get_nowait())
    assert payload["data"]["after"] == "full"
    with ab._lock:
        assert full_q not in ab._listeners.get("agent-mix", [])
