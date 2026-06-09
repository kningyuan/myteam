#!/usr/bin/env python3
"""R-K16：外部 recurring 触发入口测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.process import ProjectOutcome, TaskOutcome  # noqa: E402
from common.recurring_trigger import main, normalize_trigger, trigger_recurring  # noqa: E402


def test_normalize_trigger_accepts_budget_alias():
    args = normalize_trigger({
        "project_id": "p_tick",
        "goal": "持续优化",
        "budget": 1234,
    })
    assert args["project_id"] == "p_tick"
    assert args["goal"] == "持续优化"
    assert args["token_budget"] == 1234
    assert args["max_cycles"] == 1


def test_normalize_trigger_requires_project_id():
    with pytest.raises(ValueError, match="project_id"):
        normalize_trigger({"goal": "g"})


def test_trigger_recurring_calls_runner_once_with_recurring_mode():
    captured = {}

    def runner(project_id, **kwargs):
        captured["project_id"] = project_id
        captured.update(kwargs)
        return ProjectOutcome(project_id, "completed", {
            "c1_task_001": TaskOutcome("c1_task_001", "completed", "", 1),
        })

    out = trigger_recurring({"project_id": "p_tick", "goal": "g"}, runner=runner)
    assert out.status == "completed"
    assert captured["project_id"] == "p_tick"
    assert captured["mode"] == "recurring"
    assert captured["max_cycles"] == 1


def test_main_cli_dispatches(monkeypatch, capsys):
    import common.recurring_trigger as rt

    captured = {}

    def runner(project_id, **kwargs):
        captured["project_id"] = project_id
        captured.update(kwargs)
        return ProjectOutcome(project_id, "completed", {
            "c1_task_001": TaskOutcome("c1_task_001", "completed", "", 1),
        })

    monkeypatch.setattr(rt, "_default_runner", lambda: runner)
    rc = main(["--project-id", "p_cli", "--goal", "g", "--max-cycles", "2"])
    assert rc == 0
    assert captured["mode"] == "recurring"
    assert captured["max_cycles"] == 2
    assert '"status": "completed"' in capsys.readouterr().out
