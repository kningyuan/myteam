#!/usr/bin/env bash
# product-operations Skill 包 smoke 测试
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
cd "$ROOT"

PY="${ROOT}/venv/bin/python3"
[ -x "$PY" ] || PY=python3

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BRIEF="$ROOT/business/skills/product-operations/fixtures/sample_deck_brief.yaml"
OUT="$TMP/deck.pptx"
DELIV="$TMP/t-deck_deliverable.md"

echo "=== product-operations smoke ==="

# 1) python 直接构建
"$PY" business/skills/product-operations/scripts/build_deck.py "$BRIEF" "$OUT"
[ -f "$OUT" ]

# 2) 统一入口（应 fallback 成功）
OUT2="$TMP/deck2.pptx"
bash business/skills/product-operations/scripts/build_deck.sh "$BRIEF" "$OUT2"
[ -f "$OUT2" ]

# 3) 交付物模板拷贝 + 校验
cp business/skills/product-operations/templates/deck_deliverable.md "$DELIV"
"$PY" business/skills/product-operations/scripts/verify_deck.py "$OUT" --deliverable "$DELIV"

# 4) WPS 探活（非阻塞）
if [ -x business/skills/wps-deck/scripts/check_wps_ready.sh ]; then
  bash business/skills/wps-deck/scripts/check_wps_ready.sh || true
fi

echo "product-operations smoke: PASS"
