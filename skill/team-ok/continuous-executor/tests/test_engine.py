"""
持续任务引擎 — 单元测试
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目依赖路径
_HOME = Path.home()
_OPENCLAW = _HOME / ".openclaw"
sys.path.insert(0, str(_OPENCLAW / "skills" / "team-ok"))
sys.path.insert(0, str(_OPENCLAW / "skills" / "team-ok" / "continuous-executor"))
sys.path.insert(0, str(_OPENCLAW / "skills" / "team-ok" / "continuous-executor" / "scripts"))


def _get_engine():
    import engine
    return engine


def _queue_run_side_effect(task_id: str = "task_001"):
    """Mock task_queue status/next 两轮：先取任务，再 empty。"""
    next_idx = {"n": 0}

    def _mock_run(script, cmd, *args, **kwargs):
        if cmd == "status":
            return (0, "idle", "")
        if cmd == "next":
            next_idx["n"] += 1
            if next_idx["n"] == 1:
                return (0, task_id, "")
            return (0, "none", "")
        return (0, "", "")

    return _mock_run


# ── 工具函数测试 ──


class TestCycleFunctions:
    """测试 cycle 相关工具函数。"""

    def test_is_phase_due_active_no_next(self):
        """没有 next_cycle_at 的 active recurring phase 应到期。"""
        eng = _get_engine()
        phase = {"type": "recurring", "status": "active"}
        assert eng.is_phase_due(phase) is True

    def test_is_phase_due_not_recurring(self):
        """one_time phase 不应到期。"""
        eng = _get_engine()
        phase = {"type": "one_time", "status": "active"}
        assert eng.is_phase_due(phase) is False

    def test_is_phase_due_paused(self):
        """暂停的 phase 不应到期。"""
        eng = _get_engine()
        phase = {"type": "recurring", "status": "paused"}
        assert eng.is_phase_due(phase) is False

    def test_is_phase_due_future(self):
        """未来到期的 phase 不应到期。"""
        eng = _get_engine()
        future = (datetime.now() + timedelta(days=30)).isoformat()
        phase = {"type": "recurring", "status": "active", "next_cycle_at": future}
        assert eng.is_phase_due(phase) is False

    def test_is_phase_due_past(self):
        """过去到期的 phase 应到期。"""
        eng = _get_engine()
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        phase = {"type": "recurring", "status": "active", "next_cycle_at": past}
        assert eng.is_phase_due(phase) is True

    def test_generate_instance_id(self):
        """实例 ID 生成格式。"""
        eng = _get_engine()
        assert eng.generate_instance_id("content", 1) == "content_001"
        assert eng.generate_instance_id("evaluation", 24) == "evaluation_024"


class TestRouteReviewer:
    """reviewer 同侪路由：按 task_type 路由，规避自评审与 main 单点。"""

    def test_route_by_task_type(self):
        eng = _get_engine()
        assert eng.route_reviewer("content", "content") == "seo"
        assert eng.route_reviewer("research", "researcher") == "analyst"
        assert eng.route_reviewer("strategy", "analyst") == "product"
        assert eng.route_reviewer("code-deliverable", "developer") == "tester"
        assert eng.route_reviewer("test-plan", "tester") == "developer"

    def test_main_default_is_overridden_by_routing(self):
        """Main 写死的 'main' 应被 task_type 路由覆盖。"""
        eng = _get_engine()
        assert eng.route_reviewer("content", "content", "main") == "seo"

    def test_avoid_self_review(self):
        """产出者本人不得评审自己，取下一候选。"""
        eng = _get_engine()
        assert eng.route_reviewer("research", "analyst") == "researcher"
        assert eng.route_reviewer("test-plan", "developer") == "tester"

    def test_honor_explicit_peer(self):
        """显式指定的非 main、非本人 reviewer 应被尊重。"""
        eng = _get_engine()
        assert eng.route_reviewer("content", "content", "product") == "product"

    def test_explicit_self_falls_back_to_routing(self):
        eng = _get_engine()
        assert eng.route_reviewer("content", "content", "content") == "seo"

    def test_unknown_task_type_defaults_main(self):
        eng = _get_engine()
        assert eng.route_reviewer("unknown-type", "content") == "main"

    def test_get_cycle_number(self):
        """cycle_number 应为 cycle_count + 1。"""
        eng = _get_engine()
        assert eng.get_cycle_number({"cycle_count": 0}) == 1
        assert eng.get_cycle_number({"cycle_count": 23}) == 24
        assert eng.get_cycle_number({}) == 1


class TestAdjustmentExtraction:
    """测试调整建议提取。"""

    def test_extract_adjustments_empty(self):
        """无调整建议时返回空字典。"""
        eng = _get_engine()
        assert eng.extract_adjustments("纯文本内容") == {}
        assert eng.extract_adjustments("") == {}
        assert eng.extract_adjustments(None) == {}

    def test_extract_cycle_interval(self):
        """提取间隔调整。"""
        eng = _get_engine()
        text = "## 调整建议\n- cycle_interval: 14"
        adj = eng.extract_adjustments(text)
        assert adj.get("cycle_interval") == 14

    def test_extract_pause_phase(self):
        """提取暂停 phase。"""
        eng = _get_engine()
        text = "## 调整建议\n- pause_phase: 月度评估"
        adj = eng.extract_adjustments(text)
        assert adj.get("pause_phase") == "月度评估"

    def test_extract_no_section(self):
        """没有 ## 调整建议 章节时返回空。"""
        eng = _get_engine()
        text = "## 评估结果\n效果良好。\n## 下期计划\n继续优化。"
        assert eng.extract_adjustments(text) == {}


