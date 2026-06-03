#!/usr/bin/env python3
"""P0 对话记忆地基测试：conversation/message CRUD、FTS 检索、Context Assembler。

验收点：
  - 消息按 seq 入库、recent 取近窗；
  - 关键词检索能召回历史；
  - assemble 跨轮可引用旧事实，且组装长度有界（抗注意力偏移/抗膨胀）；
  - 滚动摘要：注入式生成 + 规则回退，summarized_through_seq 推进。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store import Store  # noqa: E402
from common.context_assembler import (  # noqa: E402
    AssemblerConfig, assemble, assemble_context, maybe_update_summary,
)


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_dm_create_idempotent(store):
    cid1 = store.get_or_create_dm("ops")
    cid2 = store.get_or_create_dm("ops")
    assert cid1 == cid2 == "dm:ops"
    conv = store.get_conversation(cid1)
    assert conv["kind"] == "dm"
    assert conv["participants"] == ["user", "ops"]


def test_append_and_recent_order(store):
    cid = store.get_or_create_dm("ops")
    ids = []
    for i in range(5):
        mid, seq = store.append_message(cid, "user", "user", text=f"msg{i}")
        ids.append((mid, seq))
    assert [seq for _, seq in ids] == [1, 2, 3, 4, 5]
    assert store.count_messages(cid) == 5
    recent = store.recent_messages(cid, 3)
    assert [m["text"] for m in recent] == ["msg2", "msg3", "msg4"]  # 升序、近窗


def test_search_recall_and_scoping(store):
    cid = store.get_or_create_dm("ops")
    other = store.get_or_create_dm("seo")
    store.append_message(cid, "user", "user", text="the project codename is OrionAlpha7")
    store.append_message(cid, "agent", "ops", text="noted, will proceed")
    store.append_message(other, "user", "user", text="OrionAlpha7 should not leak here check")

    hits = store.search_messages("OrionAlpha7", conversation_id=cid)
    assert any("OrionAlpha7" in m["text"] for m in hits)
    assert all(m["conversation_id"] == cid for m in hits)  # 会话内隔离


def test_cross_turn_reference_in_recent_window(store):
    cid = store.get_or_create_dm("ops")
    store.append_message(cid, "user", "user", text="我叫小龙，负责知乎运营")
    store.append_message(cid, "agent", "ops", text="好的小龙")
    ctx = assemble(store, cid, "我叫什么", AssemblerConfig(recent_turns=4))
    assert "小龙" in ctx


def test_assemble_includes_summary_and_pins(store):
    cid = store.get_or_create_dm("ops")
    store.append_message(cid, "user", "user", text="hello")
    store.update_conversation_meta(cid, summary="用户在做 GEO 优化",
                                   pins=["禁止接入外部 API"])
    ctx = assemble(store, cid, "hello")
    assert "用户在做 GEO 优化" in ctx
    assert "禁止接入外部 API" in ctx


def test_assemble_budget_bounded(store):
    """灌入大量长消息后，组装上下文长度仍受预算约束（抗膨胀/抗注意力偏移）。"""
    cid = store.get_or_create_dm("ops")
    big = "x" * 2000
    for i in range(50):
        store.append_message(cid, "user", "user", text=f"{i}-{big}")
    cfg = AssemblerConfig(char_budget=4000, recent_turns=6, message_clip=500,
                          recent_floor=1000)
    ctx = assemble(store, cid, "x" * 5, cfg)
    # 预算上界 + 各段头部开销的宽松上界
    assert len(ctx) < cfg.char_budget + 1500


def test_maybe_update_summary_with_injected_fn(store):
    cid = store.get_or_create_dm("ops")
    for i in range(10):
        store.append_message(cid, "user", "user", text=f"line{i}")
    cfg = AssemblerConfig(recent_turns=2, summary_trigger=2)
    called = {}

    def fake_fn(pending, prev):
        called["n"] = len(pending)
        return "FAKE_SUMMARY"

    assert maybe_update_summary(store, cid, summarize_fn=fake_fn, config=cfg) is True
    conv = store.get_conversation(cid)
    assert conv["meta"]["summary"] == "FAKE_SUMMARY"
    assert conv["meta"]["summarized_through_seq"] == 8  # 10 - recent 2
    assert called["n"] == 8


def test_maybe_update_summary_rule_fallback(store):
    cid = store.get_or_create_dm("ops")
    for i in range(6):
        store.append_message(cid, "user", "user", text=f"决策{i}")
    cfg = AssemblerConfig(recent_turns=2, summary_trigger=2)
    # 无 summarize_fn → 规则截断回退
    assert maybe_update_summary(store, cid, config=cfg) is True
    conv = store.get_conversation(cid)
    assert "决策0" in conv["meta"]["summary"]
    assert conv["meta"]["summarized_through_seq"] == 4


def test_clear_conversation_wipes_messages_fts_and_meta(store):
    cid = store.get_or_create_dm("ops")
    store.append_message(cid, "user", "user", text="the codename is OrionAlpha7")
    store.append_message(cid, "agent", "ops", text="ok")
    store.update_conversation_meta(cid, summary="old summary", pins=["keep this"])

    n = store.clear_conversation(cid)
    assert n == 2
    assert store.count_messages(cid) == 0
    assert store.search_messages("OrionAlpha7", conversation_id=cid) == []  # FTS 也清了
    conv = store.get_conversation(cid)
    assert (conv.get("meta") or {}) == {} or conv.get("meta") is None


def test_assemble_context_emits_citations_from_retrieval(store):
    """引用闭环：被检索召回（且进入 prompt）的旧消息应作为 citation 暴露出来。"""
    cid = store.get_or_create_dm("ops")
    # 一条含独特关键词的旧消息
    store.append_message(cid, "user", "user", text="项目代号是 OrionAlpha7 请记住")
    # 灌入足够多的近期消息，把上面那条挤出近窗
    for i in range(8):
        store.append_message(cid, "user", "user", text=f"无关闲聊 {i}")

    cfg = AssemblerConfig(recent_turns=4, retrieval_k=4)
    res = assemble_context(store, cid, "OrionAlpha7", cfg)
    assert isinstance(res, dict) and "text" in res and "citations" in res
    cites = res["citations"]
    assert cites, "应从检索召回中产出引用"
    c = cites[0]
    assert c["type"] == "citation"
    assert c["ref"].startswith(f"{cid}#seq")
    assert "OrionAlpha7" in c["snippet"]
    # 召回的历史片段也应进入上下文文本
    assert "OrionAlpha7" in res["text"]


def test_assemble_context_no_citations_without_history(store):
    """无历史可召回时不应捏造引用（首轮对话）。"""
    cid = store.get_or_create_dm("ops")
    res = assemble_context(store, cid, "随便问问")
    assert res["citations"] == []


def test_summary_not_triggered_below_threshold(store):
    cid = store.get_or_create_dm("ops")
    store.append_message(cid, "user", "user", text="a")
    cfg = AssemblerConfig(recent_turns=2, summary_trigger=2)
    assert maybe_update_summary(store, cid, config=cfg) is False
