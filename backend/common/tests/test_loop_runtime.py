#!/usr/bin/env python3
"""Workflow loops — loader 与 loop_runtime 单元测试。"""
from __future__ import annotations

import yaml
import pytest

from common.loop_runtime import (
    AssessSpec,
    LoopSpec,
    TransitionResult,
    TransitionRule,
    _apply_min_rounds_guard,
    evaluate_transition,
    _inject_loop_vars,
    evaluate_until,
    instantiate_round_body_tasks,
    loop_body_task_id,
    parse_loop_specs,
    reconstruct_loop_state,
    resolve_assess_inputs,
    resolve_assess_task_id,
    seed_patch_baseline,
    validate_loop_specs,
)
from common.plan_gate import check_plan
from common.process_types import TaskOutcome
from common.project_artifacts import artifact_rel_path, task_deliverable_base
from common.workflow_loader import load_workflow, workflows_dir, write_workflow_raw

_FIXTURE_PATH = workflows_dir() / "_examples" / "iteration-v2-fixture.yaml"


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


def test_load_plan_improve_workflow_v2_with_loops():
    profile = load_workflow("方案完善")
    assert profile.version == "1.0"
    assert len(profile.loops) == 1
    assert profile.loops[0].id == "plan_improve_round"
    assert profile.loops[0].is_v2 is True
    assert profile.loops[0].assess is not None
    assert profile.loops[0].assess.ref == "step-3"
    loop_task = next(t for t in profile.tasks if t.get("loop"))
    assert loop_task["id"] == "task-1"
    assert loop_task.get("loop") == "plan_improve_round"


def test_parse_loop_specs_v2_fixture():
    specs = parse_loop_specs(yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))["loops"])
    assert len(specs) == 1
    spec = specs[0]
    assert spec.id == "demo"
    assert spec.is_v2 is True
    assert spec.default_body == "default"
    assert "assess" in {t["id"] for t in spec.body_for()}
    assert spec.assess is not None
    assert spec.assess.ref == "assess"
    assert len(spec.transition) == 4


def test_validate_v2_fixture_yaml():
    raw = yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))
    specs = parse_loop_specs(raw["loops"])
    validate_loop_specs(specs, raw["tasks"], {"main", "research"})


def test_validate_v2_transition_next_body_ref():
    bad = LoopSpec(
        id="bad",
        is_v2=True,
        bodies={"default": [{"id": "w", "agent": "research", "task_type": "research", "dependencies": []}]},
        default_body="default",
        transition=[TransitionRule(when="exhausted", next_body="missing")],
    )
    with pytest.raises(ValueError, match="next_body"):
        validate_loop_specs([bad], [], {"main", "research"})


def test_parse_loop_specs_v2_bodies_assess_transition():
    specs = parse_loop_specs([{
        "id": "wave",
        "max_rounds": 3,
        "min_rounds": 1,
        "default_body": "default",
        "bodies": {
            "default": [
                {"id": "work", "agent": "research", "task_type": "research", "dependencies": []},
                {"id": "assess", "agent": "main", "task_type": "iteration-assess",
                 "dependencies": ["work"]},
            ],
        },
        "assess": {"ref": "assess", "inputs": [{"kind": "goal"}]},
        "transition": [
            {"when": "deliverable_marker", "task": "assess", "marker": "ITERATION: PASS",
             "action": "exit", "outcome": "complete"},
        ],
    }])
    assert len(specs) == 1
    spec = specs[0]
    assert spec.id == "wave"
    assert spec.is_v2 is True
    assert spec.default_body == "default"
    assert "default" in spec.bodies
    assert len(spec.bodies["default"]) == 2
    assert isinstance(spec.assess, AssessSpec)
    assert spec.assess.ref == "assess"
    assert len(spec.transition) == 1
    assert isinstance(spec.transition[0], TransitionRule)
    assert spec.transition[0].marker == "ITERATION: PASS"


