#!/usr/bin/env python3
"""memstack 可用性测试 — 模拟真实多轮对话 / 任务闭环（无 Hub）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.store import Store
from memstack.facade import (
    after_chat_turn,
    inject_for_execute,
    on_chat_turn,
    on_consensus,
    on_project_complete,
    on_task_success,
)
from memstack.kb import get_kb_backend
from memstack.l1.protocol import memory_scope_dm
from memstack.l1.registry import get_agent_memory_provider
from memstack.orchestration.context import (
    ChatTurnContext,
    ConsensusContext,
    ExecuteInjectContext,
    ProjectCompleteContext,
    TaskSuccessContext,
)


@pytest.fixture()
def enable_memstack(monkeypatch):
    monkeypatch.setattr("memstack.facade.memstack_enabled", lambda default=False: True)
    monkeypatch.setattr("memstack.config.memstack_enabled", lambda default=False: True)
    monkeypatch.setattr("memstack.facade.inject_top_k", lambda default=3: 3)


@pytest.fixture()
def sqlite_l1(monkeypatch, tmp_path):
    """强制 L1 使用 sqlite 并绑定临时 store。"""
    store = Store(tmp_path / "l1.db")

    def _provider(name=None):
        from memstack.l1.sqlite import SqliteAgentMemory

        return SqliteAgentMemory(store)

    monkeypatch.setattr("memstack.l1.registry.get_agent_memory_provider", _provider)
    monkeypatch.setattr(
        "memstack.facade.get_agent_memory_provider",
        _provider,
    )
    return store


class TestUsableMemstack:
    """开箱即用：sqlite L1 + sqlite KB + static 偏好。"""

    def test_l1_multi_turn_recall(self, sqlite_l1):
        store = sqlite_l1
        scope = memory_scope_dm("product")
        provider = get_agent_memory_provider()

        after_chat_turn(scope, "什么是 GEO?", "GEO 是生成式引擎优化。", provider=provider)
        hint = provider.before_turn(scope, "GEO 有哪些策略?")
        assert hint
        assert "GEO" in hint or "生成式" in hint
        store.close()

    def test_full_chat_facade_with_preference(
        self, enable_memstack, sqlite_l1, monkeypatch, tmp_path
    ):
        store = sqlite_l1
        monkeypatch.setattr("memstack.preferences.static.CONFIG_DIR", tmp_path)
        (tmp_path / "USER.md").write_text("始终用中文、简洁回答。", encoding="utf-8")

        scope = memory_scope_dm("product")
        provider = get_agent_memory_provider()

        after_chat_turn(scope, "记住：我们主攻 B2B", "好的，已了解 B2B 方向。", provider=provider)
        msg = on_chat_turn(
            ChatTurnContext(scope=scope, message="下一步做什么?", owner_id="product"),
            provider=provider,
        )
        assert "中文" in msg or "B2B" in msg or "下一步" in msg
        store.close()

    def test_execute_inject_kb_and_experience(self, enable_memstack, tmp_path):
        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store)
        kb.write("proj1", "research:t0", "prior lesson", tags=["research", "ledger"])
        kb.write("proj1", "research:note", "domain knowledge", tags=["research"])

        lines: list[str] = []
        inject_for_execute(
            ExecuteInjectContext(
                lines=lines,
                project_id="proj1",
                task_type="research",
                agent_id="product",
                store=store,
            )
        )
        text = "\n".join(lines)
        assert "同类任务经验" in text
        assert "prior lesson" in text
        assert "【相关知识】" in text
        assert "domain knowledge" in text
        store.close()

    def test_task_success_promote_and_reuse(self, tmp_path):
        store = Store(tmp_path / "s.db")
        base = tmp_path / "deliv"
        base.mkdir()
        (base / "ledger.entry.yaml").write_text(
            "task_id: t1\nlesson:\n  worked: 先调研竞品\n  next_time: 加数据\n",
            encoding="utf-8",
        )
        ref = on_task_success(
            TaskSuccessContext(
                base_dir=base,
                project_id="proj1",
                task_id="t1",
                task_type="research",
                store=store,
                gate_passed=True,
            )
        )
        assert ref and ref.startswith("kb://")

        lines: list[str] = []
        inject_for_execute(
            ExecuteInjectContext(
                lines=lines,
                project_id="proj1",
                task_type="research",
                store=store,
            )
        )
        assert any("竞品" in ln for ln in lines)
        store.close()

    def test_project_complete_and_consensus(self, enable_memstack, tmp_path, monkeypatch):
        store = Store(tmp_path / "s.db")
        monkeypatch.setattr(
            "memstack.facade.get_kb_backend",
            lambda s=None: get_kb_backend(store),
        )
        store.upsert_task("pro1", "t1", task_type="research", status="completed")

        ref1 = on_project_complete(
            ProjectCompleteContext(project_id="pro1", store=store, status="completed")
        )
        assert ref1

        ref2 = on_consensus(
            ConsensusContext(group_id="g1", draft_text="测试驱动开发是最佳实践")
        )
        assert ref2

        kb = get_kb_backend(store)
        assert kb.search(tags=["project_review"])
        assert kb.search(tags=["best_practice"])
        store.close()

    def test_gbrain_backend_usable_without_vendor(self, tmp_path):
        from memstack.kb import get_kb_backend

        store = Store(tmp_path / "s.db")
        kb = get_kb_backend(store, backend="gbrain")
        ref = kb.write("p", "title", "content", tags=["x"])
        assert ref.startswith("kb://gbrain/")
        got = kb.search(tags=["x"], project_id="p")
        assert got
        store.close()
