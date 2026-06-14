#!/usr/bin/env python3
"""Workflow loops — loader 与 loop_runtime 单元测试。"""
from __future__ import annotations

import pytest

from common.loop_runtime import (
    LoopSpec,
    _inject_loop_vars,
    evaluate_until,
    instantiate_round_body_tasks,
    loop_body_task_id,
    parse_loop_specs,
    seed_patch_baseline,
    validate_loop_specs,
)
from common.process_types import TaskOutcome
from common.project_artifacts import artifact_rel_path, task_deliverable_base
from common.workflow_loader import load_workflow, write_workflow_raw


def test_parse_loop_specs_minimal():
    specs = parse_loop_specs([{
        "id": "lr",
        "max_rounds": 3,
        "until": [{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
        "body": [
            {"id": "work", "agent": "product", "task_type": "research", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "research",
             "dependencies": ["work"]},
        ],
    }])
    assert len(specs) == 1
    assert specs[0].id == "lr"
    assert specs[0].max_rounds == 3


def test_instantiate_round_body_tasks_ids_and_deps():
    spec = LoopSpec(
        id="ch3",
        max_rounds=5,
        body=[
            {"id": "work", "agent": "product", "task_type": "strategy", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "strategy", "dependencies": ["work"]},
        ],
        until=[{"type": "deliverable_marker", "task": "review", "marker": "X"}],
    )
    tasks = instantiate_round_body_tasks(spec, 2, goal_prefix="【目标】g\n\n")
    assert len(tasks) == 2
    assert tasks[0]["id"] == "ch3-r2-work"
    assert tasks[1]["id"] == "ch3-r2-review"
    assert tasks[1]["dependencies"] == ["ch3-r2-work"]
    assert "{round}" not in tasks[0].get("description", "")


def test_inject_loop_vars_task_ids():
    out = _inject_loop_vars(
        "work={work_task_id} prev={prev_work_task_id} rv={prev_review_task_id}",
        loop_id="ch3_quality_round",
        round_num=2,
        max_rounds=5,
    )
    assert out == (
        "work=ch3_quality_round-r2-work "
        "prev=ch3_quality_round-r1-work "
        "rv=ch3_quality_round-r1-review"
    )


def test_seed_patch_baseline(tmp_path, monkeypatch):
    import common.paths as paths

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    ddir = tmp_path / "project" / "p1" / "deliverables"
    ddir.mkdir(parents=True)
    prev = ddir / "ch3-r1-work_deliverable.md"
    prev.write_text("# 基线\n", encoding="utf-8")
    assert seed_patch_baseline("p1", "ch3-r1-work", "ch3-r2-work")
    cur = ddir / "ch3-r2-work_deliverable.md"
    assert cur.read_text(encoding="utf-8") == "# 基线\n"


def test_evaluate_until_deliverable_marker(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        body=[{"id": "review", "task_type": "research"}],
        until=[{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
    )
    tid = loop_body_task_id("L", 1, "review")
    base = task_deliverable_base("p1", tid, "research")
    rel = artifact_rel_path(tid, "research")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nREVIEW: PASS\n", encoding="utf-8")

    passed = evaluate_until(
        spec, 1, {tid: TaskOutcome(tid, "completed")}, store, "p1", {tid: "research"},
    )
    assert passed is True
    store.close()


def test_validate_loop_rejects_unknown_loop_ref():
    spec = LoopSpec(
        id="L",
        body=[{"id": "w", "agent": "product", "task_type": "research", "dependencies": []}],
        until=[{"type": "deliverable_marker", "task": "w", "marker": "OK"}],
    )
    tasks = [{"id": "t1", "loop": "missing", "dependencies": []}]
    with pytest.raises(ValueError, match="未知 loop"):
        validate_loop_specs([spec], tasks, {"main", "product"})


def test_write_workflow_with_loops(monkeypatch, tmp_path):
    monkeypatch.setattr("common.workflow_loader.workflows_dir", lambda: tmp_path)
    data = {
        "id": "loop-smoke",
        "version": "2.0",
        "tasks": [
            {"id": "t1", "name": "n", "agent": "research", "task_type": "research",
             "dependencies": []},
            {"id": "t-loop", "name": "loop node", "loop": "r1", "dependencies": ["t1"]},
        ],
        "loops": [{
            "id": "r1",
            "max_rounds": 2,
            "until": [{"type": "deliverable_marker", "task": "rv", "marker": "PASS"}],
            "body": [
                {"id": "wk", "agent": "research", "task_type": "research", "dependencies": []},
                {"id": "rv", "agent": "research", "task_type": "research", "dependencies": ["wk"]},
            ],
        }],
    }
    wid = write_workflow_raw(data)
    profile = load_workflow(wid)
    assert len(profile.loops) == 1


def test_load_product_planning_workflow_v2_with_loops():
    profile = load_workflow("产品规划方案")
    assert profile.version == "2.2"
    assert len(profile.loops) == 1
    assert profile.loops[0].id == "ch3_quality_round"
    loop_task = next(t for t in profile.tasks if t.get("loop"))
    assert loop_task["id"] == "t-ch3-plan"
    assert loop_task.get("loop") == "ch3_quality_round"
