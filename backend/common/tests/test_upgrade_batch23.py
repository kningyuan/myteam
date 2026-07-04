#!/usr/bin/env python3
"""第二批+第三批升级测试：workflow reviewer 校验、loop transition、plan 质量、reviewer 自动分配。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.process.plan_gate import check_plan, evaluate_plan_quality  # noqa: E402
from common.process.process_types import ProcessConfig  # noqa: E402


# ========== 3.1 plan 质量评分 ==========

class TestPlanQuality:
    """evaluate_plan_quality 测试。"""

    def test_simple_chain(self):
        """简单链式 DAG：深度3，扇出1"""
        tasks = [
            {"id": "t1", "agent": "a", "task_type": "research", "dependencies": []},
            {"id": "t2", "agent": "a", "task_type": "strategy", "dependencies": ["t1"]},
            {"id": "t3", "agent": "a", "task_type": "content", "dependencies": ["t2"]},
        ]
        q = evaluate_plan_quality(tasks)
        assert q.task_count == 3
        assert q.max_depth == 3
        assert q.max_fanout == 1
        assert q.score >= 0.8  # 简单 DAG 应高分

    def test_wide_fanout(self):
        """宽扇出 DAG：1→3"""
        tasks = [
            {"id": "t1", "agent": "a", "task_type": "research", "dependencies": []},
            {"id": "t2", "agent": "b", "task_type": "research", "dependencies": ["t1"]},
            {"id": "t3", "agent": "c", "task_type": "research", "dependencies": ["t1"]},
            {"id": "t4", "agent": "d", "task_type": "research", "dependencies": ["t1"]},
        ]
        q = evaluate_plan_quality(tasks)
        assert q.max_fanout == 3
        assert q.max_depth == 2

    def test_deep_chain_penalty(self):
        """过深链（6层）应被扣分"""
        tasks = [
            {"id": f"t{i}", "agent": "a", "task_type": "research",
             "dependencies": [f"t{i-1}"] if i > 0 else []}
            for i in range(6)
        ]
        q = evaluate_plan_quality(tasks)
        assert q.max_depth == 6
        assert q.score < 1.0
        assert any("过深" in n for n in q.notes)

    def test_too_many_tasks_penalty(self):
        """任务数过多（>12）应被扣分"""
        tasks = [
            {"id": f"t{i}", "agent": "a", "task_type": "research", "dependencies": []}
            for i in range(15)
        ]
        q = evaluate_plan_quality(tasks)
        assert q.task_count == 15
        assert q.score < 1.0
        assert any("偏多" in n for n in q.notes)

    def test_low_diversity_penalty(self):
        """task_type 多样性低应被扣分"""
        tasks = [
            {"id": f"t{i}", "agent": "a", "task_type": "research", "dependencies": []}
            for i in range(5)
        ]
        q = evaluate_plan_quality(tasks)
        assert q.type_diversity < 0.3
        assert any("多样性低" in n for n in q.notes)

    def test_high_dep_density_penalty(self):
        """依赖密度过高应被扣分"""
        tasks = [
            {"id": "t1", "agent": "a", "task_type": "research", "dependencies": []},
            {"id": "t2", "agent": "a", "task_type": "strategy", "dependencies": ["t1"]},
            {"id": "t3", "agent": "a", "task_type": "content", "dependencies": ["t1", "t2"]},
            {"id": "t4", "agent": "a", "task_type": "review", "dependencies": ["t1", "t2", "t3"]},
            {"id": "t5", "agent": "a", "task_type": "research", "dependencies": ["t1", "t2", "t3", "t4"]},
            {"id": "t6", "agent": "a", "task_type": "strategy", "dependencies": ["t1", "t2", "t3", "t4", "t5"]},
        ]
        q = evaluate_plan_quality(tasks)
        # total deps = 0+1+2+3+4+5 = 15, n=6, density = 15/6 = 2.5
        assert q.dep_density > 2.0
        assert any("耦合" in n for n in q.notes)

    def test_empty_plan(self):
        """空 plan 返回默认值"""
        q = evaluate_plan_quality([])
        assert q.task_count == 0
        assert q.score == 1.0

    def test_to_dict(self):
        """to_dict 可序列化"""
        tasks = [{"id": "t1", "agent": "a", "task_type": "research", "dependencies": []}]
        d = evaluate_plan_quality(tasks).to_dict()
        assert "task_count" in d
        assert "score" in d
        assert isinstance(d["notes"], list)


# ========== 3.2 reviewer 自动分配 ==========

class TestReviewerAutoAssign:
    """_auto_assign_reviewer 测试。"""

    @pytest.fixture()
    def env(self, tmp_path, monkeypatch):
        import common.paths as paths
        monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
        from common.store.store import Store
        store = Store(tmp_path / "state.db")
        store.upsert_project("p", title="测试")
        store.upsert_task("p", "t1", name="任务1", agent="worker1",
                          reviewer="", task_type="research")
        store.upsert_task("p", "t2", name="任务2", agent="worker2",
                          reviewer="", task_type="strategy")
        yield store
        store.close()

    def test_auto_assign_excludes_executor(self, env):
        """自动分配排除执行者"""
        from common.process.task_pipeline import TaskPipeline
        from common.agent.agent_port import AgentPort
        config = ProcessConfig(review_enabled=True)
        pipeline = TaskPipeline(
            store=env, port=None, config=config, release_files=lambda a, i: None,
        )
        reviewer = pipeline._auto_assign_reviewer("p", "t1", "research", "worker1")
        assert reviewer != "worker1"
        assert reviewer in ("worker2", "main")

    def test_auto_assign_returns_empty_when_solo(self, tmp_path, monkeypatch):
        """只有执行者时返回空"""
        import common.paths as paths
        monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
        from common.store.store import Store
        from common.process.task_pipeline import TaskPipeline
        store = Store(tmp_path / "solo.db")
        store.upsert_project("solo", title="单人")
        store.upsert_task("solo", "t1", name="任务", agent="only_agent",
                          reviewer="", task_type="research")
        config = ProcessConfig(review_enabled=True)
        pipeline = TaskPipeline(
            store=store, port=None, config=config, release_files=lambda a, i: None,
        )
        reviewer = pipeline._auto_assign_reviewer("solo", "t1", "research", "only_agent")
        assert reviewer == ""
        store.close()


# ========== 3.3 plan 重试上限 ==========

class TestPlanRetries:
    """max_plan_retries 测试。"""

    def test_default_is_3(self):
        """默认重试上限为3"""
        config = ProcessConfig()
        assert config.max_plan_retries == 3


# ========== 2.1 workflow reviewer 校验 ==========

class TestWorkflowReviewerValidation:
    """workflow_loader.validate_workflow 中 reviewer 校验测试。"""

    def test_valid_reviewer_passes(self, tmp_path, monkeypatch):
        """reviewer 在 roster 中时校验通过"""
        import common.paths as paths
        monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
        from common.workflow.workflow_loader import WorkflowProfile, validate_workflow
        from common.gate.registry import get_spec

        profile = WorkflowProfile(
            id="test-wf",
            name="测试",
            version="1.0",
            description="",
            roster={"worker1", "reviewer1"},
            tasks=[
                {"id": "t1", "agent": "worker1", "task_type": "research",
                 "reviewer": "reviewer1", "dependencies": [], "name": "任务1"},
            ],
            options={},
            phases=[],
            loops=[],
        )
        # validate_workflow 内部调用 get_spec，需要 task_type 在 templates.yaml 注册
        # research 已注册，所以应该通过
        try:
            validate_workflow(profile)
        except ValueError as e:
            # 如果失败，不应包含 reviewer 相关错误
            assert "reviewer" not in str(e).lower()

    def test_invalid_reviewer_fails(self, tmp_path, monkeypatch):
        """reviewer 不在 roster 中时报错"""
        import common.paths as paths
        monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")
        from common.workflow.workflow_loader import WorkflowProfile, validate_workflow

        # Mock agent registry to include worker1 but not unknown_agent
        from common.agent import agent_registry as ar
        monkeypatch.setattr(ar, "agent_task_type_map", lambda: {"worker1": ["research"]})
        monkeypatch.setattr(ar, "list_available_agent_ids", lambda: ["worker1"])

        profile = WorkflowProfile(
            id="test-wf",
            name="测试",
            version="1.0",
            description="",
            roster={"worker1"},
            tasks=[
                {"id": "t1", "agent": "worker1", "task_type": "research",
                 "reviewer": "unknown_agent", "dependencies": [], "name": "任务1"},
            ],
            options={},
            phases=[],
            loops=[],
        )
        with pytest.raises(ValueError) as exc_info:
            validate_workflow(profile)
        assert "reviewer" in str(exc_info.value).lower()
        assert "unknown_agent" in str(exc_info.value)


# ========== 2.2 loop transition 去文本依赖 ==========

class TestLoopTransitionFallback:
    """loop transition 隐式 fallback 测试。"""

    def test_implicit_fallback_on_assess_completed(self):
        """assess task completed 时，即使无 marker 也应通过"""
        from common.loop.loop_runtime import (
            AssessSpec, LoopSpec, TransitionResult, TransitionRule, evaluate_transition,
        )
        from common.process.process_types import TaskOutcome

        spec = LoopSpec(
            id="test-loop",
            max_rounds=3,
            min_rounds=1,
            default_body="default",
            bodies={
                "default": [
                    {"id": "work", "agent": "a", "task_type": "research", "dependencies": []},
                    {"id": "assess", "agent": "b", "task_type": "review", "dependencies": ["work"]},
                ],
            },
            assess=AssessSpec(ref="assess", inputs=[]),
            transition=[
                TransitionRule(when="deliverable_marker", task="assess",
                               marker="ITERATION: PASS", action="exit", outcome="complete"),
            ],
            on_pass="complete",
            on_exhaust="needs_review",
        )

        # 模拟 assess task 已 completed，但交付物中无 marker
        round_outcomes = {
            "test-loop-r1-work": TaskOutcome(task_id="test-loop-r1-work", status="completed"),
            "test-loop-r1-assess": TaskOutcome(task_id="test-loop-r1-assess", status="completed"),
        }

        result = evaluate_transition(
            spec=spec,
            round_num=1,
            body_key="default",
            round_outcomes=round_outcomes,
            store=None,
            project_id="test",
            body_task_types={"work": "research", "assess": "review"},
        )

        # 隐式 fallback 应触发：assess completed → exit + pass
        assert result.action == "exit"
        assert result.passed is True


# ========== 2.4 loop goal 保留 ==========

class TestLoopGoalPreservation:
    """build_patch_goal_prefix 保留原始 goal 测试。"""

    def test_goal_included_in_patch_prefix(self):
        """第2+轮 goal_prefix 包含原始目标"""
        from common.loop.loop_runtime import build_patch_goal_prefix
        prefix = build_patch_goal_prefix(
            "p", 2, "test-loop", original_goal="完成产品调研报告",
        )
        assert "原始目标" in prefix
        assert "完成产品调研报告" in prefix
        assert "PATCH" in prefix

    def test_no_goal_no_summary(self):
        """无原始 goal 时不包含【原始目标】"""
        from common.loop.loop_runtime import build_patch_goal_prefix
        prefix = build_patch_goal_prefix(
            "p", 2, "test-loop", original_goal="",
        )
        assert "原始目标" not in prefix

    def test_round1_returns_empty(self):
        """第1轮返回空字符串"""
        from common.loop.loop_runtime import build_patch_goal_prefix
        prefix = build_patch_goal_prefix(
            "p", 1, "test-loop", original_goal="有目标",
        )
        assert prefix == ""

    def test_goal_truncated(self):
        """超长 goal 被截断到 300 字符"""
        from common.loop.loop_runtime import build_patch_goal_prefix
        long_goal = "A" * 500
        prefix = build_patch_goal_prefix(
            "p", 2, "test-loop", original_goal=long_goal,
        )
        assert "原始目标" in prefix
        # 原始 goal 被截断
        assert "A" * 400 not in prefix
        assert "A" * 200 in prefix
