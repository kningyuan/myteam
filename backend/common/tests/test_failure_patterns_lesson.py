"""测试 Path D+B 新模块 + Path A 计划 + Path C 质量画像。"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.store import Store


class TestFailurePatterns:
    def test_classify_failure_maps_rules(self):
        from execution_harness.post.failure_patterns import classify_failure

        assert classify_failure("required_sections") == "section_missing"
        assert classify_failure("section_level") == "format_error"
        assert classify_failure("stub") == "content_stub"
        assert classify_failure("file_exists") == "plan_drift"
        assert classify_failure("contract") == "plan_drift"
        assert classify_failure("evidence_url") == "plan_drift"
        assert classify_failure("unknown_rule") == "format_error"  # fallback

    def test_classify_failures_batch_enriches(self):
        from execution_harness.post.failure_patterns import classify_failures

        failures = [
            {"rule": "required_sections", "expected": "背景", "actual": "未找到"},
            {"rule": "stub", "expected": "≥200字符", "actual": "仅30字符"},
        ]
        result = classify_failures(failures)
        assert len(result) == 2
        assert result[0]["pattern"] == "section_missing"
        assert result[0]["label"] == "📋 章节缺失"
        assert result[1]["pattern"] == "content_stub"
        assert result[1]["label"] == "📝 内容空洞"
        for r in result:
            assert "guidance" in r
            assert len(r["guidance"]) > 10

    def test_build_classified_summary(self):
        from execution_harness.post.failure_patterns import build_classified_summary

        failures = [
            {"rule": "required_sections"},
            {"rule": "section_level"},
        ]
        summary = build_classified_summary(failures)
        assert "章节缺失" in summary
        assert "格式错误" in summary

    def test_empty_failures(self):
        from execution_harness.post.failure_patterns import build_classified_summary

        assert build_classified_summary([]) == ""

    def test_pattern_guidance(self):
        from execution_harness.post.failure_patterns import pattern_guidance

        guidances = {
            "section_missing": "章节",
            "content_stub": "内容",
            "format_error": "层级",
            "plan_drift": "任务要求",
            "timeout_interrupt": "超时",
        }
        for pattern, keyword in guidances.items():
            assert keyword in pattern_guidance(pattern)

    def test_fallback_guidance(self):
        from execution_harness.post.failure_patterns import pattern_guidance

        assert "排查" in pattern_guidance("non_existent_pattern")


class TestLessonWrite:
    def test_extract_lesson_from_full_ledger(self, tmp_path):
        from execution_harness.post.lesson import extract_lesson_from_ledger

        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text(
            "task_type: research\n"
            "summary: 调研完成\n"
            "lesson:\n"
            "  worked: 多源交叉验证有效\n"
            "  failed: 未覆盖竞品\n"
            "pitfalls:\n"
            "- 信息源仅限百度，缺 Google Scholar\n"
            "- 未区分一手和二手信息\n",
        )
        result = extract_lesson_from_ledger(tmp_path)
        assert result is not None
        assert "信息源" in result or "竞品" in result

    def test_extract_lesson_no_file(self, tmp_path):
        from execution_harness.post.lesson import extract_lesson_from_ledger

        assert extract_lesson_from_ledger(tmp_path) is None

    def test_extract_lesson_empty_ledger(self, tmp_path):
        from execution_harness.post.lesson import extract_lesson_from_ledger

        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text("# empty\nsummary: done\n", encoding="utf-8")
        result = extract_lesson_from_ledger(tmp_path)
        # 无 pitfalls/lesson 时返回 None
        assert result is None

    def test_write_lesson_entry_creates_memory(self, tmp_path):
        from execution_harness.post.lesson import write_lesson_entry

        store = Store(tmp_path / "test.db")
        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text(
            "task_type: coding\n"
            "lesson:\n  worked: 分步实现\n  failed: 忘了跑测试\n"
            "pitfalls:\n- 测试未覆盖边界\n",
        )
        mem_id = write_lesson_entry(
            store, "proj1", "t1", "coding", "developer", tmp_path, attempt=2,
        )
        assert mem_id is not None
        entries = store.memory_search(tags=["lesson", "coding", "developer"])
        assert entries
        assert any("测试" in (e.get("content") or "") for e in entries)
        store.close()

    def test_write_lesson_entry_no_ledger(self, tmp_path):
        from execution_harness.post.lesson import write_lesson_entry

        store = Store(tmp_path / "s2.db")
        mem_id = write_lesson_entry(
            store, "p1", "t1", "research", "product", tmp_path, attempt=3,
        )
        assert mem_id is None
        store.close()


class TestLessonInject:
    def test_fetch_lesson_entries_returns_lessons(self, tmp_path):
        from execution_harness.pre.lesson_inject import fetch_lesson_entries

        store = Store(tmp_path / "s3.db")
        store.memory_write(
            "p1", "lesson:developer/coding:t1",
            "【教训】忘了跑测试 → 被 Gate 拒绝",
            tags=["lesson", "coding", "developer"],
        )
        entries = fetch_lesson_entries("p1", "coding", "developer", store=store)
        assert entries
        assert any("测试" in (e.get("content") or "") for e in entries)
        store.close()

    def test_fetch_lesson_falls_back_globally(self, tmp_path):
        from execution_harness.pre.lesson_inject import fetch_lesson_entries

        store = Store(tmp_path / "s4.db")
        # 全局条目（不同项目ID）
        store.memory_write(
            "other_proj", "lesson:developer/research:t99",
            "【教训】信息源不够多样",
            tags=["lesson", "research", "developer"],
        )
        entries = fetch_lesson_entries("p1", "research", "developer", store=store)
        assert entries
        assert any("信息源" in (e.get("content") or "") for e in entries)
        store.close()

    def test_fetch_lesson_falls_back_cross_agent(self, tmp_path):
        from execution_harness.pre.lesson_inject import fetch_lesson_entries

        store = Store(tmp_path / "s5.db")
        store.memory_write(
            "p1", "lesson:product/research:t1",
            "【教训】调研范围过大",
            tags=["lesson", "research", "product"],
        )
        # developer 没有 lesson，但可以复用 research 的跨 agent 教训
        entries = fetch_lesson_entries("p1", "research", "developer", store=store)
        assert entries
        store.close()

    def test_append_lesson_hints_appends_block(self):
        from execution_harness.pre.lesson_inject import append_lesson_hints

        lines: list[str] = []
        # store=None → 无 lesson 时不追加
        append_lesson_hints(lines, "p1", "coding", "developer", store=None)
        assert not lines

    def test_append_lesson_hints_empty_when_no_entries(self, tmp_path):
        from execution_harness.pre.lesson_inject import append_lesson_hints

        store = Store(tmp_path / "s6.db")
        lines: list[str] = []
        append_lesson_hints(lines, "p1", "nonexistent", "dev", store=store)
        assert not lines
        store.close()

    def test_integration_write_then_read(self, tmp_path):
        from execution_harness.post.lesson import write_lesson_entry
        from execution_harness.pre.lesson_inject import fetch_lesson_entries

        store = Store(tmp_path / "integ.db")
        ledger = tmp_path / "ledger.entry.yaml"
        ledger.write_text(
            "lesson:\n  worked: 分批提问\n  failed: 未读文档\n"
            "pitfalls:\n- 跳过文档直接问\n",
        )
        mem_id = write_lesson_entry(
            store, "p1", "t1", "research", "developer", tmp_path, attempt=3,
        )
        assert mem_id is not None
        entries = fetch_lesson_entries("p1", "research", "developer", store=store)
        assert entries
        content = entries[0].get("content", "")
        assert "跳过" in content or "文档" in content or "读文档" in content
        store.close()


class TestYamlUtilShared:
    """验证 distill 和 lesson 通过共享 _yaml_util 解析一致。"""

    def test_distill_and_lesson_parse_consistently(self, tmp_path):
        """同一 ledger，distill 和 lesson 都正确提取内容。"""
        from execution_harness.post.lesson import extract_lesson_from_ledger
        from execution_harness.post.distill import distill_ledger_body

        ledger = tmp_path / "ledger.entry.yaml"
        raw = (
            "task_type: coding\n"
            "summary: 完成了登录模块\n"
            "lesson:\n"
            "  worked: 分步实现\n"
            "  failed: 忘了跑测试\n"
            "pitfalls:\n"
            "- 测试未覆盖边界\n"
        )
        ledger.write_text(raw)

        lesson = extract_lesson_from_ledger(tmp_path)
        assert lesson is not None
        assert "测试" in lesson

        distilled = distill_ledger_body(raw, task_type="coding", task_id="t1")
        assert "测试" in distilled
        assert "ledger" in distilled or "coding" in distilled


class TestPlanContract:
    """路径 A：plan 契约 + 门禁。"""

    def test_plan_result_basic(self):
        from common.contracts import PlanResult

        pr = PlanResult(
            approach="先收集资料再分析数据最后撰写报告",
            steps=["收集资料", "分析数据", "撰写报告"],
            risks=["时间不足"],
            confidence=0.8,
        )
        assert pr.approach
        assert len(pr.steps) >= 1

    def test_plan_response_parses(self):
        from common.contracts import PlanResult, PlanResponse, parse_response

        pr = PlanResult(approach="先收集源头数据再分析", steps=["收集资料", "分析数据"])
        resp = PlanResponse(interaction_id="p1:t1:plan", kind="plan", result=pr, status="ok")
        d = resp.model_dump()
        parsed = parse_response(d)
        assert parsed.kind == "plan"

    def test_plan_gate_valid_passes(self):
        from common.gate import check_plan

        ok = {
            "interaction_id": "t:1", "kind": "plan", "status": "ok",
            "result": {
                "approach": "先收集需求再设计方案最后编码实现",
                "steps": ["收集需求", "设计方案", "编码实现"],
                "risks": ["需求不明确"],
                "confidence": 0.8,
            },
        }
        gr = check_plan(ok)
        assert gr.passed, gr.failures

    def test_plan_gate_no_steps_fails(self):
        from common.gate import check_plan

        bad = {
            "interaction_id": "t:2", "kind": "plan", "status": "ok",
            "result": {"approach": "太短", "steps": [], "risks": []},
        }
        gr = check_plan(bad)
        # contract check catches approach < 10 and empty steps
        assert not gr.passed or any("contract" in f["rule"] for f in gr.failures)

    def test_plan_to_string(self):
        from common.task_pipeline import _plan_to_string

        result = {
            "approach": "分三步完成",
            "steps": ["调研", "设计", "编码"],
            "risks": ["时间不足"],
            "confidence": 0.7,
        }
        s = _plan_to_string(result)
        assert "思路" in s
        assert "步骤" in s
        assert "风险" in s


class TestAgentQualityProfile:
    """路径 C：Agent 质量画像。"""

    def test_record_quality_writes_memory(self, tmp_path):
        from execution_harness.post.quality import record_quality

        store = Store(tmp_path / "q.db")
        mid = record_quality(
            store=store,
            project_id="p1", task_id="t1",
            task_type="research", agent_id="developer",
            attempt=2, quality_score=0.85,
            gate_passed=True, review_result="passed", status="completed",
        )
        assert mid is not None
        entries = store.memory_search(tags=["quality", "developer"])
        assert entries
        store.close()

    def test_record_quality_with_failure(self, tmp_path):
        from execution_harness.post.quality import record_quality

        store = Store(tmp_path / "q2.db")
        mid = record_quality(
            store=store, project_id="p1", task_id="t2",
            task_type="coding", agent_id="developer",
            attempt=3, quality_score=0.3,
            gate_passed=False, review_result="skipped", status="failed",
        )
        assert mid is not None
        entries = store.memory_search(tags=["quality", "developer"])
        assert entries
        store.close()

    def test_fetch_quality_profile(self, tmp_path):
        from execution_harness.post.quality import fetch_quality_profile, record_quality

        store = Store(tmp_path / "q3.db")
        record_quality(
            store=store, project_id="p1", task_id="t1",
            task_type="research", agent_id="dev1",
            attempt=1, quality_score=0.9,
            gate_passed=True, review_result="passed", status="completed",
        )
        entries = fetch_quality_profile("dev1", task_type="research", store=store)
        assert entries
        assert any("quality_score: 0.90" in (e.get("content") or "") for e in entries)
        store.close()

    def test_summarize_quality(self, tmp_path):
        from execution_harness.post.quality import record_quality, summarize_quality, fetch_quality_profile

        store = Store(tmp_path / "q4.db")
        record_quality(
            store=store, project_id="p1", task_id="t1",
            task_type="research", agent_id="dev1",
            attempt=1, quality_score=0.9,
            gate_passed=True, review_result="passed", status="completed",
        )
        record_quality(
            store=store, project_id="p1", task_id="t2",
            task_type="research", agent_id="dev1",
            attempt=1, quality_score=0.7,
            gate_passed=True, review_result="passed", status="completed",
        )
        entries = fetch_quality_profile("dev1", task_type="research", store=store)
        summary = summarize_quality(entries)
        assert "Gate 通过率" in summary
        assert "2/2" in summary or "100" in summary
        store.close()

    def test_quality_suggestion_for_failure(self):
        from execution_harness.post.quality import _quality_suggestion

        s = _quality_suggestion(0.5, 3, "failed")
        assert "未完成" in s or "失败" in s or "评估" in s

    def test_quality_suggestion_for_low_score(self):
        from execution_harness.post.quality import _quality_suggestion

        s = _quality_suggestion(0.3, 2, "completed")
        assert "偏低" in s or "复核" in s
        s2 = _quality_suggestion(0.5, 5, "completed")
        assert "重试" in s2
