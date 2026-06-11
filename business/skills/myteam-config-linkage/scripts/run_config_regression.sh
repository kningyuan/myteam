#!/usr/bin/env bash
# 配置贯通全量回归 — qa / 验收前执行；stdout 可附进交付物。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend"

PY="${ROOT}/venv/bin/python"
[ -x "$PY" ] || PY=python3

echo "=== config regression pytest ==="
"$PY" -m pytest \
  backend/common/tests/test_ui_config_linkage.py \
  backend/common/tests/test_kernel_config.py \
  backend/common/tests/test_skill_config_api.py \
  backend/common/tests/test_settings_config_contract.py \
  backend/common/tests/test_fix_be_contract.py \
  -q

echo "=== verify_config_contract (static) ==="
"$PY" business/skills/myteam-config-linkage/scripts/verify_config_contract.py

echo "CONFIG_REGRESSION: PASS"
