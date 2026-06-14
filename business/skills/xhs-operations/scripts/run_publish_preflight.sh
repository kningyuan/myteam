#!/bin/bash
# 发布 submit 前：登录态 + 交付物静态校验
set -uo pipefail
DELIV="${1:?用法: run_publish_preflight.sh <t-publish_deliverable.md>}"
ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
cd "$ROOT"

echo "=== 1. 登录态 ==="
bash business/skills/xhs-operations/scripts/check_xhs_login.sh
rc=$?
[ "$rc" -ne 0 ] && exit "$rc"

echo "=== 2. 交付物静态校验 ==="
python3 business/skills/xhs-operations/scripts/verify_publish_deliverable.py "$DELIV"
