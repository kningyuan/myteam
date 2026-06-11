#!/usr/bin/env bash
# B 层：复制 ALL 过程模板到交付物目录（与 task_type / means 无关）
set -euo pipefail
DELIV="${1:?用法: scaffold_process.sh <交付物目录>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPL="$SCRIPT_DIR/../templates"
mkdir -p "$DELIV"
cp "$TPL/align.md" "$DELIV/align.md"
cp "$TPL/plan.md" "$DELIV/plan.md"
cp "$TPL/ledger.entry.yaml" "$DELIV/ledger.entry.yaml"
cp "$TPL/trace.manifest.yaml" "$DELIV/trace.manifest.yaml"
touch "$DELIV/verify.log"
echo "scaffold_process: OK → $DELIV"
