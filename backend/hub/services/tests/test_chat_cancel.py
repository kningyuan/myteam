"""chat_cancel 单元测试 — 活跃对话流取消注册表。

覆盖：
- ChatCancelRegistry：register / unregister / cancel / is_active / 同 key 抢占
- CombinedCancel：合并 SSE 断开 + 显式 /cancel，is_set 任一即 True，set 置位全部
- wrap_producer：合并 cancel 源；断开即取消；结束后自动 unregister
- wrap_producer_background：客户端断开不取消，仅显式 /cancel 或抢占取消；结束后自动 unregister
- session key 辅助函数

注：kill_group_cli_processes / cancel_group_roundtable 涉及 subprocess + skill_settings，
依赖外部环境，本轮不单测（聚焦注册表与 cancel 合并纯逻辑）。
"""

import threading

import pytest

from hub.services.chat_cancel import (
    ChatCancelRegistry,
    CombinedCancel,
    agent_session_key,
    cancel_chat,
    group_session_key,
    is_chat_active,
    register_chat,
    unregister_chat,
    wrap_producer,
    wrap_producer_background,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前后清空模块级注册表，保证用例隔离。"""
    with ChatCancelRegistry._lock:
        ChatCancelRegistry._sessions.clear()
    yield
    with ChatCancelRegistry._lock:
        ChatCancelRegistry._sessions.clear()


# --------------------------------------------------------------------------- #
# ChatCancelRegistry
# --------------------------------------------------------------------------- #

def test_register_returns_event_and_marks_active():
    ev = register_chat("chat:agent:a1")
    assert isinstance(ev, threading.Event)
    assert not ev.is_set()
    assert is_chat_active("chat:agent:a1") is True


def test_cancel_sets_event_and_returns_true():
    ev = register_chat("chat:agent:a2")
    assert cancel_chat("chat:agent:a2") is True
    assert ev.is_set() is True


def test_cancel_unknown_key_returns_false():
    assert cancel_chat("chat:agent:nonexistent") is False


def test_unregister_removes_session():
    ev = register_chat("chat:agent:a3")
    unregister_chat("chat:agent:a3", ev)
    assert is_chat_active("chat:agent:a3") is False


def test_unregister_wrong_event_does_not_remove():
    """unregister 传入不属于该 session 的 event 时不移除（防误删）。"""
    register_chat("chat:agent:a4")
    other = threading.Event()
    unregister_chat("chat:agent:a4", other)
    assert is_chat_active("chat:agent:a4") is True


def test_register_same_key_supersedes_previous():
    """同 key 重复注册会抢占：前一个 event 被置位，新 event 生效。"""
    first = register_chat("chat:agent:a5")
    second = register_chat("chat:agent:a5")

    assert first.is_set() is True       # 被抢占
    assert second.is_set() is False     # 新的未置位
    assert is_chat_active("chat:agent:a5") is True

    # cancel 现在作用于 second
    assert cancel_chat("chat:agent:a5") is True
    assert second.is_set() is True


def test_cancel_after_unregister_is_false():
    ev = register_chat("chat:agent:a6")
    unregister_chat("chat:agent:a6", ev)
    assert cancel_chat("chat:agent:a6") is False


# --------------------------------------------------------------------------- #
# CombinedCancel
# --------------------------------------------------------------------------- #

def test_combined_cancel_initially_unset():
    cc = CombinedCancel(threading.Event(), threading.Event())
    assert cc.is_set() is False


def test_combined_cancel_any_source_triggers():
    """任一源置位即 is_set True。"""
    e1 = threading.Event()
    e2 = threading.Event()
    cc = CombinedCancel(e1, e2)

    e1.set()
    assert cc.is_set() is True

    e1.clear()
    e2.set()
    assert cc.is_set() is True


def test_combined_cancel_set_sets_all_sources():
    e1 = threading.Event()
    e2 = threading.Event()
    cc = CombinedCancel(e1, e2)

    cc.set()

    assert e1.is_set() is True
    assert e2.is_set() is True
    assert cc.is_set() is True


def test_combined_cancel_accepts_single_event():
    e = threading.Event()
    cc = CombinedCancel(e)
    assert cc.is_set() is False
    e.set()
    assert cc.is_set() is True


# --------------------------------------------------------------------------- #
# session key 辅助函数
# --------------------------------------------------------------------------- #

def test_session_key_helpers():
    assert agent_session_key("a1") == "chat:agent:a1"
    assert group_session_key("g1") == "chat:group:g1"


# --------------------------------------------------------------------------- #
# wrap_producer（合并 SSE 断开 + 显式 /cancel）
# --------------------------------------------------------------------------- #

def test_wrap_producer_merges_disconnect_and_registry_cancel():
    """SSE 断开置位 disconnect_cancel 后，inner 通过 combined 能看到。"""
    seen = []

    def inner(combined):
        seen.append(combined.is_set())   # False
        yield "a"
        seen.append(combined.is_set())   # True（disconnect 后）
        yield "b"

    produce = wrap_producer("chat:agent:wp1", inner)
    disc = threading.Event()
    gen = produce(disc)

    assert next(gen) == "a"
    assert is_chat_active("chat:agent:wp1") is True

    disc.set()  # 模拟 SSE 断开
    assert next(gen) == "b"

    assert seen == [False, True]
    # 生成器结束后自动 unregister
    assert list(gen) == []
    assert is_chat_active("chat:agent:wp1") is False


def test_wrap_producer_registry_cancel_visible_to_inner():
    """显式 /cancel API 置位 registry event，inner 通过 combined 看到。"""
    seen = []

    def inner(combined):
        seen.append(combined.is_set())   # False
        yield "x"
        seen.append(combined.is_set())   # True（cancel 后）
        yield "y"

    produce = wrap_producer("chat:agent:wp2", inner)
    gen = produce(threading.Event())

    assert next(gen) == "x"
    assert seen == [False]

    cancel_chat("chat:agent:wp2")  # 显式 /cancel
    assert next(gen) == "y"
    assert seen == [False, True]

    list(gen)
    assert is_chat_active("chat:agent:wp2") is False


def test_wrap_producer_unregisters_on_exception():
    """inner 抛异常时 finally 仍 unregister。"""
    def inner(combined):
        yield "x"
        raise RuntimeError("boom")

    produce = wrap_producer("chat:agent:wp3", inner)
    gen = produce(threading.Event())

    assert next(gen) == "x"
    with pytest.raises(RuntimeError):
        next(gen)

    assert is_chat_active("chat:agent:wp3") is False


# --------------------------------------------------------------------------- #
# wrap_producer_background（断开不取消，仅显式 /cancel 或抢占）
# --------------------------------------------------------------------------- #

def test_wrap_producer_background_ignores_disconnect():
    """客户端断开不取消底层 CLI，inner 仍能继续产出。"""
    def inner(cancel_ev):
        yield "x"
        yield "y"

    produce = wrap_producer_background("chat:agent:bg1", inner)
    disc = threading.Event()
    gen = produce(disc)

    assert next(gen) == "x"
    assert is_chat_active("chat:agent:bg1") is True

    disc.set()  # 客户端断开 —— 不影响
    assert next(gen) == "y"           # 仍能继续产出
    assert is_chat_active("chat:agent:bg1") is True

    list(gen)
    assert is_chat_active("chat:agent:bg1") is False


def test_wrap_producer_background_registry_cancel_stops_inner():
    """wrap_producer_background 下显式 /cancel 对 inner 可见，inner 可据此提前退出。"""
    def inner(cancel_ev):
        yield "x"
        if cancel_ev.is_set():
            return
        yield "y"  # 不会到达

    produce = wrap_producer_background("chat:agent:bg2", inner)
    gen = produce(threading.Event())

    assert next(gen) == "x"
    cancel_chat("chat:agent:bg2")  # 显式 /cancel
    assert list(gen) == []          # inner 检测到 cancel 后提前返回

    assert is_chat_active("chat:agent:bg2") is False
