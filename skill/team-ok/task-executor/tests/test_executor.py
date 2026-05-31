#!/usr/bin/env python3
"""Tests for executor.py state machine.

Covers all 6 states:
  INIT → TEAM_CONFIG → TASK_PLAN → ADD_TASKS → DISPATCH_LOOP → COMPLETE

Plus helpers: try_resume, _read_task_data, _run_script, _notify_agent
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import pytest


# ============================================================================
# Helper tests
# ============================================================================


class TestHelpers:
    """Test executor helper functions."""

    def test_read_task_data_empty(self, executor_mod, mock_home):
        """_read_task_data returns default dict when no file exists."""
        data = executor_mod._read_task_data("pro_nonexistent")
        assert data == {"project": {}, "tasks": []}

    def test_read_task_data_exists(self, executor_mod, mock_home, sample_task_data):
        """_read_task_data returns parsed JSON."""
        executor_mod._write_task_data("pro_test_001", sample_task_data)
        data = executor_mod._read_task_data("pro_test_001")
        assert data["project"]["id"] == "pro_test_001"
        assert len(data["tasks"]) == 3

    def test_write_task_data(self, executor_mod, mock_home, sample_task_data):
        """_write_task_data writes valid JSON file."""
        executor_mod._write_task_data("pro_test_001", sample_task_data)
        path = mock_home / ".openclaw" / "tasks" / "projects" / "pro_test_001" / "task_data.json"
        assert path.exists()
        written = json.loads(path.read_text())
        assert written["project"]["name"] == "测试项目"

    def test_script_path_resolves(self, executor_mod, mock_home):
        """_script returns absolute path under ~/.openclaw/skills/team-ok/."""
        sp = executor_mod._script("task-queue/scripts/task_queue.py")
        expected = mock_home / ".openclaw" / "skills" / "team-ok" / "task-queue/scripts/task_queue.py"
        assert sp == str(expected)

    def test_project_dir_resolves(self, executor_mod, mock_home):
        """_project_dir returns path under tasks/projects/."""
        pd = executor_mod._project_dir("pro_test_001")
        expected = mock_home / ".openclaw" / "tasks" / "projects" / "pro_test_001"
        assert pd == expected


class TestRunScript:
    """Test _run_script function."""

    def test_success(self, executor_mod):
        """_run_script returns (0, stdout, '') on success."""
        with patch.object(executor_mod, "subprocess") as mock_sp:
            mock_sp.run.return_value = MagicMock(returncode=0, stdout="hello\n", stderr="")
            rc, out, err = executor_mod._run_script("/tmp/test.py", "arg1")
            assert rc == 0
            assert out == "hello"
            assert err == ""

    def test_failure(self, executor_mod):
        """_run_script returns (1, '', stderr) on failure."""
        with patch.object(executor_mod, "subprocess") as mock_sp:
            mock_sp.run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            rc, out, err = executor_mod._run_script("/tmp/test.py")
            assert rc == 1
            assert err == "error"

    def test_timeout(self, executor_mod):
        """_run_script propagates TimeoutExpired."""
        with patch.object(executor_mod, "subprocess") as mock_sp:
            mock_sp.run.side_effect = subprocess.TimeoutExpired("cmd", 30)
            with pytest.raises(subprocess.TimeoutExpired):
                executor_mod._run_script("/tmp/test.py")


# ============================================================================
# State: INIT
# ============================================================================


class TestStateInit:
    """Test INIT state — project creation."""

    def test_success(self, executor, executor_mod):
        """state_init creates project and parses project_id from stdout."""
        with patch.object(executor_mod, "_run_script", return_value=(0, "pro_abc123\n", "")):
            result = executor.state_init("测试项目", "项目描述")
            assert result is True
            assert executor.project_id == "pro_abc123"

    def test_script_failure(self, executor, executor_mod):
        """state_init returns False when init script fails."""
        with patch.object(executor_mod, "_run_script", return_value=(1, "", "init failed")):
            result = executor.state_init("测试项目", "项目描述")
            assert result is False

    def test_invalid_project_id(self, executor, executor_mod):
        """state_init fails when stdout doesn't contain a valid pro_ ID."""
        with patch.object(executor_mod, "_run_script", return_value=(0, "invalid", "")):
            result = executor.state_init("测试项目", "项目描述")
            assert result is False


# ============================================================================
# State: TEAM_CONFIG
# ============================================================================


