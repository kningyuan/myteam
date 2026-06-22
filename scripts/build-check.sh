#!/usr/bin/env bash
# 构建验证脚本 — myteam 是 Python 项目，无需编译
# 验证关键模块可导入
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
exec venv/bin/python3 -c "
from common.contracts import PlanResult
from common.gate import check_plan
from execution_harness.post.failure_patterns import classify_failures
from execution_harness.post.lesson import extract_lesson_from_ledger
from execution_harness.post.quality import record_quality
print('build ok')
"