def test_parse_loop_specs_rejects_body_and_bodies():
    with pytest.raises(ValueError, match="互斥"):
        parse_loop_specs([{
            "id": "bad",
            "body": [{"id": "w", "agent": "research", "task_type": "research", "dependencies": []}],
            "bodies": {"default": [{"id": "w", "agent": "research", "task_type": "research",
                                    "dependencies": []}]},
            "until": [{"type": "deliverable_marker", "task": "w", "marker": "OK"}],
        }])


def test_validate_transition_next_body_refs():
    spec = LoopSpec(
        id="L",
        is_v2=True,
        bodies={
            "default": [
                {"id": "work", "agent": "research", "task_type": "research", "dependencies": []},
                {"id": "assess", "agent": "main", "task_type": "iteration-assess",
                 "dependencies": ["work"]},
            ],
        },
        assess=AssessSpec(ref="assess"),
        transition=[
            TransitionRule(
                when="deliverable_marker", task="assess", marker="ITERATION: CONTINUE",
                action="continue", next_body="missing",
            ),
        ],
        default_body="default",
    )
    tasks = [{"id": "t1", "loop": "L", "dependencies": []}]
    with pytest.raises(ValueError, match="next_body「missing」"):
        validate_loop_specs([spec], tasks, {"main", "research"})


def test_normalize_v1_body_to_internal_bodies():
    """v1 body/until 解析后注入 bodies.default 与 fallback_until。"""
    item = {
        "id": "lr",
        "max_rounds": 2,
        "body": [
            {"id": "work", "agent": "product", "task_type": "research", "dependencies": []},
            {"id": "review", "agent": "arch", "task_type": "research", "dependencies": ["work"]},
        ],
        "until": [{"type": "deliverable_marker", "task": "review", "marker": "REVIEW: PASS"}],
    }
    specs = parse_loop_specs([item])
    spec = specs[0]
    assert spec.is_v2 is False
    assert spec.default_body == "default"
    assert list(spec.bodies.keys()) == ["default"]
    assert len(spec.bodies["default"]) == 2
    assert spec.body == spec.bodies["default"]
    assert spec.fallback_until == spec.until


@pytest.mark.skip(reason="P2: expand_loop_body_for_validation all branches")
def test_expand_loop_body_for_validation_all_branches():
    pass


def test_load_iteration_v2_fixture_workflow():
    assert _FIXTURE_PATH.is_file(), f"missing fixture {_FIXTURE_PATH}"
    profile = load_workflow("iteration-v2-fixture", path=_FIXTURE_PATH)
    assert profile.id == "iteration-v2-fixture"
    assert len(profile.loops) == 1
    spec = profile.loops[0]
    assert spec.id == "demo"
    assert spec.is_v2 is True
    assert spec.bodies
    assert spec.assess
    assert spec.transition
    tasks = profile.instantiate_tasks(goal="fixture smoke")
    result = check_plan(tasks, set(profile.roster), check_capabilities=False)
    assert result.passed, result.feedback


