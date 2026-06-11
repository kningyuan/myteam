#!/usr/bin/env bash
# 配置贯通快速回归 — developer / frontend 改代码后执行。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend"

PY="${ROOT}/venv/bin/python"
[ -x "$PY" ] || PY=python3

echo "=== linkage quick tests ==="
"$PY" -m pytest \
  backend/common/tests/test_ui_config_linkage.py \
  backend/common/tests/test_settings_config_contract.py \
  -q

echo "=== verify_config_contract (static) ==="
"$PY" business/skills/myteam-config-linkage/scripts/verify_config_contract.py

echo "LINKAGE_QUICK: PASS"
