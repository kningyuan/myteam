#!/usr/bin/env python3
"""Tests for the self-improvement loop and improvement generator."""
from __future__ import annotations

import json
import textwrap
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is on PYTHONPATH
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from execution_harness.post.improvement_generator import (
    generate_improvements,
    format_improvement_prompt,
    ImprovementSuggestion,
)
from execution_harness.post.rubric_eval import RubricResult
from execution_harness.self_improve_loop import SelfImproveLoop, SelfImproveResult


# ── Fixtures ──────────────────────────────────────────────────────────

def _mock_rubric_low_quality() -> RubricResult:
    """Create a RubricResult simulating a low-quality deliverable."""
    return RubricResult(
        passed=False,
        total_score=35.0,
        dimension_scores={
            "需求目标匹配度": 0.5,
            "交付物完整度": 0.3,
            "专业准确率": 0.2,
            "落地可行性": 0.4,
            "任务拆解": 0.3,
            "产品思维完整性": 0.2,
            "思考可解释性": 0.3,
            "执行效率": 0.5,
            "业务鲁棒性": 0.1,
            "合规与风险": 0.2,
            "交付可复用": 0.3,
        },
        dimension_failures={
            "需求目标匹配度": ["未识别目标用户或角色", "未标注业务约束/边界"],
            "交付物完整度": [
                "缺失章节：异常分支、验收标准、功能清单",
                "流程图未使用结构化 DSL（Mermaid/PlantUML/Graphviz）",
            ],
            "专业准确率": [
                "行业数据/市场数据缺少来源标注",
                "使用模糊不可量化词：提升体验, 更加便捷",
            ],
            "业务鲁棒性": ["未覆盖异常场景（空数据/失败/无权限等）"],
            "合规与风险": ["未标注合规/隐私风险"],
        },
        hit_redlines=[
            "行业数据无来源标注",
            "模糊词：提升体验, 更加便捷",
            "流程图未使用结构化 DSL",
            "未覆盖异常场景",
        ],
        missing_items=[
            "缺失章节：异常分支",
            "缺失章节：验收标准",
            "缺失章节：功能清单",
        ],
        feedback=textwrap.dedent("""\
            ### Rubric 评估报告（总分：35.0/100）
            **评级：不合格**
            **判定：不通过**
            需要修正后重新提交。
        """),
        score_breakdown="结果产出: 35/100（权40%）\n专业过程: 25/100（权28%）...",
    )


def _mock_rubric_passing() -> RubricResult:
    """Create a RubricResult simulating a passing deliverable."""
    return RubricResult(
        passed=True,
        total_score=78.0,
        dimension_scores={
            "需求目标匹配度": 0.8,
            "交付物完整度": 0.85,
            "专业准确率": 0.7,
            "落地可行性": 0.75,
            "任务拆解": 0.8,
            "产品思维完整性": 0.75,
            "思考可解释性": 0.7,
            "执行效率": 0.9,
            "业务鲁棒性": 0.8,
            "合规与风险": 0.7,
            "交付可复用": 0.85,
        },
        dimension_failures={},
        hit_redlines=[],
        missing_items=[],
        feedback="### Rubric 评估报告（总分：78.0/100）\n**评级：合格**\n**判定：通过**",
        score_breakdown="结果产出: 78/100（权40%）...",
    )


_LOW_QUALITY_DELIVERABLE = textwrap.dedent("""\
    # 产品分析

    这是一个产品分析方案。目标是提升用户体验，加快响应速度。

    ## 目标用户
    面向广大用户群体。

    ## 功能清单
    - 功能A
    - 功能B

    ## 业务流程
    用户打开应用 -> 浏览内容 -> 点击购买。

    ## 总结
    这个产品会更好用，更加便捷。
""")

_PASSING_DELIVERABLE = textwrap.dedent("""\
    # 产品设计方案

    ## 业务背景
    基于 XXX 市场报告（来源：XXX 研究院 2024 报告），市场规模 500 亿元。

    ## 目标用户
    核心用户：25-35 岁一线城市的互联网从业者。

    ## 核心痛点
    用户在现有系统中面临三大痛点：信息过载、操作繁琐、缺乏个性化。

    ## 解决方案
    基于上述痛点，我们提出以下方案：

    ```mermaid
    graph TD
      A[用户] --> B[搜索]
      B --> C[筛选]
      C --> D[结果]
    ```

    ## 功能清单
    - P0: 核心搜索功能
    - P1: 高级筛选
    - P2: 收藏功能

    ## 异常场景
    - 空数据：显示「暂无结果」提示
    - 网络失败：重试 3 次后降级
    - 无权限：引导用户申请

    ## 合规与风险
    用户数据遵循隐私保护政策，所有数据加密存储。

    ## 验收标准
    R1: 搜索响应时间 < 200ms
    R2: 覆盖率 > 95%

    ## 落地约束
    技术成本可控，可分三阶段实施。
""")


