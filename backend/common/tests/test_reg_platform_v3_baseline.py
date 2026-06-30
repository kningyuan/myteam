#!/usr/bin/env python3
"""Fast in-process wrapper for reg_platform_v3_e2e_baseline logic."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "regression"))

try:  # noqa: E402
    from reg_platform_v3_e2e_baseline import (
        BASELINE_TEST_PATHS,
        execute_double_run,
        parse_pytest_q_output,
        run_baseline_once_inprocess,
        runs_are_consistent,
    )
except ImportError:
    pytest.skip(
        "scripts/regression/reg_platform_v3_e2e_baseline.py 模块缺失（slim-core 分支已移除）",
        allow_module_level=True,
    )


def test_parse_pytest_q_output_extracts_counts():
    text = ".......                                                                  [100%]\n8 passed in 0.42s\n"
    counts = parse_pytest_q_output(text)
    assert counts["passed"] == 8
    assert counts["failed"] == 0


def test_runs_are_consistent_detects_mismatch():
    assert runs_are_consistent(
        {"exit_code": 0, "passed": 8, "failed": 0},
        {"exit_code": 0, "passed": 8, "failed": 0},
    )
    assert not runs_are_consistent(
        {"exit_code": 0, "passed": 8, "failed": 0},
        {"exit_code": 0, "passed": 7, "failed": 0},
    )


def test_baseline_tests_pass_inprocess():
    """Single in-process run — fast smoke for P1.5 baseline suite."""
    result = run_baseline_once_inprocess(repo_root=ROOT)
    assert result["exit_code"] == 0, result
    assert result["failed"] == 0, result
    # 4 tests in platform_e2e + 4 in run_kernel
    assert result["passed"] == 8, result


def test_double_run_inprocess_is_consistent():
    """In-process double run — verifies comparison logic without subprocess."""
    summary = execute_double_run(repo_root=ROOT, use_subprocess=False)
    assert summary["consistent"] is True
    assert summary["pass"] is True
    assert summary["run1"]["passed"] == summary["run2"]["passed"] == 8