def test_evaluate_transition_pass_marker(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=3,
        default_body="default",
        bodies={
            "default": [
                {"id": "work", "task_type": "research"},
                {"id": "review", "task_type": "research"},
            ],
        },
        assess=AssessSpec(ref="review"),
        transition=[
            TransitionRule(
                when="deliverable_marker", task="review", marker="REVIEW: PASS",
                action="exit", outcome="complete",
            ),
        ],
    )
    tid = loop_body_task_id("L", 1, "review")
    base = task_deliverable_base("p1", tid, "research")
    rel = artifact_rel_path(tid, "research")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nREVIEW: PASS\n", encoding="utf-8")

    result = evaluate_transition(
        spec,
        round_num=1,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "exit"
    assert result.passed is True
    store.close()


def test_evaluate_transition_stop_marker(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=3,
        default_body="default",
        bodies={"default": [{"id": "assess", "task_type": "research"}]},
        assess=AssessSpec(ref="assess"),
        transition=[
            TransitionRule(
                when="deliverable_marker", task="assess", marker="ITERATION: STOP",
                action="exit", outcome="complete",
            ),
        ],
        on_pass="complete",
    )
    tid = loop_body_task_id("L", 1, "assess")
    base = task_deliverable_base("p1", tid, "research")
    rel = artifact_rel_path(tid, "research")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nITERATION: STOP\n", encoding="utf-8")

    result = evaluate_transition(
        spec,
        round_num=1,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "exit"
    assert result.passed is False
    assert result.outcome == "complete"
    store.close()


def test_evaluate_transition_continue_with_next_body(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=3,
        default_body="default",
        bodies={
            "default": [{"id": "assess", "task_type": "research"}],
            "patch": [{"id": "revise", "task_type": "research"}],
        },
        assess=AssessSpec(ref="assess"),
        transition=[
            TransitionRule(
                when="deliverable_marker", task="assess", marker="ITERATION: CONTINUE",
                action="continue", next_body="patch",
            ),
        ],
    )
    tid = loop_body_task_id("L", 1, "assess")
    base = task_deliverable_base("p1", tid, "research")
    rel = artifact_rel_path(tid, "research")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nITERATION: CONTINUE\n", encoding="utf-8")

    result = evaluate_transition(
        spec,
        round_num=1,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "continue"
    assert result.next_body == "patch"
    assert result.passed is False
    store.close()


def test_evaluate_transition_exhausted(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=2,
        default_body="default",
        bodies={"default": [{"id": "review", "task_type": "research"}]},
        transition=[
            TransitionRule(
                when="exhausted", action="exit", outcome="needs_review",
            ),
        ],
        on_exhaust="needs_review",
    )
    tid = loop_body_task_id("L", 2, "review")
    result = evaluate_transition(
        spec,
        round_num=2,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "exit"
    assert result.outcome == "needs_review"
    assert result.passed is False
    store.close()


def test_evaluate_transition_iteration_pass_marker(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=3,
        default_body="default",
        bodies={"default": [{"id": "assess", "task_type": "research"}]},
        assess=AssessSpec(ref="assess"),
        transition=[
            TransitionRule(
                when="deliverable_marker", task="assess", marker="ITERATION: PASS",
                action="exit", outcome="complete",
            ),
        ],
    )
    tid = loop_body_task_id("L", 1, "assess")
    base = task_deliverable_base("p1", tid, "research")
    rel = artifact_rel_path(tid, "research")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nITERATION: PASS\n", encoding="utf-8")

    result = evaluate_transition(
        spec,
        round_num=1,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "exit"
    assert result.passed is True
    assert result.outcome == "complete"
    store.close()


def test_resolve_assess_task_id():
    spec = LoopSpec(
        id="wave",
        is_v2=True,
        bodies={"default": [{"id": "work"}, {"id": "review"}]},
        assess=AssessSpec(ref="assess"),
    )
    assert resolve_assess_task_id(spec, 2, "default") == "wave-r2-assess"
    assert resolve_assess_task_id(spec, 1, body_ref="review") == "wave-r1-review"


def test_min_rounds_enforced():
    spec = LoopSpec(id="L", min_rounds=2, default_body="default")
    early_stop = TransitionResult("exit", "needs_review", None, 0, passed=False)
    guarded = _apply_min_rounds_guard(spec, round_num=1, result=early_stop)
    assert guarded.action == "continue"
    assert guarded.next_body == "default"
    assert guarded.passed is False

    after_min = _apply_min_rounds_guard(spec, round_num=2, result=early_stop)
    assert after_min.action == "exit"
    assert after_min.outcome == "needs_review"

    pass_exit = TransitionResult("exit", "complete", None, 0, passed=True)
    assert _apply_min_rounds_guard(spec, round_num=1, result=pass_exit).passed is True


def test_evaluate_transition_continue_when_no_match(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="L",
        is_v2=True,
        max_rounds=3,
        default_body="default",
        bodies={"default": [{"id": "review", "task_type": "research"}]},
        transition=[
            TransitionRule(
                when="deliverable_marker", task="review", marker="REVIEW: PASS",
                action="exit", outcome="complete",
            ),
        ],
        fallback_until=[],
    )
    tid = loop_body_task_id("L", 1, "review")
    result = evaluate_transition(
        spec,
        round_num=1,
        body_key="default",
        project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "research"},
        store=store,
    )
    assert result.action == "continue"
    assert result.passed is False
    store.close()


def test_load_plan_improve_workflow_collaboration():
    profile = load_workflow("方案完善")
    assert profile.options.get("collaboration", {}).get("group_discussion", {}).get("enabled") is True
    assert profile.options.get("collaboration", {}).get("group_discussion", {}).get("profile") == "work-review-alignment"
    assert len(profile.loops) == 1
    assert profile.loops[0].id == "plan_improve_round"


def test_resolve_assess_inputs_goal_and_phase(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    store.upsert_project("p1", meta={"goal": "GEO 优化目标"})
    spec = LoopSpec(
        id="geo",
        is_v2=True,
        default_body="audit",
        bodies={
            "audit": [
                {"id": "audit", "task_type": "geo-audit"},
                {"id": "assess", "task_type": "iteration-assess", "dependencies": ["audit"]},
            ],
        },
        assess=AssessSpec(ref="assess", inputs=[
            {"kind": "goal"},
            {"kind": "phase.deliverable", "phase": "audit"},
        ]),
    )
    tid = loop_body_task_id("geo", 1, "audit")
    base = task_deliverable_base("p1", tid, "geo-audit")
    rel = artifact_rel_path(tid, "geo-audit")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# audit\n\n发现 3 处问题\n", encoding="utf-8")

    text = resolve_assess_inputs(spec, "p1", 1, "audit", store, "GEO 优化目标")
    assert "GEO 优化目标" in text
    assert "发现 3 处问题" in text
    store.close()


def test_resolve_assess_inputs_ops_log_optional(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    store.upsert_project("p1", meta={"ops_log_publish_log": "已发布 2 篇"})
    spec = LoopSpec(
        id="L",
        is_v2=True,
        default_body="default",
        bodies={"default": [{"id": "assess", "task_type": "iteration-assess"}]},
        assess=AssessSpec(ref="assess", inputs=[
            {"kind": "ops_log", "table": "publish_log", "optional": True},
        ]),
    )
    text = resolve_assess_inputs(spec, "p1", 1, "default", store, "")
    assert "已发布 2 篇" in text
    store.close()


def test_reconstruct_loop_state_resume_after_transition(tmp_path):
    from common.store import Store

    store = Store(tmp_path / "s.db")
    store.upsert_project("p1")
    spec = LoopSpec(
        id="geo",
        is_v2=True,
        max_rounds=6,
        default_body="audit",
        bodies={"audit": [{"id": "w"}], "patch": [{"id": "r"}]},
    )
    scope = "p1:loop:geo"
    store.append_run_event(scope, "loop_round_assess", {
        "round": 1, "body_key": "audit", "action": "continue", "marker": "REVIEW: FAIL",
    })
    store.append_run_event(scope, "loop_transition", {
        "round": 1, "from_body": "audit", "to_body": "patch", "action": "continue",
    })
    store.append_run_event(scope, "loop_round_done", {
        "round": 1, "body_key": "audit", "passed": False,
    })

    state = reconstruct_loop_state(store, "p1", "geo", spec)
    assert state is not None
    assert state.round == 2
    assert state.body_key == "patch"
    store.close()


def test_reconstruct_loop_state_none_when_finished(tmp_path):
    from common.store import Store

    store = Store(tmp_path / "s.db")
    store.upsert_project("p1")
    spec = LoopSpec(id="L", is_v2=True, max_rounds=3, default_body="default",
                    bodies={"default": [{"id": "w"}]})
    scope = "p1:loop:L"
    store.append_run_event(scope, "loop_finished", {"state": "passed", "rounds_used": 1})

    assert reconstruct_loop_state(store, "p1", "L", spec) is None
    store.close()


def test_apply_min_rounds_guard_blocks_stop():
    spec = LoopSpec(id="L", min_rounds=2, default_body="default")
    result = TransitionResult("exit", "needs_review", None, 1, passed=False)
    guarded = _apply_min_rounds_guard(spec, 1, result)
    assert guarded.action == "continue"
    assert guarded.next_body == "default"


def test_evaluate_transition_branch_next_body(tmp_path, monkeypatch):
    import common.paths as paths
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    spec = LoopSpec(
        id="geo",
        is_v2=True,
        max_rounds=6,
        default_body="audit",
        bodies={
            "audit": [{"id": "assess", "task_type": "iteration-assess"}],
            "patch": [{"id": "assess", "task_type": "iteration-assess"}],
        },
        transition=[
            TransitionRule(
                when="deliverable_marker", task="assess", marker="REVIEW: FAIL",
                action="continue", next_body="patch",
            ),
        ],
    )
    tid = loop_body_task_id("geo", 1, "assess")
    base = task_deliverable_base("p1", tid, "iteration-assess")
    rel = artifact_rel_path(tid, "iteration-assess")
    dv = base / rel
    dv.parent.mkdir(parents=True, exist_ok=True)
    dv.write_text("# x\n\nREVIEW: FAIL\n", encoding="utf-8")

    result = evaluate_transition(
        spec, round_num=1, body_key="audit", project_id="p1",
        round_outcomes={tid: TaskOutcome(tid, "completed")},
        body_task_types={tid: "iteration-assess"}, store=store,
    )
    assert result.action == "continue"
    assert result.next_body == "patch"
    store.close()


def test_hydrate_loop_round_from_store_rehydrates_split_children(tmp_path, monkeypatch):
    import common.paths as paths
    from common.loop_runtime import _hydrate_loop_round_from_store
    from common.store import Store

    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
    store = Store(tmp_path / "s.db")
    pid = "pro_x"
    parent_id = "loop-r1-step-2"
    ch1 = f"{parent_id}.ch1"
    ch2 = f"{parent_id}.ch2"
    store.upsert_task(
        pid, parent_id, name="正文", agent="product", task_type="section-authoring",
        status="cancelled", dependencies=["loop-r1-step-1"],
        meta={"split_children": [ch1, ch2]},
    )
    store.upsert_task(
        pid, ch1, name="ch1", agent="product", task_type="section-authoring",
        status="completed", dependencies=["loop-r1-step-1"],
        meta={"description": "d1"},
    )
    store.upsert_task(
        pid, ch2, name="ch2", agent="product", task_type="section-authoring",
        status="pending", dependencies=[ch1],
        meta={"description": "d2"},
    )
    by_id = {
        "loop-r1-step-1": {
            "id": "loop-r1-step-1", "agent": "product", "task_type": "deck-build",
            "dependencies": [],
        },
        parent_id: {
            "id": parent_id, "agent": "product", "task_type": "section-authoring",
            "dependencies": ["loop-r1-step-1"],
        },
        "loop-r1-step-3": {
            "id": "loop-r1-step-3", "agent": "main", "task_type": "section-review",
            "dependencies": [parent_id],
        },
    }
    order = list(by_id.keys())
    outcomes, done = _hydrate_loop_round_from_store(pid, by_id, order, store)
    assert parent_id not in by_id
    assert ch1 in by_id and ch2 in by_id
    assert "loop-r1-step-3" in by_id
    assert ch1 in (by_id["loop-r1-step-3"].get("dependencies") or [])
    assert ch2 in (by_id["loop-r1-step-3"].get("dependencies") or [])
    assert outcomes[ch1].status == "completed"
    assert ch1 in done and ch2 not in done
    store.close()