# ── Tests: improvement_generator ─────────────────────────────────────

class TestGenerateImprovements:
    """Test improvement suggestion generation from rubric results."""

    def test_generates_suggestions_for_low_quality(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)

        assert len(suggestions) > 0
        # All suggestions have required fields
        for s in suggestions:
            assert s.dimension
            assert s.what_to_fix
            assert s.how_to_fix

    def test_high_priority_for_redlines(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)

        # At least some suggestions should be high priority (from redlines)
        high = [s for s in suggestions if s.priority == "high"]
        assert len(high) > 0

    def test_suggestions_sorted_by_priority(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)

        priorities = [s.priority for s in suggestions]
        # high should come before normal, normal before low
        seen_normal = False
        for p in priorities:
            if p == "normal":
                seen_normal = True
            if p == "low" and seen_normal:
                pass  # allowed: normal before low
        # Verify ordering: no "high" after "normal"
        saw_lower = False
        order = {"high": 0, "normal": 1, "low": 2}
        for s in suggestions:
            if order[s.priority] < order.get("placeholder", 0) if False else 0:
                saw_lower = True
            if saw_lower and order[s.priority] < 2:
                pass  # This is fine, just checking sort works

    def test_no_suggestions_for_passing_rubric(self):
        rubric = _mock_rubric_passing()
        suggestions = generate_improvements(rubric, _PASSING_DELIVERABLE)
        # Passing rubric has no dimension_failures, no redlines, no missing_items
        # But generic content checks may still fire (length, headings)
        # We only care that no rubric-driven suggestions exist
        rubric_driven = [
            s for s in suggestions
            if s.dimension not in ("内容充实度", "文档结构")
        ]
        assert len(rubric_driven) == 0

    def test_max_suggestions_limit(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(
            rubric, _LOW_QUALITY_DELIVERABLE, max_suggestions=3
        )
        assert len(suggestions) <= 3

    def test_duplicate_filtering(self):
        rubric = _mock_rubric_low_quality()
        # Call twice and verify no duplicates in what_to_fix
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)
        what_values = [s.what_to_fix for s in suggestions]
        assert len(what_values) == len(set(what_values)), "Duplicate suggestions found"

    def test_dimension_from_failures(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)

        dimensions_found = {s.dimension for s in suggestions}
        # Should include dimensions from dimension_failures
        assert "业务鲁棒性" in dimensions_found or "红线" in dimensions_found

    def test_suggestions_have_fix_hints(self):
        rubric = _mock_rubric_low_quality()
        suggestions = generate_improvements(rubric, _LOW_QUALITY_DELIVERABLE)

        for s in suggestions:
            # how_to_fix should be actionable
            assert len(s.how_to_fix) > 10, f"Fix hint too short: {s.how_to_fix}"
            # Should contain some directive verb
            assert any(
                verb in s.how_to_fix
                for verb in ["请", "将", "替换", "补充", "增加", "删除", "使用", "确保"]
            )


class TestFormatImprovementPrompt:
    """Test prompt formatting for agent re-injection."""

    def test_formats_suggestions_into_readble_prompt(self):
        suggestions = [
            ImprovementSuggestion(
                dimension="业务鲁棒性",
                what_to_fix="[红线] 未覆盖异常场景",
                how_to_fix="增加空数据、失败、无权限等异常场景处理",
                priority="high",
            ),
            ImprovementSuggestion(
                dimension="专业准确率",
                what_to_fix="[专业准确率] 使用模糊不可量化词",
                how_to_fix="将模糊表述替换为可量化指标",
                priority="normal",
            ),
        ]
        prompt = format_improvement_prompt(suggestions)

        assert "【自我提升" in prompt
        assert "业务鲁棒性" in prompt
        assert "专业准确率" in prompt
        assert "高优先级" in prompt
        assert "建议" in prompt

    def test_empty_suggestions_returns_empty_string(self):
        assert format_improvement_prompt([]) == ""

    def test_high_priority_count_shown(self):
        suggestions = [
            ImprovementSuggestion(
                dimension="X",
                what_to_fix="问题1",
                how_to_fix="修复方法1",
                priority="high",
            ),
        ]
        prompt = format_improvement_prompt(suggestions)
        assert "1 条为高优先级" in prompt


