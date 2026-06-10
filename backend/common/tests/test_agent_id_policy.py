#!/usr/bin/env python3
"""agent_id_policy 单测。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from common.agent_id_policy import (  # noqa: E402
    assert_auto_create_allowed,
    normalize_agent_id,
    normalize_agent_ids,
    normalize_plan_tasks,
    partition_auto_create_candidates,
)
from common.plan_gate import check_plan  # noqa: E402


def test_normalize_researcher_alias():
    assert normalize_agent_id("researcher") == "research"
    assert normalize_agent_ids(["researcher", "research", "main"]) == ["research", "main"]


def test_normalize_plan_tasks():
    tasks = [{"id": "t1", "agent": "researcher", "task_type": "research"}]
    out = normalize_plan_tasks(tasks)
    assert out[0]["agent"] == "research"


def test_check_plan_accepts_researcher_after_alias(monkeypatch):
    monkeypatch.setattr(
        "common.agent_registry.agent_task_type_map",
        lambda: {"research": ["research"]},
    )
    tasks = [{"id": "a", "name": "n", "agent": "researcher", "task_type": "research", "dependencies": []}]
    r = check_plan(tasks, {"research"})
    assert r.passed, r.feedback


def test_assert_auto_create_rejects_unknown(monkeypatch):
    monkeypatch.setattr(
        "common.agent_id_policy.allowed_auto_create_ids",
        lambda: frozenset({"main", "research"}),
    )
    assert assert_auto_create_allowed("researcher") == "research"
    with pytest.raises(RuntimeError, match="ghost"):
        assert_auto_create_allowed("ghost")


def test_partition_auto_create(monkeypatch):
    monkeypatch.setattr(
        "common.agent_id_policy.allowed_auto_create_ids",
        lambda: frozenset({"research", "main"}),
    )
    ok, bad = partition_auto_create_candidates(["researcher", "ghost"])
    assert ok == ["research"]
    assert bad == ["ghost"]
