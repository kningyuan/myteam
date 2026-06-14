#!/usr/bin/env python3
"""Token 计量抽象测试（Workflow v3 修正项 2/3）。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store import Store  # noqa: E402
from common.token_usage import (  # noqa: E402
    StoreTokenUsageSink,
    TokenUsageRecord,
    TokenUsageSink,
)


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "state.db")
    yield s
    s.close()


def test_token_usage_record_frozen():
    rec = TokenUsageRecord(
        project_id="pro_x",
        interaction_id="i1",
        tokens=580,
        agent_id="research",
        backend="claude",
        model="claude-sonnet-4",
    )
    assert rec.tokens == 580
    assert rec.backend == "claude"


def test_store_sink_is_protocol(store):
    sink = StoreTokenUsageSink(store)
    assert isinstance(sink, TokenUsageSink)


def test_store_sink_bumps_interaction_tokens(store):
    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x", agent_id="research", backend="claude")
    sink = StoreTokenUsageSink(store)
    sink.record_usage("pro_x", "i1", 100, agent_id="research", backend="claude", model="m1")
    assert store.get_interaction("i1")["tokens"] == 100
    sink.record_usage("pro_x", "i1", 80, agent_id="research", backend="claude", model="m1")
    assert store.get_interaction("i1")["tokens"] == 100
    sink.record_usage("pro_x", "i1", 250, agent_id="research", backend="claude", model="m1")
    assert store.get_interaction("i1")["tokens"] == 250


def test_store_sink_skips_non_positive(store):
    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x")
    StoreTokenUsageSink(store).record_usage("pro_x", "i1", 0)
    assert store.get_interaction("i1")["tokens"] == 0


def test_finalize_interaction_uses_token_sink(store, tmp_path):
    """finalize 路径经 TokenUsageSink 落盘，而非直接 bump_interaction_tokens。"""
    from unittest.mock import MagicMock

    from common.agent_port import finalize_interaction

    store.upsert_project("pro_x")
    store.create_interaction("i1", "execute", "pro_x", agent_id="research", backend="claude")
    mock_sink = MagicMock()
    resp_path = tmp_path / "i1.response"
    resp = {
        "interaction_id": "i1",
        "kind": "execute",
        "status": "ok",
        "meta": {"tokens": 321},
        "result": {"outcome": {"kind": "artifact", "artifact": {"path": "x.md"}}},
    }
    finalize_interaction(store, "i1", resp_path, resp, token_sink=mock_sink)
    mock_sink.record_usage.assert_called_once_with(
        "pro_x", "i1", 321, agent_id="research", backend="claude",
    )
    assert store.get_interaction("i1")["status"] == "done"