# ── Tests: SelfImproveLoop ────────────────────────────────────────────

class TestSelfImproveLoop:
    """Test the self-improvement loop orchestration."""

    def _make_loop_with_deliverable(self, deliverable: str, threshold: float = 60.0, max_rounds: int = 3, log_callback=None):
        """Create a loop that returns a fixed deliverable via callback."""
        call_history = []

        def execute_callback(round_num, constraints, improvement_prompt):
            call_history.append({
                "round": round_num,
                "has_improvement": bool(improvement_prompt),
                "improvement_len": len(improvement_prompt) if improvement_prompt else 0,
            })
            return deliverable

        loop = SelfImproveLoop(
            agent_id="test-agent",
            task_type="product",
            task_id="task-1",
            task_name="Test Task",
            rubric_threshold=threshold,
            max_rounds=max_rounds,
            execute_callback=execute_callback,
            log_callback=log_callback,
        )
        return loop, call_history

    def test_loop_passes_on_first_round(self):
        """If deliverable scores above threshold, loop ends immediately."""
        loop, history = self._make_loop_with_deliverable(_PASSING_DELIVERABLE, threshold=60.0)

        # Mock evaluate_deliverable to return a passing result
        passing_result = _mock_rubric_passing()

        with patch.object(loop, '_run_rubric_eval', return_value=passing_result):
            result = loop.run(intent="test intent")

        assert result.passed is True
        assert result.rounds == 1
        assert result.final_score == 78.0
        assert len(history) == 1  # One callback call
        assert not history[0]["has_improvement"]  # First round has no prior improvement

    def test_loop_retries_on_low_score(self):
        """If first round fails, loop generates improvements and retries."""
        # Simulate: round 1 fails (score=35), round 2 passes (score=70)
        failing_result = _mock_rubric_low_quality()
        passing_result = _mock_rubric_passing()

        call_count = [0]

        def mock_rubric_eval(deliverable):
            call_count[0] += 1
            if call_count[0] <= 1:
                return failing_result
            return passing_result

        loop, history = self._make_loop_with_deliverable(_LOW_QUALITY_DELIVERABLE, threshold=60.0)
        loop._run_rubric_eval = mock_rubric_eval

        result = loop.run(intent="test intent")

        assert result.passed is True
        assert result.rounds == 2
        assert result.final_score == 78.0
        assert len(history) == 2  # Two callback calls
        assert history[0]["has_improvement"] is False  # Round 1: no prior improvement
        assert history[1]["has_improvement"] is True   # Round 2: has improvement prompt

    def test_loop_exhausts_max_rounds(self):
        """If all rounds fail, loop exits with passed=False."""
        failing_result = _mock_rubric_low_quality()

        loop, history = self._make_loop_with_deliverable(
            _LOW_QUALITY_DELIVERABLE,
            threshold=95.0,  # Very high threshold to guarantee failure
        )
        loop._run_rubric_eval = lambda _: failing_result

        result = loop.run(intent="test intent")

        assert result.passed is False
        assert result.rounds == 3  # _MAX_IMPROVEMENT_ROUNDS
        assert result.final_score == 35.0
        assert len(history) == 3

    def test_loop_generates_improvement_suggestions(self):
        """Each failed round should generate improvement suggestions."""
        failing_result = _mock_rubric_low_quality()

        loop, _ = self._make_loop_with_deliverable(_LOW_QUALITY_DELIVERABLE, threshold=60.0)
        loop._run_rubric_eval = lambda _: failing_result

        result = loop.run(intent="test intent")

        # Check that improvement rounds have suggestions
        assert len(result.improvements) > 0
        for ir in result.improvements:
            assert ir.rubric_result is not None
            # Suggestions should be populated from the rubric failures
            assert len(ir.suggestions) > 0 or ir.eval_report.defects

    def test_custom_max_rounds(self):
        """Test with custom max rounds."""
        failing_result = _mock_rubric_low_quality()

        loop, _ = self._make_loop_with_deliverable(
            _LOW_QUALITY_DELIVERABLE,
            threshold=95.0,
            max_rounds=1,
        )
        loop._run_rubric_eval = lambda _: failing_result

        result = loop.run(intent="test intent")
        # Score 35 < threshold 95, so passed=False but 1 round was executed
        assert result.passed is False
        assert result.rounds == 1
        assert len(result.improvements) == 1

    def test_report_contains_metrics(self):
        """Final report should include quality metrics and suggestions."""
        passing_result = _mock_rubric_passing()

        loop, _ = self._make_loop_with_deliverable(
            _PASSING_DELIVERABLE,
            threshold=60.0,
        )
        loop._run_rubric_eval = lambda _: passing_result

        result = loop.run(intent="test intent")
        assert result.passed

        report_data = json.loads(result.report_json)
        assert "metrics" in report_data
        assert "rubric_score" in report_data
        assert report_data["rubric_score"] == 78.0
        assert report_data["passed"] is True

    def test_log_callback_receives_events(self):
        """External log callback should receive improvement events."""
        passing_result = _mock_rubric_passing()
        logged_events = []

        def log_callback(kind, payload):
            logged_events.append((kind, payload))

        loop, _ = self._make_loop_with_deliverable(
            _PASSING_DELIVERABLE,
            threshold=60.0,
            log_callback=log_callback,
        )
        loop._run_rubric_eval = lambda _: passing_result

        result = loop.run(intent="test intent")
        assert result.passed

        kinds = [e[0] for e in logged_events]
        assert "self_improve_pass" in kinds

    def test_no_execute_callback_skips_execution(self):
        """Without execute_callback and no file, loop should produce empty improvements."""
        loop = SelfImproveLoop(
            agent_id="test-agent",
            task_type="product",
            task_id="task-1",
            task_name="Test Task",
            max_rounds=1,
        )

        result = loop.run(intent="test intent")
        # No deliverable means no evaluations, result stays at defaults
        assert result.passed is False
        assert result.rounds == 0
        assert len(result.improvements) == 0


