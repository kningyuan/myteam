#!/usr/bin/env python3
"""REG-PLATFORM-V3-E2E-BASELINE — Workflow v3 修正项 1。

编排内核 E2E 基线：Process → AgentPort → Gate → Store 核心路径（快速 pytest，无真实 CLI）。

双跑要求：同一 pytest 命令连续执行两次，exit code 与 pass 计数必须一致。

用法:
    MYTEAM_ROOT=$PWD PYTHONPATH=$PWD/backend \\
        python3 scripts/regression/reg_platform_v3_e2e_baseline.py

等价 pytest:
    pytest backend/common/tests/test_platform_e2e_baseline.py \\
          backend/common/tests/test_run_kernel.py -q
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
REG_ID = "REG-PLATFORM-V3-E2E-BASELINE"

BASELINE_TEST_PATHS = (
    "backend/common/tests/test_platform_e2e_baseline.py",
    "backend/common/tests/test_run_kernel.py",
)

_PASS_RE = re.compile(r"(\d+)\s+passed")
_FAIL_RE = re.compile(r"(\d+)\s+failed")
_ERROR_RE = re.compile(r"(\d+)\s+error")
_SKIP_RE = re.compile(r"(\d+)\s+skipped")


def _repo_root(repo_root: Path | None = None) -> Path:
    return repo_root or REPO


def _python_bin(repo_root: Path) -> str:
    venv_py = repo_root / "venv" / "bin" / "python3"
    return str(venv_py if venv_py.is_file() else sys.executable)


def parse_pytest_q_output(text: str) -> dict[str, int]:
    """Parse pytest -q terminal summary for pass/fail/error/skip counts."""
    passed = failed = errors = skipped = 0
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        if m := _PASS_RE.search(line):
            passed = int(m.group(1))
        if m := _FAIL_RE.search(line):
            failed = int(m.group(1))
        if m := _ERROR_RE.search(line):
            errors = int(m.group(1))
        if m := _SKIP_RE.search(line):
            skipped = int(m.group(1))
        if passed or failed or errors:
            break
    return {
        "passed": passed,
        "failed": failed + errors,
        "skipped": skipped,
    }


class _PytestSummaryPlugin:
    """Collect pass/fail counts when invoking pytest.main in-process."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0

    def pytest_terminal_summary(self, terminalreporter, exitstatus) -> None:  # noqa: ANN001
        stats = terminalreporter.stats
        self.passed = len(stats.get("passed", []))
        self.failed = len(stats.get("failed", []))
        self.skipped = len(stats.get("skipped", []))
        self.errors = len(stats.get("error", []))


def run_baseline_once_subprocess(repo_root: Path | None = None) -> dict[str, Any]:
    """Run baseline pytest suite once via subprocess."""
    repo = _repo_root(repo_root)
    cmd = [
        _python_bin(repo),
        "-m",
        "pytest",
        *BASELINE_TEST_PATHS,
        "-q",
        "--tb=no",
    ]
    env = {**os.environ, "PYTHONPATH": str(repo / "backend")}
    proc = subprocess.run(cmd, cwd=str(repo), env=env, capture_output=True, text=True)
    counts = parse_pytest_q_output((proc.stdout or "") + "\n" + (proc.stderr or ""))
    return {
        "exit_code": proc.returncode,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_baseline_once_inprocess(repo_root: Path | None = None) -> dict[str, Any]:
    """Run baseline pytest suite once in-process (fast path for unit tests)."""
    import pytest

    repo = _repo_root(repo_root)
    tests = [str(repo / rel) for rel in BASELINE_TEST_PATHS]
    plugin = _PytestSummaryPlugin()
    exit_code = pytest.main(["-q", "--tb=no", *tests], plugins=[plugin])
    return {
        "exit_code": exit_code,
        "passed": plugin.passed,
        "failed": plugin.failed + plugin.errors,
        "skipped": plugin.skipped,
    }


def runs_are_consistent(run_a: dict[str, Any], run_b: dict[str, Any]) -> bool:
    """True when exit code and pass/fail counts match between two runs."""
    keys = ("exit_code", "passed", "failed")
    return all(run_a.get(k) == run_b.get(k) for k in keys)


def execute_double_run(
    *,
    repo_root: Path | None = None,
    use_subprocess: bool = True,
) -> dict[str, Any]:
    """Run baseline twice and compare exit codes + pass counts."""
    runner = run_baseline_once_subprocess if use_subprocess else run_baseline_once_inprocess
    run1 = runner(repo_root=repo_root)
    run2 = runner(repo_root=repo_root)
    consistent = runs_are_consistent(run1, run2)
    all_pass = (
        run1.get("exit_code") == 0
        and run1.get("failed", 0) == 0
        and run2.get("exit_code") == 0
        and run2.get("failed", 0) == 0
    )
    ok = consistent and all_pass
    return {
        "reg_id": REG_ID,
        "baseline_tests": list(BASELINE_TEST_PATHS),
        "run1": {
            "exit_code": run1.get("exit_code"),
            "passed": run1.get("passed"),
            "failed": run1.get("failed"),
            "skipped": run1.get("skipped", 0),
        },
        "run2": {
            "exit_code": run2.get("exit_code"),
            "passed": run2.get("passed"),
            "failed": run2.get("failed"),
            "skipped": run2.get("skipped", 0),
        },
        "consistent": consistent,
        "pass": ok,
    }


def main() -> int:
    print(f"=== {REG_ID}（Workflow v3 修正项 1 · 双跑 E2E 基线）===")
    result = execute_double_run(use_subprocess=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        if not result["consistent"]:
            print(
                "FAIL: run1 vs run2 mismatch — "
                f"exit/run1={result['run1']} run2={result['run2']}",
                file=sys.stderr,
            )
        else:
            print(
                "FAIL: baseline tests did not全部通过 — "
                f"run1={result['run1']} run2={result['run2']}",
                file=sys.stderr,
            )
        return 1
    print(f"{REG_ID}: PASS (双跑一致, {result['run1']['passed']} passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
