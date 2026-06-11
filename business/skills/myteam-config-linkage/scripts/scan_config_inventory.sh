#!/usr/bin/env bash
# 输出设置页 UI 控件与 settings.js 引用 — research 盘点辅助。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
SETTINGS="${ROOT}/frontend/settings.js"
HTML="${ROOT}/frontend/index.html"

echo "=== UI controls (index.html id=set-*) ==="
grep -oE 'id="set-[^"]+"' "$HTML" | sed 's/id="//;s/"$//' | sort -u | grep -vE 'set-status|set-cli-path-label|set-cli-path-hint'

echo ""
echo "=== loadSettings DOM refs ==="
grep -oE "DOM\['set-[^']+'\]" "$SETTINGS" | sort -u

echo ""
echo "=== saveSettings DOM refs ==="
awk '/async function saveSettings/,/^function /' "$SETTINGS" | grep -oE "DOM\['set-[^']+'\]" | sort -u || true

echo ""
echo "=== API endpoints in settings.js ==="
grep -E "fetch\('/api/(config|skill-config)" "$SETTINGS" || true

echo "SCAN_INVENTORY: done (human fills field_matrix template)"
