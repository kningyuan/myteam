#!/bin/bash
# submit 前：登录态 + 交付物静态校验（须先完成 publish_zhihu.sh 并写好交付物）
# 用法: run_publish_preflight.sh <deliverable.md>
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DELIV="${1:?需要交付物路径}"

echo "=== 1/2 知乎登录态 ==="
bash "$SCRIPT_DIR/check_zhihu_login.sh" || exit $?

echo ""
echo "=== 2/2 交付物静态校验 ==="
python3 "$SCRIPT_DIR/verify_publish_deliverable.py" "$DELIV" || exit $?

echo ""
echo "OK: submit preflight 通过"