class TestStateTeamConfig:
    """Test TEAM_CONFIG state — team configuration."""

    def test_success(self, executor, executor_mod, mock_home, sample_task_data):
        """state_team_config reads response file and validates team list."""
        executor_mod._write_task_data(executor.project_id, sample_task_data)

        resp_dir = mock_home / ".openclaw" / "workspace-main" / ".response"
        resp_file = resp_dir / f"{executor.project_id}_team_config.response"
        resp_file.write_text(json.dumps({
            "agents": ["researcher", "developer", "tester"],
        }))

        with (
            patch.object(executor_mod, "_run_script", return_value=(0, "idle", "")),
            patch.object(executor_mod, "_notify_agent", return_value=True),
        ):
            result = executor.state_team_config()
            assert result is True
            assert executor.team == ["researcher", "developer", "tester"]

    def test_timeout(self, executor, executor_mod, mock_home, sample_task_data):
        """state_team_config returns False when no response file appears."""
        executor_mod._write_task_data(executor.project_id, sample_task_data)

        with (
            patch.object(executor_mod, "_notify_agent", return_value=True),
            patch.object(executor_mod, "_run_script", return_value=(0, "idle", "")),
            patch.object(executor_mod, "time") as mock_time,
        ):
            # Make time.time() return values that expire the deadline immediately
            mock_time.time.return_value = 100.0
            mock_time.sleep.return_value = None
            # The deadline at start is time.time() + TEAM_CONFIG_TIMEOUT
            # If TEAM_CONFIG_TIMEOUT=600, deadline = 700
            # Make next time.time() call return > deadline
            mock_time.time.side_effect = [100.0, 999.0, 999.0]
            result = executor.state_team_config()
            assert result is False


# ============================================================================
# State: TASK_PLAN
# ============================================================================


class TestStateTaskPlan:
    """Test TASK_PLAN state — task planning."""

    def test_success(self, executor_with_project, executor_mod, mock_home):
        """state_task_plan reads task plan from Agent response."""
        executor = executor_with_project
        resp_dir = mock_home / ".openclaw" / "workspace-main" / ".response"
        resp_file = resp_dir / f"{executor.project_id}_task_plan.response"
        resp_file.write_text(json.dumps({
            "tasks": [
                {"id": "task_001", "name": "调研", "agent": "researcher",
                 "description": "调研需求", "dependencies": []},
                {"id": "task_002", "name": "开发", "agent": "developer",
                 "description": "开发功能", "dependencies": ["task_001"]},
            ],
        }))

        with patch.object(executor_mod, "_notify_agent", return_value=True):
            result = executor.state_task_plan()
            assert result is True
            assert len(executor.tasks) >= 2

    def test_invalid_plan(self, executor_with_project, executor_mod, mock_home):
        """state_task_plan fails when plan has invalid structure."""
        executor = executor_with_project
        resp_dir = mock_home / ".openclaw" / "workspace-main" / ".response"
        resp_file = resp_dir / f"{executor.project_id}_task_plan.response"
        resp_file.write_text(json.dumps({"invalid": "format"}))

        with patch.object(executor_mod, "_notify_agent", return_value=True):
            result = executor.state_task_plan()
            assert result is False


# ============================================================================
# State: ADD_TASKS
# ============================================================================


class TestStateAddTasks:
    """Test ADD_TASKS state — persist tasks to project-data."""

    def test_success(self, executor_with_project, executor_mod):
        """state_add_tasks calls project-data for tasks and confirms."""
        executor = executor_with_project
        executor.tasks = [
            {"id": "task_001", "name": "调研", "agent": "researcher",
             "description": "desc", "dependencies": []},
        ]

        with patch.object(executor_mod, "_run_script", return_value=(0, "ok", "")):
            result = executor.state_add_tasks()
            assert result is True


# ============================================================================
# State: DISPATCH_LOOP
# ============================================================================


