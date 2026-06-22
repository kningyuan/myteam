#!/usr/bin/env bash
# 验证测试
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
exec venv/bin/python3 -m pytest backend/common/tests/test_failure_patterns_lesson.py backend/common/tests/test_execution_harness.py backend/common/tests/test_contracts.py backend/common/tests/test_dag_dispatch.py -q