#!/usr/bin/env bash
set -euo pipefail

# myteam 本地 CI 脚本
# 用法: scripts/test.sh [--coverage]
# 前置: MYTEAM_ROOT 已设置，venv 已创建

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MYTEAM_ROOT="$ROOT"
export PYTHONPATH="$ROOT/backend"

VENV="$ROOT/venv"
PYTHON="$VENV/bin/python3"

echo "=== myteam CI: pytest ==="
START_TS=$(date +%s)

$PYTHON -m pytest backend -q -x --tb=short 2>&1

DURATION=$(( $(date +%s) - START_TS ))
echo "=== Done in ${DURATION}s ==="