class TestStateDispatchLoop:
    """Test DISPATCH_LOOP state — task scheduling and execution."""

    def test_no_tasks_remaining(self, executor_with_project, executor_mod, mock_home):
        """state_dispatch_loop returns True when queue has no more tasks."""
        executor = executor_with_project
        executor_mod._write_task_data(executor.project_id, {
            "project": {"id": "pro_test_001", "status": "active"},
            "tasks": [],
        })

        calls = {"count": 0}

        def fake_run(script, *args, **_kw):
            calls["count"] += 1
            # Determine what the script is by looking at the full path
            script_str = str(script)

            if "task_queue.py" in script_str:
                cmd = args[0] if len(args) > 0 else ""
                if cmd == "status":
                    return (0, "idle", "")
                if cmd == "next":
                    return (0, "none", "")
            return (0, "", "")

        with patch.object(executor_mod, "_run_script", side_effect=fake_run):
            result = executor.state_dispatch_loop()
            assert result is True

    def test_queue_running(self, executor_with_project, executor_mod):
        """state_dispatch_loop waits when queue status is 'running:task_id',
        then after idle and no more tasks, returns True."""
        executor = executor_with_project
        call_count = [0]

        def fake_run(script, *args, **_kw):
            call_count[0] += 1
            script_str = str(script)
            if "task_queue.py" in script_str:
                cmd = args[0] if len(args) > 0 else ""
                if cmd == "status":
                    # First call: running, subsequent calls: idle
                    if call_count[0] <= 1:
                        return (0, "running:task_001", "")
                    return (0, "idle", "")
                if cmd == "next":
                    # After running wait, no more tasks
                    return (0, "none", "")
            return (0, "", "")

        with (
            patch.object(executor_mod, "_run_script", side_effect=fake_run),
            patch.object(executor, "_wait_task_complete", return_value=True),
        ):
            result = executor.state_dispatch_loop()
            assert result is True

    def test_queue_error(self, executor_with_project, executor_mod):
        """state_dispatch_loop returns False on queue status failure."""
        executor = executor_with_project
        with patch.object(executor_mod, "_run_script", return_value=(1, "", "queue error")):
            result = executor.state_dispatch_loop()
            assert result is False

    def test_evaluate_and_execute(self, executor_with_project, executor_mod, mock_home):
        """state_dispatch_loop evaluates task and dispatches to agent."""
        executor = executor_with_project
        executor.tasks = [
            {"id": "task_001", "name": "调研", "agent": "researcher",
             "status": "pending", "dependencies": []},
        ]

        # Write task_data.json so task info can be read
        executor_mod._write_task_data(executor.project_id, {
            "project": {"id": "pro_test_001", "status": "active"},
            "tasks": executor.tasks,
        })

        task_dispatched = [False]

        def fake_run(script, *args, **_kw):
            script_str = str(script)
            if "task_queue.py" in script_str:
                cmd = args[0] if len(args) > 0 else ""
                if cmd == "status":
                    return (0, "idle", "")
                if cmd == "next":
                    if task_dispatched[0]:
                        return (0, "none", "")
                    task_dispatched[0] = True
                    return (0, "task_001", "")
            return (0, "", "")

        with (
            patch.object(executor_mod, "_run_script", side_effect=fake_run),
            patch.object(executor, "state_evaluate_task",
                         return_value={"should_split": False}),
            patch.object(executor, "state_execute_task", return_value=True),
            patch.object(executor_mod, "_notify_agent", return_value=True),
            patch.object(executor, "_run_cleanup"),
        ):
            result = executor.state_dispatch_loop()
            assert result is True


# ============================================================================
# State: COMPLETE
# ============================================================================


class TestStateComplete:
    """Test COMPLETE state — project completion."""

    def test_success(self, executor_with_project, executor_mod):
        """state_complete updates project status and sends notification."""
        executor = executor_with_project
        with patch.object(executor_mod, "_run_script", return_value=(0, "ok", "")):
            result = executor.state_complete()
            assert result is True

    def test_script_failure(self, executor_with_project, executor_mod):
        """state_complete handles script failure gracefully."""
        executor = executor_with_project
        with patch.object(executor_mod, "_run_script", return_value=(1, "", "complete error")):
            result = executor.state_complete()
            assert result is True  # complete failure should not fail the whole run


# ============================================================================
# Run method
# ============================================================================