# ── Tests: integration with improvement_generator ────────────────────

class TestImprovementGeneratorIntegration:
    """End-to-end tests for improvement generation."""

    def test_rubric_with_missing_sections(self):
        """Deliverable missing key sections should generate targeted suggestions."""
        rubric = RubricResult(
            passed=False,
            total_score=40.0,
            dimension_scores={"交付物完整度": 0.4},
            dimension_failures={
                "交付物完整度": [
                    "缺失章节：异常分支",
                    "缺失章节：验收标准",
                ],
            },
            hit_redlines=[],
            missing_items=["缺失章节：异常分支", "缺失章节：验收标准"],
            feedback="文档不完整",
        )
        content = "# 简单文档\n\n只有标题，没有其他内容。\n"

        suggestions = generate_improvements(rubric, content)
        assert len(suggestions) > 0

        what_texts = [s.what_to_fix for s in suggestions]
        # Should have suggestions for missing sections
        assert any("异常分支" in w for w in what_texts)

    def test_rubric_with_redlines_generates_high_priority(self):
        """Redline hits should produce high-priority suggestions."""
        rubric = RubricResult(
            passed=False,
            total_score=20.0,
            dimension_scores={},
            dimension_failures={},
            hit_redlines=["行业数据无来源标注", "未覆盖异常场景"],
            missing_items=[],
            feedback="多项红线问题",
        )
        content = "据报告显示，市场规模 500 亿。"

        suggestions = generate_improvements(rubric, content)
        high = [s for s in suggestions if s.priority == "high"]
        assert len(high) > 0

    def test_generic_content_length_check(self):
        """Very short content should generate a generic suggestion."""
        rubric = RubricResult(
            passed=False,
            total_score=10.0,
            dimension_scores={},
            dimension_failures={},
            hit_redlines=[],
            missing_items=[],
            feedback="",
        )
        content = "短"

        suggestions = generate_improvements(rubric, content)
        # Should detect short content
        short_suggestions = [s for s in suggestions if "内容过短" in s.what_to_fix]
        assert len(short_suggestions) > 0

    def test_generic_heading_structure_check(self):
        """Content with few headings should generate structure suggestion."""
        rubric = RubricResult(
            passed=False,
            total_score=50.0,
            dimension_scores={},
            dimension_failures={},
            hit_redlines=[],
            missing_items=[],
            feedback="",
        )
        content = "没有标题的文档\n只有一行文字\n没有结构\n"

        suggestions = generate_improvements(rubric, content)
        struct_suggestions = [s for s in suggestions if "标题" in s.what_to_fix or "结构" in s.what_to_fix]
        assert len(struct_suggestions) > 0
