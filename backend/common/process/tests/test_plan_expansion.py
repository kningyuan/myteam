#!/usr/bin/env python3
"""plan_expansion 单元测试 — 子任务规范化与 DAG 折回。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.process.plan_splice import normalize_subtasks, splice_subtasks, validate_subtasks  # noqa: E402


def _parent(pid="root"):
    return {
        "id": pid, "name": "root", "agent": "research", "task_type": "research",
        "dependencies": ["up"], "description": "d",
    }


from common.process.plan_expansion import PlanExpander, _is_loop_placeholder  # noqa: E402
from common.process.process_types import ProcessConfig  # noqa: E402
from common.store.store import Store  # noqa: E402


def test_is_loop_placeholder():
    assert _is_loop_placeholder({"id": "t1", "loop": "round1"})
    assert not _is_loop_placeholder({"id": "t1"})
    assert not _is_loop_placeholder({"id": "t1", "loop": ""})


def test_expand_skips_loop_placeholder(monkeypatch, tmp_path):
    store = Store(db_path=tmp_path / "s.db")
    evaluated: list[str] = []

    class FakeDecision:
        def evaluate(self, project_id, task, agents, depth, *, cycle=0):
            evaluated.append(task["id"])
            return None

    expander = PlanExpander(FakeDecision(), store, ProcessConfig(split_enabled=True))
    tasks = [
        {"id": "loop-anchor", "name": "L", "loop": "r1", "dependencies": []},
        {"id": "plain", "name": "P", "agent": "research", "task_type": "research", "dependencies": []},
    ]
    out = expander.expand("pro_x", tasks, ["research"])
    assert evaluated == ["plain"]
    assert any(t["id"] == "loop-anchor" for t in out)


def test_normalize_subtasks_prefixes_ids_and_deps():
    parent = _parent("p1")
    subs = [{"id": "a", "name": "A", "dependencies": ["b"]}]
    out = normalize_subtasks(subs, parent)
    assert out[0]["id"] == "p1.a"
    assert out[0]["dependencies"] == ["p1.b"]
    assert out[0]["agent"] == "research"
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
    team = {"research"}
    subs = [
        {"id": f"s{i}", "agent": "research", "task_type": "research", "dependencies": []}
        for i in range(6)
    ]
    msg = validate_subtasks(subs, team, max_fanout=5)
    assert "5" in msg