class TestRun:
    """Test run() and run_from_state()."""

    def test_full_run_success(self, executor, executor_mod):
        """run() goes through all 6 states successfully."""
        with (
            patch.object(executor, "state_init", return_value=True),
            patch.object(executor, "state_team_config", return_value=True),
            patch.object(executor, "state_task_plan", return_value=True),
            patch.object(executor, "state_add_tasks", return_value=True),
            patch.object(executor, "state_dispatch_loop", return_value=True),
            patch.object(executor, "state_complete", return_value=True),
        ):
            result = executor.run("测试项目", "完整项目描述")
            assert result is True

    def test_run_fails_at_init(self, executor, executor_mod):
        """run() returns False early if INIT fails."""
        with patch.object(executor, "state_init", return_value=False):
            result = executor.run("项目", "描述")
            assert result is False

    def test_run_fails_at_dispatch(self, executor, executor_mod):
        """run() returns False if DISPATCH_LOOP fails."""
        with (
            patch.object(executor, "state_init", return_value=True),
            patch.object(executor, "state_team_config", return_value=True),
            patch.object(executor, "state_task_plan", return_value=True),
            patch.object(executor, "state_add_tasks", return_value=True),
            patch.object(executor, "state_dispatch_loop", return_value=False),
        ):
            result = executor.run("项目", "描述")
            assert result is False

    def test_run_from_state_dispatch(self, executor_with_project, executor_mod):
        """run_from_state starts from DISPATCH_LOOP."""
        executor = executor_with_project
        with (
            patch.object(executor, "state_dispatch_loop", return_value=True),
            patch.object(executor, "state_complete", return_value=True),
        ):
            result = executor.run_from_state("dispatch_loop")
            assert result is True

    def test_run_from_state_unknown(self, executor, executor_mod):
        """run_from_state returns False for unknown state name."""
        result = executor.run_from_state("nonexistent")
        assert result is False

    def test_run_from_state_complete_only(self, executor_with_project, executor_mod):
        """run_from_state starts from COMPLETE (skipping dispatch)."""
        executor = executor_with_project
        with patch.object(executor, "state_complete", return_value=True):
            result = executor.run_from_state("complete")
            assert result is True


# ============================================================================
# Try Resume
# ============================================================================


class TestTryResume:
    """Test try_resume() — project recovery after interruption."""

    def test_resume_found(self, executor, executor_mod, mock_home, sample_task_data):
        """try_resume finds project by name and resets in_progress tasks."""
        data = sample_task_data
        data["project"]["name"] = "测试项目"
        for task in data["tasks"]:
            task["status"] = "in_progress"

        proj_dir = mock_home / ".openclaw" / "tasks" / "projects" / "pro_test_001"
        proj_dir.mkdir(parents=True, exist_ok=True)
        executor_mod._write_task_data("pro_test_001", data)

        with patch.object(executor_mod, "_run_script", return_value=(0, "", "")):
            result = executor.try_resume("测试项目")
            assert result is True
            assert executor.project_id == "pro_test_001"

            # Verify tasks were reset to pending
            restored = executor_mod._read_task_data("pro_test_001")
            for task in restored["tasks"]:
                assert task["status"] == "pending"

    def test_resume_not_found(self, executor, executor_mod, mock_home):
        """try_resume returns False when project name doesn't match."""
        result = executor.try_resume("不存在的项目")
        assert result is False

    def test_resume_empty_directory(self, executor, executor_mod, mock_home):
        """try_resume returns False when no projects directory exists."""
        result = executor.try_resume("测试")
        assert result is False

# ============================================================================
# State: Quality Gate (added in optimization pass)
# ============================================================================


class TestStateQualityGate:
    """Test state_quality_gate — deliverable validation rules."""

    def test_quality_gate_passed(self, executor, executor_mod):
        """state_quality_gate returns True when gate passes."""
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock_gate:
            mock_gate.return_value.passed = True
            mock_gate.return_value.skipped = False
            result = executor.state_quality_gate("task_001", "code-deliverable", "/path.md")
            assert result is True

    def test_quality_gate_skipped(self, executor, executor_mod):
        """state_quality_gate returns True when gate is skipped (no standard page)."""
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock_gate:
            mock_gate.return_value.skipped = True
            mock_gate.return_value.passed = True
            result = executor.state_quality_gate("task_001", "code-deliverable", "/path.md")
            assert result is True

    def test_quality_gate_failed_then_retry(self, executor, executor_mod):
        """state_quality_gate returns False on failure, decrements retry."""
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock_gate:
            mock_gate.return_value.passed = False
            mock_gate.return_value.skipped = False
            mock_gate.return_value.failures = []
            mock_gate.return_value.feedback = "字数不足"
            with patch.object(executor_mod, "_update_task_via_cli"):
                with patch.object(executor_mod, "_notify_task_event"):
                    result = executor.state_quality_gate("task_001", "code-deliverable", "/path.md")
                    assert result is False
                    assert executor.quality_gate_retries.get("task_001") == 1

    def test_quality_gate_retries_exhausted(self, executor, executor_mod):
        """state_quality_gate returns False when retries exhausted (max 3)."""
        executor.project_id = "pro_test_001"
        executor.quality_gate_retries["task_001"] = 3
        with patch.object(executor_mod, "run_quality_gate") as mock_gate:
            mock_gate.return_value.passed = False
            result = executor.state_quality_gate("task_001", "code-deliverable", "/path.md")
            assert result is False


