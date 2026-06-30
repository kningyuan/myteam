#!/usr/bin/env python3
"""memory FTS + ledger 蒸馏 + roster skills 回退 — 执行质量迭代测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.store.store import Store


class TestMemoryFts:
    def test_memory_search_fts_keyword(self, tmp_path):
        store = Store(tmp_path / "fts.db")
        store.memory_write("p1", "research:t1", "Agent execute harness PRE inject block")
        store.memory_write("p1", "other", "unrelated content")
        hits = store.memory_search(text="harness inject", project_id="p1")
        assert hits
        assert "harness" in (hits[0].get("content") or "").lower()
        store.close()


class TestLedgerDistill:
    def test_distill_yaml_to_summary(self):
        from execution_harness.post.distill import distill_ledger_body

        raw = (
            "task_id: t1\n"
            "task_type: research\n"
            "intent: 全景调研 myteam\n"
            "lesson:\n"
            "  worked: 读 docs + pytest\n"
            "  failed: 未跑 T1 基线\n"
            "pitfalls:\n"
            "- 文档 drift\n"
        )
        out = distill_ledger_body(raw, task_type="research", task_id="t1")
        assert "distilled" in out
        assert "全景调研" in out
        assert "pytest" in out

    def test_promote_writes_distilled_tag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "execution_harness.config.ledger_distill_enabled", lambda default=True: True
        )
        from memstack.orchestration.experience import promote_ledger_to_memory

        store = Store(tmp_path / "s.db")
        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text(
            "task_id: t1\ntask_type: research\nsummary: ok run\n",
            encoding="utf-8",
        )
        ref = promote_ledger_to_memory(tmp_path, "proj1", "t1", "research", store)
        assert ref and ref.startswith("kb://")
        entries = store.memory_search(tags=["distilled"], project_id="proj1")
        assert entries
        store.close()


class TestRosterSkillsFallback:
    def test_get_agent_info_merges_roster_skills(self, tmp_path, monkeypatch):
        import common.agent.agent_registry as reg

        roster = tmp_path / "business-roster.json"
        roster.write_text(
            json.dumps({"agents": {"product": {"skills": ["product-methodology"]}}}),
            encoding="utf-8",
        )
        reg_file = tmp_path / "agents_registry.json"
        reg_file.write_text(
            json.dumps({"version": "1.0", "agents": {"product": {"name": "产品专家"}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(reg, "REGISTRY_FILE", reg_file)
        monkeypatch.setattr(reg, "_ROSTER_FILE", roster)
        info = reg.get_agent_info("product")
        assert info.get("skills") == ["product-methodology"]


class TestInteractiveHarness:
    def test_build_interactive_block_uses_mounted_skill(self, monkeypatch):
        import common.agent.agent_registry as reg
        from execution_harness.pre.interactive import build_interactive_harness_block

        monkeypatch.setattr(
            "execution_harness.config.harness_enabled", lambda default=True: True
        )
        monkeypatch.setattr(
            "execution_harness.config.interactive_harness_enabled",
            lambda default=True: True,
        )
        monkeypatch.setattr(
            reg,
            "get_agent_info",
            lambda aid: {"skills": ["product-methodology"], "task_types": []},
        )
        block = build_interactive_harness_block("product")
        assert "product-methodology" in block
        assert "SKILL.md" in block or "方法论" in block