class TestApplyAdjustments:
    """测试调整建议应用。"""

    def test_apply_cycle_interval(self):
        """应用间隔调整。"""
        eng = _get_engine()
        phases = [
            {"name": "执行循环", "type": "recurring", "status": "active", "interval_days": 7, "tasks": []},
        ]
        changes = eng.apply_adjustments(phases, {"cycle_interval": 14})
        assert phases[0]["interval_days"] == 14
        assert "14 天" in changes[0]

    def test_apply_pause_phase(self):
        """应用暂停 phase。"""
        eng = _get_engine()
        phases = [
            {"name": "月度评估", "type": "recurring", "status": "active", "tasks": []},
        ]
        changes = eng.apply_adjustments(phases, {"pause_phase": "月度评估"})
        assert phases[0]["status"] == "paused"
        assert "暂停" in changes[0]


class TestBuildTriggerContext:
    """测试轮次继承上下文的构建。"""

    def test_build_trigger_context_no_last_review(self):
        """没有评审结论时的上下文。"""
        eng = _get_engine()
        context = eng.build_trigger_context(
            "测试项目", {"goal": "提升排名", "current_state": "初始阶段"}, {}, 1, {"id": "task_001"}
        )
        assert context["project_name"] == "测试项目"
        assert context["project_goal"] == "提升排名"
        assert context["cycle_id"] == 1
        assert "last_review" not in context

    def test_build_trigger_context_with_last_review(self):
        """有 Deputy 评审时的上下文。"""
        eng = _get_engine()
        last_review = {
            "cycle_id": 3,
            "effectiveness": "partial",
            "planning_hints": ["加强长尾词"],
            "evidence_summary": "排名+3",
        }
        context = eng.build_trigger_context(
            "测试项目", {"goal": "提升排名", "current_state": "#8"}, last_review, 4, {"id": "task_001"}
        )
        assert context["cycle_id"] == 4
        assert context["last_review"]["cycle_id"] == 3
        assert context["last_review"]["effectiveness"] == "partial"

    def test_normalize_migrates_legacy_last_cycle(self):
        """旧 last_cycle 应迁移为 last_closed_cycle + pending_review。"""
        eng = _get_engine()
        legacy = {
            "last_cycle": {
                "cycle_id": 2,
                "tasks": ["t1"],
                "baseline_metrics": "a",
                "outcome_metrics": "b",
                "effectiveness": "待评估",
                "period": ["2026-01-01", "2026-01-02"],
            },
        }
        out = eng.normalize_continuous_data(legacy)
        assert "last_cycle" not in out
        assert out["last_closed_cycle"]["cycle_id"] == 2
        assert out["pending_review"]["cycle_id"] == 2


