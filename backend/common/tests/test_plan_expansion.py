#!/usr/bin/env python3
"""plan_expansion 单元测试 — 子任务规范化与 DAG 折回。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.plan_splice import normalize_subtasks, splice_subtasks, validate_subtasks  # noqa: E402


def _parent(pid="root"):
    return {
        "id": pid, "name": "root", "agent": "researcher", "task_type": "research",
        "dependencies": ["up"], "description": "d",
    }


def test_normalize_subtasks_prefixes_ids_and_deps():
    parent = _parent("p1")
    subs = [{"id": "a", "name": "A", "dependencies": ["b"]}]
    out = normalize_subtasks(subs, parent)
    assert out[0]["id"] == "p1.a"
    assert out[0]["dependencies"] == ["p1.b"]
    assert out[0]["agent"] == "researcher"
    assert out[0]["task_type"] == "research"


def test_splice_inherits_parent_deps_when_subtask_has_none():
    parent = _parent("p1")
    subs = normalize_subtasks([{"id": "a", "name": "A", "dependencies": []}], parent)
    result = {"p1": parent}
    splice_subtasks(result, parent, subs)
    assert result["p1.a"]["dependencies"] == ["up"]


def test_splice_replaces_parent_and_rewrites_dependents():
    parent = _parent("p1")
    other = {"id": "p2", "dependencies": ["p1"]}
    subs = [{"id": "p1.a", "dependencies": []}, {"id": "p1.b", "dependencies": ["p1.a"]}]
    result = {"p1": parent, "p2": other}
    splice_subtasks(result, parent, subs)
    assert "p1" not in result
    assert result["p2"]["dependencies"] == ["p1.a", "p1.b"]


def test_validate_subtasks_rejects_fanout():
    team = {"researcher"}
    subs = [
        {"id": f"s{i}", "agent": "researcher", "task_type": "research", "dependencies": []}
        for i in range(6)
    ]
    msg = validate_subtasks(subs, team, max_fanout=5)
    assert "5" in msg
