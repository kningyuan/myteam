#!/usr/bin/env bash
# light_v1 脚手架：align + verify.log（内容型 task_type）
set -euo pipefail
DELIV="${1:?用法: scaffold_light.sh <交付物目录>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPL="$SCRIPT_DIR/../templates"
mkdir -p "$DELIV"
cp "$TPL/align.md" "$DELIV/align.md"
touch "$DELIV/verify.log"
echo "scaffold_light: OK → $DELIV (align.md verify.log)"