class TestContinuousDataIO:
    """测试持续数据读写。"""

    def test_atomic_write_and_read(self):
        """atomic 写入后再读取应返回相同数据。"""
        from common.task_data_store import atomic_write_json

        data = {"project": {"id": "pro_test"}, "cycle_summaries": [{"cycle_id": 1}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "continuous_data.json"
            atomic_write_json(path, data)
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["project"]["id"] == "pro_test"
            assert len(loaded["cycle_summaries"]) == 1


# ── 状态机测试 ──


class TestContinuousExecutor:
    """测试 ContinuousExecutor 状态机。"""

    def test_state_order_contains_all_states(self):
        """STATE_ORDER 应包含新建项目的完整流程（不含 complete）。"""
        eng = _get_engine()
        required = ["crash_recovery", "init", "team_config", "task_plan",
                    "add_tasks", "dispatch_loop"]
        for s in required:
            assert s in eng.ContinuousExecutor.STATE_ORDER, f"缺少状态：{s}"
        assert "complete" not in eng.ContinuousExecutor.STATE_ORDER

    def test_run_excludes_complete(self):
        """run() 首轮结束后不应进入 complete（否则项目会被标 stopped）。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor()
        captured = []

        def capture(states, init_args=()):
            captured.extend(states)
            return True

        with patch.object(ex, "_run_states", side_effect=capture):
            ex.run("GEO 测试", "持续 GEO 优化")
        assert "complete" not in captured

    def test_initial_state(self):
        """初始状态为 INIT。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor()
        assert ex.state == "INIT"
        assert ex.project_id == ""

    def test_crash_recovery_no_project(self):
        """无 project_id 时 crash_recovery 应正常通过。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor()
        assert ex.state_crash_recovery() is True

    def test_run_cycle_before_init_returns_false(self):
        """未初始化的 executor 运行 cycle 应失败。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor()
        # 没有 project_id 和 phases，dispatch_loop 应该失败
        assert ex.state_dispatch_loop() is False


class TestCLIParsing:
    """测试 CLI 参数验证。"""

    def test_main_import(self):
        """engine.py 可被导入。"""
        eng = _get_engine()
        assert hasattr(eng, "main")


class TestEngineBehavior:
    """P1–P4 行为回归测试。"""

    def test_run_cycle_excludes_complete(self):
        """run_cycle 不应在每轮结束时进入 complete。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_test")
        captured = []

        def fake_run_states(states, init_args=()):
            captured.extend(states)
            return True

        with patch.object(ex, "_run_states", side_effect=fake_run_states):
            assert ex.run_cycle() is True
        assert captured == ["crash_recovery", "dispatch_loop"]
        assert "complete" not in captured

    def test_load_config_merges_cycle_defaults(self):
        """自定义 config 应与内置 cycle 默认值合并。"""
        eng = _get_engine()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8",
        ) as f:
            f.write("cycle:\n  interval_days: 14\n")
            path = f.name
        try:
            ex = eng.ContinuousExecutor(config_path=path)
            assert ex.cycle_config["interval_days"] == 14
            assert ex.cycle_config["max_empty_before_backoff"] == 10
            assert ex.cycle_config["backoff_factor"] == 2
        finally:
            Path(path).unlink(missing_ok=True)

    def test_crash_recovery_fails_on_alive_pid(self):
        """存活 PID 时应 fail-closed，不删除锁文件。"""
        eng = _get_engine()
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_id = "pro_alive_test"
            proj_path = Path(tmpdir) / proj_id
            proj_path.mkdir()
            pid_file = proj_path / "continuous-pid"
            pid_file.write_text("99999", encoding="utf-8")

            ex = eng.ContinuousExecutor(proj_id)
            with patch("engine.project_dir", return_value=proj_path), \
                 patch("engine.is_pid_alive", return_value=True):
                assert ex.state_crash_recovery() is False
            assert pid_file.exists()

    def test_run_complete_only_sets_stopped(self):
        """run_complete_only 应将项目标为 stopped。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_stop")
        written = {}

        def capture_write(pid, data):
            written.update(data)

        cdata = {"project": {"id": "pro_stop", "status": "active"}, "cycle_summaries": []}

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch("engine.write_continuous_data", side_effect=capture_write), \
             patch("engine._run_script", return_value=(0, "", "")), \
             patch("engine.project_dir") as mock_pdir:
            mock_pdir.return_value = MagicMock()
            mock_pdir.return_value.__truediv__ = lambda self, x: MagicMock(unlink=MagicMock())
            assert ex.run_complete_only() is True

        assert written["project"]["status"] == "stopped"

    def test_dispatch_runs_quality_gate_on_completed_task(self):
        """任务完成后应执行质量门禁。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_qg")
        task_info = {
            "id": "task_001",
            "name": "写内容",
            "agent": "writer",
            "task_type": "content",
            "reviewer": "",
        }

        with patch("engine._run_script") as mock_run, \
             patch("task_dispatch.get_task_info", return_value=task_info), \
             patch("task_dispatch.TaskDispatchRunner.state_evaluate_task",
                   return_value={"should_split": False, "sub_tasks": []}), \
             patch("task_dispatch.TaskDispatchRunner.state_execute_task", return_value=True), \
             patch.object(ex, "state_quality_gate", return_value=True) as mock_qg, \
             patch("engine.read_continuous_data", return_value={
                 "project": {"name": "x"}, "project_summary": {}, "last_review": {},
             }), \
             patch("engine._notify_event"):
            mock_run.side_effect = _queue_run_side_effect()
            assert ex._run_standard_dispatch_loop() is True
            mock_qg.assert_called_once()
            call_args = mock_qg.call_args[0]
            assert call_args[0] == "task_001"
            assert call_args[1] == "content"

    def test_crash_recovery_cleans_stale_pid(self):
        """死 PID 锁文件应被清理并允许继续。"""
        eng = _get_engine()
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_id = "pro_stale_test"
            proj_path = Path(tmpdir) / proj_id
            proj_path.mkdir()
            pid_file = proj_path / "continuous-pid"
            pid_file.write_text("88888", encoding="utf-8")

            ex = eng.ContinuousExecutor(proj_id)
            with patch("engine.project_dir", return_value=proj_path), \
                 patch("engine.is_pid_alive", return_value=False):
                assert ex.state_crash_recovery() is True
            assert not pid_file.exists()

    def test_run_cycle_aborts_on_alive_pid(self):
        """crash_recovery fail-closed 时 run_cycle 应整体失败。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_blocked")
        with patch.object(ex, "state_crash_recovery", return_value=False), \
             patch.object(ex, "state_dispatch_loop") as mock_dispatch:
            assert ex.run_cycle() is False
            mock_dispatch.assert_not_called()

    def test_dispatch_qg_failure_skips_task_complete(self):
        """质量门禁未通过时不应发送 task_complete。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_qg_fail")
        task_info = {
            "id": "task_001",
            "name": "写内容",
            "agent": "writer",
            "task_type": "content",
            "reviewer": "",
        }
        events = []

        def capture_notify(event, *args, **kwargs):
            events.append(event)

        with patch("engine._run_script") as mock_run, \
             patch("task_dispatch.get_task_info", return_value=task_info), \
             patch("task_dispatch.TaskDispatchRunner.state_evaluate_task",
                   return_value={"should_split": False, "sub_tasks": []}), \
             patch("task_dispatch.TaskDispatchRunner.state_execute_task", return_value=True), \
             patch.object(ex, "state_quality_gate", return_value=False), \
             patch("engine.reset_task"), \
             patch("engine.read_continuous_data", return_value={
                 "project": {"name": "x"}, "project_summary": {}, "last_review": {},
             }), \
             patch("engine._notify_event", side_effect=capture_notify):
            mock_run.side_effect = _queue_run_side_effect()
            assert ex._run_standard_dispatch_loop() is True

        assert "task_complete" not in events
        assert "project_complete" not in events

    def test_dispatch_runs_review_when_reviewer_set(self):
        """有 reviewer 时任务完成后应进入交叉评审。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_review")
        task_info = {
            "id": "task_001",
            "name": "写内容",
            "agent": "writer",
            "task_type": "content",
            "reviewer": "main",
        }

        with patch("engine._run_script") as mock_run, \
             patch("task_dispatch.get_task_info", return_value=task_info), \
             patch("task_dispatch.TaskDispatchRunner.state_evaluate_task",
                   return_value={"should_split": False, "sub_tasks": []}), \
             patch("task_dispatch.TaskDispatchRunner.state_execute_task", return_value=True), \
             patch.object(ex, "state_quality_gate", return_value=True), \
             patch.object(ex, "state_review", return_value=True) as mock_review, \
             patch("engine.read_continuous_data", return_value={
                 "project": {"name": "x"}, "project_summary": {}, "last_review": {},
             }), \
             patch("engine._notify_event"):
            mock_run.side_effect = _queue_run_side_effect()
            assert ex._run_standard_dispatch_loop() is True
            mock_review.assert_called_once()
            assert mock_review.call_args[0][1] == "main"

    def test_quality_gate_failure_resets_task_and_enqueues(self):
        """门禁失败应 reset 任务并重新入队。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_qg_reset")
        from common.quality_gate import GateResult
        failed = GateResult(
            passed=False,
            failures=[{"rule": "length", "expected": ">100", "actual": "50"}],
            feedback="too short",
        )

        with patch("engine.run_quality_gate", return_value=failed), \
             patch("engine.reset_task") as mock_reset, \
             patch("engine._run_script", return_value=(0, "", "")) as mock_run, \
             patch("engine.read_task_data", return_value={"tasks": [
                 {"id": "task_001", "agent": "writer", "subtasks": []},
             ]}), \
             patch("engine.write_task_data"), \
             patch.object(ex, "_notify_task_event"):
            assert ex.state_quality_gate("task_001", "content", "/tmp/d.md") is False

        mock_reset.assert_called_once_with("pro_qg_reset", "task_001")
        enqueue_calls = [
            c for c in mock_run.call_args_list
            if len(c[0]) >= 2 and c[0][1] == "enqueue"
        ]
        assert len(enqueue_calls) == 1

    def test_dispatch_loop_no_due_phases_skips_execution(self):
        """无到期 recurring phase 时不应进入标准 dispatch。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_idle")
        future = (datetime.now() + timedelta(days=7)).isoformat()
        cdata = {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring",
                    "status": "active",
                    "name": "weekly",
                    "next_cycle_at": future,
                    "tasks": [],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": None,
            "last_closed_cycle": {},
        }

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch.object(ex, "_run_standard_dispatch_loop") as mock_std, \
             patch.object(ex, "_check_pending_adjustments"):
            assert ex.state_dispatch_loop() is True
            mock_std.assert_not_called()

    def test_dispatch_loop_generated_instances_have_queue_fields(self):
        """recurring 实例须含 status/priority 等 task_queue 必需字段。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_inst")
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        cdata = {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring",
                    "status": "active",
                    "name": "weekly",
                    "next_cycle_at": past,
                    "cycle_count": 0,
                    "interval_days": 7,
                    "tasks": [
                        {
                            "id": "content",
                            "name": "内容",
                            "agent": "writer",
                            "task_type": "content",
                            "reviewer": "main",
                            "description": "写内容",
                            "dependencies": [],
                        },
                    ],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": None,
            "last_closed_cycle": {},
            "cycle_summaries": [],
        }
        written = {}

        def capture_write(pid, data):
            written["task_data"] = data

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch("engine.read_task_data", return_value={"tasks": []}), \
             patch("engine.write_task_data", side_effect=capture_write), \
             patch("engine.write_continuous_data"), \
             patch.object(ex, "state_cycle_plan", return_value=None), \
             patch.object(ex, "_run_standard_dispatch_loop", return_value=True), \
             patch("engine.get_task_info", return_value=None):
            assert ex.state_dispatch_loop() is True

        tasks = written.get("task_data", {}).get("tasks", [])
        assert len(tasks) == 1
        inst = tasks[0]
        assert inst["id"] == "content_001"
        assert inst["status"] == "pending"
        assert inst["priority"] == 1
        assert inst["preemptible"] is True
        assert inst["timeout_minutes"] == 10
        assert inst["subtasks"] == []
        assert inst["created_at"]
        assert inst["updated_at"]

    def test_dispatch_loop_cycle2_blocks_without_review(self):
        """第 2 轮若无 last_review 且 pending 未处理，应阻塞。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_block")
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        cdata = {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring",
                    "status": "active",
                    "name": "weekly",
                    "next_cycle_at": past,
                    "cycle_count": 1,
                    "interval_days": 7,
                    "tasks": [{"id": "content", "name": "内容", "agent": "writer", "task_type": "content"}],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": {"cycle_id": 1, "requested_at": past},
            "last_closed_cycle": {"cycle_id": 1},
            "cycle_summaries": [],
        }
        with patch("engine.read_continuous_data", return_value=cdata), \
             patch.object(ex, "state_cycle_review", return_value=False):
            assert ex.state_dispatch_loop() is False

    def test_dispatch_loop_calls_cycle_review_before_plan(self):
        """存在 pending_review 时应先 cycle_review。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_rev")
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        cdata = {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring",
                    "status": "active",
                    "name": "weekly",
                    "next_cycle_at": past,
                    "cycle_count": 1,
                    "interval_days": 7,
                    "tasks": [{"id": "content", "name": "内容", "agent": "writer", "task_type": "content", "reviewer": "main", "dependencies": []}],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": {"cycle_id": 1, "requested_at": past},
            "last_closed_cycle": {"cycle_id": 1},
            "cycle_summaries": [],
        }
        after_review = dict(cdata)
        after_review["pending_review"] = None
        after_review["last_review"] = {"cycle_id": 1, "effectiveness": "partial", "planning_hints": []}

        with patch("engine.read_continuous_data", side_effect=[cdata, after_review]), \
             patch("engine.read_task_data", return_value={"tasks": []}), \
             patch("engine.write_task_data"), \
             patch("engine.write_continuous_data"), \
             patch("engine.get_task_info", return_value=None), \
             patch.object(ex, "state_cycle_review", return_value=True) as mock_review, \
             patch.object(ex, "state_cycle_plan", return_value=None), \
             patch.object(ex, "_run_standard_dispatch_loop", return_value=True):
            assert ex.state_dispatch_loop() is True
        mock_review.assert_called_once()

    def test_cycle_close_sets_pending_review_not_effectiveness(self):
        """轮末应写 pending_review，不写 effectiveness。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_close")
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        cdata = {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring",
                    "status": "active",
                    "name": "weekly",
                    "next_cycle_at": past,
                    "cycle_count": 0,
                    "interval_days": 7,
                    "tasks": [
                        {
                            "id": "content",
                            "name": "内容",
                            "agent": "writer",
                            "task_type": "content",
                            "reviewer": "main",
                            "description": "写内容",
                            "dependencies": [],
                        },
                    ],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": None,
            "last_closed_cycle": {},
            "cycle_summaries": [],
        }
        written = {}

        def capture_cdata(pid, data):
            written.update(data)

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch("engine.read_task_data", return_value={"tasks": []}), \
             patch("engine.write_task_data"), \
             patch("engine.write_continuous_data", side_effect=capture_cdata), \
             patch.object(ex, "state_cycle_plan", return_value=None), \
             patch.object(ex, "_run_standard_dispatch_loop", return_value=True), \
             patch("engine.get_task_info", return_value=None), \
             patch("engine.project_dir") as mock_pdir:
            mock_pdir.return_value = MagicMock()
            mock_pdir.return_value.__truediv__ = lambda self, x: MagicMock(unlink=MagicMock())
            assert ex.state_dispatch_loop() is True

        assert written.get("pending_review", {}).get("cycle_id") == 1
        assert written.get("last_closed_cycle", {}).get("cycle_id") == 1
        assert "effectiveness" not in written.get("last_closed_cycle", {})
        assert "last_cycle" not in written

    def test_load_merged_config_empty_path_uses_defaults(self):
        """无 config 路径时应返回完整 cycle 默认值。"""
        eng = _get_engine()
        cfg = eng.load_merged_config("")
        assert cfg["cycle"]["interval_days"] == 7
        assert cfg["cycle"]["max_empty_before_backoff"] == 10


class TestPlanCompliance:
    """P1–P6 计划项对照（行为契约）。"""

    def test_p1_run_cycle_state_order(self):
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_p1")
        order = []

        def capture(states, init_args=()):
            order.extend(states)
            return True

        with patch.object(ex, "_run_states", side_effect=capture):
            ex.run_cycle()
        assert order == ["crash_recovery", "dispatch_loop"]
        assert "complete" not in order

    def test_p4_pid_fail_closed_contract(self):
        """P4：存活 PID → crash_recovery False，不 unlink。"""
        eng = _get_engine()
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_path = Path(tmpdir) / "pro_p4"
            proj_path.mkdir()
            pid_file = proj_path / "continuous-pid"
            pid_file.write_text("99999", encoding="utf-8")
            ex = eng.ContinuousExecutor("pro_p4")
            with patch("engine.project_dir", return_value=proj_path), \
                 patch("engine.is_pid_alive", return_value=True):
                assert ex.state_crash_recovery() is False
            assert pid_file.exists()

    def test_p6_stop_via_run_complete_only_not_run_cycle(self):
        """P6：停止项目走 run_complete_only，不走 run_cycle。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_p6")
        with patch.object(ex, "state_complete", return_value=True) as mock_complete:
            ex.run_complete_only()
        mock_complete.assert_called_once()
        with patch.object(ex, "_run_states") as mock_run:
            ex.run_cycle()
        assert mock_run.call_args[0][0] == ["crash_recovery", "dispatch_loop"]


class TestPhaseConcurrency:
    """F5：多个 recurring phase 同时到期。"""

    def _two_due_phases_cdata(self):
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        return {
            "phases": [
                {"type": "one_time", "status": "completed", "name": "setup"},
                {
                    "type": "recurring", "status": "active", "name": "weekly",
                    "next_cycle_at": past, "cycle_count": 0, "interval_days": 7,
                    "tasks": [{
                        "id": "content", "name": "内容", "agent": "writer",
                        "task_type": "content", "reviewer": "main",
                        "description": "写内容", "dependencies": [],
                    }],
                },
                {
                    "type": "recurring", "status": "active", "name": "monthly",
                    "next_cycle_at": past, "cycle_count": 0, "interval_days": 30,
                    "tasks": [{
                        "id": "evaluation", "name": "评估", "agent": "analyst",
                        "task_type": "report", "reviewer": "main",
                        "description": "月度评估", "dependencies": [],
                    }],
                },
            ],
            "project_summary": {},
            "last_review": {},
            "pending_review": None,
            "last_closed_cycle": {},
            "cycle_summaries": [],
        }

    def test_two_due_phases_generate_both_instances(self):
        """两个 recurring phase 同时到期，应各自生成本轮任务实例。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_concurrent")
        cdata = self._two_due_phases_cdata()
        written = {}

        def capture_task(pid, data):
            written["task_data"] = data

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch("engine.read_task_data", return_value={"tasks": []}), \
             patch("engine.write_task_data", side_effect=capture_task), \
             patch("engine.write_continuous_data"), \
             patch.object(ex, "state_cycle_plan", return_value=None), \
             patch.object(ex, "_run_standard_dispatch_loop", return_value=True), \
             patch("engine.get_task_info", return_value=None):
            assert ex.state_dispatch_loop() is True

        ids = {t["id"] for t in written.get("task_data", {}).get("tasks", [])}
        # fallback 路径按各 phase 自身 cycle_number 实例化；两 phase 都应产出
        assert "content_001" in ids
        assert "evaluation_001" in ids

    def test_two_due_phases_both_cycle_count_incremented(self):
        """两个同时到期的 phase，轮末都应推进 cycle_count 与 next_cycle_at。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_concurrent2")
        cdata = self._two_due_phases_cdata()

        with patch("engine.read_continuous_data", return_value=cdata), \
             patch("engine.read_task_data", return_value={"tasks": []}), \
             patch("engine.write_task_data"), \
             patch("engine.write_continuous_data"), \
             patch.object(ex, "state_cycle_plan", return_value=None), \
             patch.object(ex, "_run_standard_dispatch_loop", return_value=True), \
             patch("engine.get_task_info", return_value=None), \
             patch("engine.archive_cycle_files", return_value={}), \
             patch("engine.project_dir") as mock_pdir:
            mock_pdir.return_value = MagicMock()
            mock_pdir.return_value.__truediv__ = lambda self, x: MagicMock(unlink=MagicMock())
            assert ex.state_dispatch_loop() is True

        recurring = [p for p in ex.phases if p.get("type") == "recurring"]
        assert all(p["cycle_count"] == 1 for p in recurring)
        assert all(p.get("next_cycle_at") for p in recurring)


class TestCycleLock:
    """F6：trigger-now 文件锁互斥。"""

    def test_acquire_then_second_returns_none(self):
        """同一项目第二次取锁应失败（None），释放后可再取。"""
        eng = _get_engine()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("engine.project_dir", return_value=Path(tmpdir)):
                fd1 = eng.acquire_cycle_lock("pro_lock")
                assert fd1 is not None
                fd2 = eng.acquire_cycle_lock("pro_lock")
                assert fd2 is None
                eng.release_cycle_lock(fd1)
                fd3 = eng.acquire_cycle_lock("pro_lock")
                assert fd3 is not None
                eng.release_cycle_lock(fd3)

    def test_run_cycle_skips_when_locked(self):
        """run_cycle 在锁被占用时应直接返回 False，不进入状态机。"""
        eng = _get_engine()
        ex = eng.ContinuousExecutor("pro_lock_busy")
        with patch("engine.acquire_cycle_lock", return_value=None), \
             patch.object(ex, "_run_states") as mock_run:
            assert ex.run_cycle() is False
        mock_run.assert_not_called()


class TestNeedsReviewCollection:
    """F1：needs_review 任务清单收集。"""

    def test_collect_needs_review_filters_by_cycle(self):
        eng = _get_engine()
        td = {"tasks": [
            {"id": "content_001", "status": "needs_review", "name": "a",
             "quality_gate_exhausted": True, "quality_gate_issues": ["缺章节"]},
            {"id": "content_002", "status": "needs_review", "name": "b"},
            {"id": "content_001b", "status": "completed", "name": "c"},
        ]}
        with patch("engine.read_task_data", return_value=td):
            out = eng.collect_needs_review_tasks("pro_nr", cycle_id=1)
        assert len(out) == 1
        assert out[0]["id"] == "content_001"
        assert out[0]["quality_gate_exhausted"] is True

    def test_collect_needs_review_all_cycles(self):
        eng = _get_engine()
        td = {"tasks": [
            {"id": "content_001", "status": "needs_review", "name": "a"},
            {"id": "content_002", "status": "needs_review", "name": "b"},
            {"id": "content_003", "status": "completed", "name": "c"},
        ]}
        with patch("engine.read_task_data", return_value=td):
            out = eng.collect_needs_review_tasks("pro_nr", cycle_id=0)
        assert {o["id"] for o in out} == {"content_001", "content_002"}


class TestSummaryArchive:
    """F3：cycle_summaries 归档。"""

    def test_no_archive_under_threshold(self):
        eng = _get_engine()
        cdata = {"cycle_summaries": [{"cycle_id": i} for i in range(3)]}
        n = eng.archive_overflow_summaries("pro_arc", cdata, max_inmemory=50)
        assert n == 0
        assert len(cdata["cycle_summaries"]) == 3

    def test_archive_overflow_writes_jsonl(self):
        eng = _get_engine()
        cdata = {"cycle_summaries": [{"cycle_id": i} for i in range(5)]}
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("engine.project_dir", return_value=Path(tmpdir)):
                n = eng.archive_overflow_summaries("pro_arc", cdata, max_inmemory=2)
                assert n == 3
                assert len(cdata["cycle_summaries"]) == 2
                assert cdata["cycle_summaries"][0]["cycle_id"] == 3
                jsonl = Path(tmpdir) / "archive" / "cycle_summaries.jsonl"
                assert jsonl.exists()
                lines = jsonl.read_text(encoding="utf-8").strip().split("\n")
                assert len(lines) == 3
                assert json.loads(lines[0])["cycle_id"] == 0


class TestRecentReviewsWindow:
    """F2：recent_reviews 滚动窗口由 normalize 初始化。"""

    def test_normalize_initializes_recent_reviews(self):
        eng = _get_engine()
        out = eng.normalize_continuous_data({"phases": []})
        assert out["recent_reviews"] == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])