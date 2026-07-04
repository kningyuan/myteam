#!/usr/bin/env python3
"""plan_gate 单元测试 — 从 test_process 拆出，覆盖纯函数门禁。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.process.plan_gate import check_plan, prefix_cycle, topological_order  # noqa: E402


def _task(tid, agent="research", task_type="research", deps=None):
    return {
        "id": tid, "name": tid, "agent": agent, "task_type": task_type,
        "dependencies": deps or [],
    }


def test_topological_order_and_cycle():
    tasks = [{"id": "a", "dependencies": []}, {"id": "b", "dependencies": ["a"]}]
    assert topological_order(tasks) == ["a", "b"]
    with pytest.raises(ValueError):
        topological_order([{"id": "a", "dependencies": ["b"]},
                           {"id": "b", "dependencies": ["a"]}])
    prefixed = prefix_cycle(tasks, 2)
    assert prefixed[0]["id"] == "c2_a"
    assert prefixed[1]["dependencies"] == ["c2_a"]


def test_check_plan_valid():
    team = {"research"}
    tasks = [_task("a")]
    r = check_plan(tasks, team)
    assert r.passed


def test_check_plan_empty_plan():
    r = check_plan([], {"research"})
    assert r.passed


def test_check_plan_duplicate_ids():
    r = check_plan([_task("a"), _task("a")], {"research"})
    assert not r.passed
    assert "重复" in r.feedback


def test_check_plan_agent_not_in_team():
    r = check_plan([_task("a", agent="ghost")], {"research"})
    assert not r.passed
    assert "ghost" in r.feedback


def test_check_plan_unregistered_task_type():
    r = check_plan([_task("a", task_type="fake_type")], {"research"})
    assert not r.passed
    assert "fake_type" in r.feedback


def test_check_plan_agent_empty_task_types(monkeypatch, tmp_path):
    import common.agent.agent_registry as agent_registry_mod

    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "agents": {"research": {"name": "研究员", "task_types": []}},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)

    r = check_plan(
        [_task("a", agent="research", task_type="research")],
        {"research"},
        check_capabilities=True,
    )
    assert not r.passed
    assert "未配置可执行任务类型" in r.feedback


def test_check_plan_agent_task_type_mismatch(monkeypatch, tmp_path):
    import common.agent.agent_registry as agent_registry_mod

    reg_path = tmp_path / "agents_registry.json"
    reg_path.write_text(json.dumps({
        "agents": {"research": {"task_types": ["research"]}},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_registry_mod, "REGISTRY_FILE", reg_path)

    r = check_plan(
        [_task("a", agent="research", task_type="section-review")],
        {"research"},
        check_capabilities=True,
    )
    assert not r.passed
    assert "能力边界" in r.feedback or "不能执行" in r.feedback


def test_check_plan_dangling_dependency():
    r = check_plan([_task("a", deps=["nonexistent"])], {"research"})
    assert not r.passed
    assert "nonexistent" in r.feedback


def test_check_plan_cycle():
    r = check_plan([_task("a", deps=["b"]), _task("b", deps=["a"])], {"research"})
    assert not r.passed
    assert "环" in r.feedback


def test_check_plan_fanout_exceeded():
    tasks = [_task(f"t{i}") for i in range(6)]
    r = check_plan(tasks, {"research"}, max_fanout=5)
    assert not r.passed
    assert "5" in r.feedback


def test_check_plan_mixed_errors_first_wins():
    tasks = [_task("a"), _task("a", agent="ghost", task_type="fake")]
    r = check_plan(tasks, {"research"})
    assert not r.passed
    assert "重复" in r.feedback