# ============================================================================
# State: Cross Review (added in optimization pass)
# ============================================================================


class TestStateReview:
    """Test state_review — cross-review flow."""

    def test_review_passed(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock_r:
            mock_r.return_value.passed = True
            assert executor.state_review("task_001", "tester", "/p.md", "s") is True

    def test_review_timed_out(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock_r:
            mock_r.return_value.passed = False
            mock_r.return_value.timed_out = True
            with patch.object(executor_mod, "_read_task_data") as mock_rd:
                mock_rd.return_value = {"tasks": [{"id": "task_001", "status": "x"}]}
                with patch.object(executor_mod, "_write_task_data"):
                    assert executor.state_review("task_001", "tester", "/p.md", "s") is True

    def test_review_skipped(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock_r:
            mock_r.return_value.skipped = True
            mock_r.return_value.passed = True
            assert executor.state_review("task_001", "", "/p.md", "s") is True

    def test_review_failed(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock_r:
            mock_r.return_value.passed = False
            mock_r.return_value.timed_out = False
            mock_r.return_value.skipped = False
            with patch.object(executor_mod, "_update_task_via_cli"):
                assert executor.state_review("task_001", "tester", "/p.md", "s") is False

# ============================================================================
# State: Quality Gate (added in optimization pass)
# ============================================================================


class TestStateQualityGate:
    """Test state_quality_gate — deliverable validation rules."""

    def test_quality_gate_passed(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock:
            mock.return_value.passed = True
            mock.return_value.skipped = False
            assert executor.state_quality_gate("t1", "c", "/p.md") is True

    def test_quality_gate_skipped(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock:
            mock.return_value.skipped = True
            mock.return_value.passed = True
            assert executor.state_quality_gate("t1", "c", "/p.md") is True

    def test_quality_gate_failed_then_retry(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_quality_gate") as mock:
            mock.return_value.passed = False
            mock.return_value.skipped = False
            mock.return_value.feedback = "bad"
            mock.return_value.failures = []
            with patch.object(executor, "_update_task_via_cli"):
                with patch.object(executor, "_notify_task_event"):
                    assert executor.state_quality_gate("t1", "c", "/p.md") is False
                    assert executor.quality_gate_retries.get("t1") == 1

    def test_quality_gate_retries_exhausted(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        executor.quality_gate_retries["t1"] = 3
        with patch.object(executor_mod, "run_quality_gate") as mock:
            mock.return_value.passed = False
            assert executor.state_quality_gate("t1", "c", "/p.md") is False


# ============================================================================
# State: Cross Review (added in optimization pass)
# ============================================================================


class TestStateReview:
    """Test state_review — cross-review flow."""

    def test_review_passed(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock:
            mock.return_value.passed = True
            assert executor.state_review("t1", "tester", "/p.md", "s") is True

    def test_review_timed_out(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock:
            mock.return_value.passed = False
            mock.return_value.timed_out = True
            mock.return_value.skipped = False
            with patch.object(executor_mod, "_read_task_data") as rd:
                rd.return_value = {"tasks": [{"id": "t1", "status": "x"}]}
                with patch.object(executor_mod, "_write_task_data"):
                    assert executor.state_review("t1", "tester", "/p.md", "s") is True

    def test_review_skipped(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock:
            mock.return_value.skipped = True
            mock.return_value.passed = True
            assert executor.state_review("t1", "", "/p.md", "s") is True

    def test_review_failed(self, executor, executor_mod):
        executor.project_id = "pro_test_001"
        with patch.object(executor_mod, "run_cross_review") as mock:
            mock.return_value.passed = False
            mock.return_value.timed_out = False
            mock.return_value.skipped = False
            assert executor.state_review("t1", "tester", "/p.md", "s") is False
