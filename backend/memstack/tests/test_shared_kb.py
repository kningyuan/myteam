#!/usr/bin/env python3
"""共享知识库（用户-Agent 共享 KB）测试 — P1。

验证：
- KB 条目支持 source（user/agent/auto）+ created_by 字段
- 用户写入入口（API create_memory 带 source=user）
- 私聊沉淀（用户说"记住" → 自动存 KB，source=user）
- fetch_kb_entries 搜索范围含用户全局条目
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store.store import Store
from memstack.kb import get_kb_backend
from memstack.l1.protocol import MemoryScope
from memstack.facade import _maybe_remember_to_kb


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def test_memory_write_with_source_and_created_by(store):
    """memory_write 支持 source/created_by 参数。"""
    mid = store.memory_write(
        "__global__", "用户知识", "内容",
        tags=["research"], source="user", created_by="alice",
    )
    row = store.memory_get(mid)
    assert row["source"] == "user"
    assert row["created_by"] == "alice"


def test_memory_write_defaults_source_auto(store):
    """默认 source=auto, created_by=''。"""
    mid = store.memory_write("__global__", "自动沉淀", "内容")
    row = store.memory_get(mid)
    assert row["source"] == "auto"
    assert row["created_by"] == ""


def test_kb_backend_write_with_source(store):
    """KB backend write 透传 source/created_by。"""
    kb = get_kb_backend(store)
    ref = kb.write(
        "__global__", "用户条目", "内容",
        tags=["research"], source="user", created_by="bob",
    )
    entry = kb.get(ref)
    assert entry["source"] == "user"
    assert entry["created_by"] == "bob"


def test_memory_schema_migration_adds_columns(tmp_path):
    """旧库（无 source/created_by 列）启动后自动加列。"""
    db = tmp_path / "old.db"
    # 模拟旧库：手动建无 source/created_by 的 memory 表
    import sqlite3
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE memory (id INTEGER PRIMARY KEY, project_id TEXT, "
        "task_id TEXT, tags TEXT, title TEXT, content TEXT, created_at TEXT)"
    )
    conn.execute(
        "INSERT INTO memory (project_id, title, content) VALUES ('p1','t','c')"
    )
    conn.commit()
    conn.close()

    # 用 Store 打开旧库 → 触发 migration
    s = Store(str(db))
    row = s.memory_get(1)
    assert row["source"] == "auto"  # 默认值
    assert row["created_by"] == ""
    s.close()


def test_maybe_remember_to_kb_triggers_on_remember(store, monkeypatch):
    """用户说"记住" → 自动存 KB，source=user。"""
    monkeypatch.setattr("memstack.facade.memstack_enabled", lambda: True)
    monkeypatch.setattr("memstack.facade.get_kb_backend", lambda _store=None: get_kb_backend(store))
    scope = MemoryScope(agent_id="research")
    ref = _maybe_remember_to_kb(scope, "请记住这个：Claude Code 是 Anthropic 的 CLI", "好的，已记住。")
    assert ref is not None
    assert ref.startswith("kb://")
    entries = get_kb_backend(store).search(text="Claude", project_id="__global__")
    assert any(e["source"] == "user" for e in entries)
    assert any(e["created_by"] == "research" for e in entries)
    assert any("remembered" in (e["tags"] or []) for e in entries)


def test_maybe_remember_to_kb_no_trigger_without_marker(store, monkeypatch):
    """无"记住"关键词时不沉淀。"""
    monkeypatch.setattr("memstack.facade.memstack_enabled", lambda: True)
    monkeypatch.setattr("memstack.facade.get_kb_backend", lambda _store=None: get_kb_backend(store))
    scope = MemoryScope(agent_id="research")
    ref = _maybe_remember_to_kb(scope, "今天天气怎么样", "我不太清楚。")
    assert ref is None


def test_fetch_kb_entries_includes_user_entries(store, monkeypatch):
    """fetch_kb_entries 搜索范围含用户全局条目（source=user）。"""
    monkeypatch.setattr("execution_harness.config.kb_inject_allowed", lambda: True)
    monkeypatch.setattr("execution_harness.config.inject_top_k", lambda: 5)
    monkeypatch.setattr("memstack.kb.get_kb_backend", lambda _store=None: get_kb_backend(store))

    # 用户写入一条全局 KB，content 含 "research" 关键词
    kb = get_kb_backend(store)
    kb.write(
        "__global__", "用户的调研心得", "做 research 时要注重数据来源",
        tags=["user_kb"], source="user", created_by="alice",
    )
    from execution_harness.backends.context_provider import fetch_kb_entries
    entries = fetch_kb_entries("proj1", "research", store=store)
    assert any(e.get("source") == "user" for e in entries)
