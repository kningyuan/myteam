#!/usr/bin/env python3
"""dag_dispatch 单元测试 — 纯函数调度逻辑。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.dag_dispatch import deps_block, derive_project_status  # noqa: E402
from common.process_types import TaskOutcome  # noqa: E402


def _out(tid, status, reason=""):
    return TaskOutcome(tid, status, reason)


def test_deps_block_upstream_failed():
    task = {"id": "b", "dependencies": ["a"]}
    outcomes = {"a": _out("a", "failed")}
    assert "failed" in deps_block(task, outcomes, needs_review_blocks=False)


def test_deps_block_needs_review_default_pass():
    task = {"id": "b", "dependencies": ["a"]}
    outcomes = {"a": _out("a", "needs_review")}
    assert deps_block(task, outcomes, needs_review_blocks=False) == ""


def test_deps_block_needs_review_when_blocking():
    task = {"id": "b", "dependencies": ["a"]}
    outcomes = {"a": _out("a", "needs_review")}
    assert "待评审" in deps_block(task, outcomes, needs_review_blocks=True)


def test_derive_project_status_completed():
    outcomes = {"a": _out("a", "completed"), "b": _out("b", "needs_review")}
    assert derive_project_status(outcomes) == "completed"


def test_derive_project_status_partially_failed():
    outcomes = {"a": _out("a", "completed"), "b": _out("b", "failed")}
    assert derive_project_status(outcomes) == "partially_failed"


def test_derive_project_status_all_failed():
    outcomes = {"a": _out("a", "failed"), "b": _out("b", "blocked")}
    assert derive_project_status(outcomes) == "failed"


def test_derive_project_status_cancelled_overrides():
    outcomes = {"a": _out("a", "completed")}
    assert derive_project_status(outcomes, cancelled=True) == "cancelled"


def test_derive_project_status_aborted_overrides():
    outcomes = {"a": _out("a", "completed")}
    assert derive_project_status(outcomes, aborted=True) == "aborted"


def test_derive_project_status_paused_overrides():
    outcomes = {"a": _out("a", "completed")}
    assert derive_project_status(outcomes, paused=True) == "paused"
