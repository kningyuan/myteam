"""group_broadcast 单元测试 — 项目群实时事件 pub/sub。

与 agent_broadcast 同构，按 group_id 维护 asyncio.Queue。覆盖：
subscribe / unsubscribe / publish、多订阅者、满队列剔除、空 group_id 短路。
"""

import json

import pytest

import hub.services.group_broadcast as gb
from hub.services.group_broadcast import publish, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def _clean_listeners():
    """每个测试前后清空模块级订阅表，保证用例隔离。"""
    with gb._lock:
        gb._listeners.clear()
    yield
    with gb._lock:
        gb._listeners.clear()


def test_subscribe_returns_queue_and_publish_delivers():
    q = subscribe("group-1")
    publish("group-1", {"event": "agent_thinking", "data": {"agent_id": "a1", "type": "text"}})

    assert q.qsize() == 1
    payload = json.loads(q.get_nowait())
    assert payload["event"] == "agent_thinking"
    assert payload["data"]["agent_id"] == "a1"


def test_multiple_subscribers_all_receive():
    q1 = subscribe("group-multi")
    q2 = subscribe("group-multi")

    publish("group-multi", {"event": "agent_thinking", "data": {}})

    assert q1.qsize() == 1
    assert q2.qsize() == 1
    assert json.loads(q1.get_nowait())["event"] == "agent_thinking"
    assert json.loads(q2.get_nowait())["event"] == "agent_thinking"


def test_unsubscribe_stops_delivery():
    q = subscribe("group-stop")
    unsubscribe("group-stop", q)

    publish("group-stop", {"event": "agent_thinking", "data": {}})

    assert q.qsize() == 0


def test_unsubscribe_only_removes_target_queue():
    q1 = subscribe("group-pair")
    q2 = subscribe("group-pair")
    unsubscribe("group-pair", q1)

    publish("group-pair", {"event": "agent_thinking", "data": {}})

    assert q1.qsize() == 0
    assert q2.qsize() == 1


def test_publish_empty_group_id_is_noop():
    publish("", {"event": "agent_thinking", "data": {}})
    with gb._lock:
        assert "" not in gb._listeners


def test_publish_to_group_without_listeners_is_safe():
    publish("group-nobody", {"event": "agent_thinking", "data": {}})
    with gb._lock:
        assert gb._listeners.get("group-nobody", []) == []


def test_full_queue_evicts_subscriber():
    """队列满（maxsize=300）后 publish 触发自动剔除该订阅者。"""
    q = subscribe("group-full")
    for _ in range(300):
        q.put_nowait("fill")
    assert q.full()

    publish("group-full", {"event": "agent_thinking", "data": {"overflow": True}})

    with gb._lock:
        assert q not in gb._listeners.get("group-full", [])
    assert q.qsize() == 300


def test_groups_are_isolated_by_id():
    """不同 group_id 的订阅互不干扰。"""
    q_a = subscribe("group-a")
    q_b = subscribe("group-b")

    publish("group-a", {"event": "agent_thinking", "data": {"g": "a"}})

    assert q_a.qsize() == 1
    assert q_b.qsize() == 0
    assert json.loads(q_a.get_nowait())["data"]["g"] == "a"
