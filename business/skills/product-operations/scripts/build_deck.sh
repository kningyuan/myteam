#!/usr/bin/env bash
# 统一生成 deck.pptx：优先 WPS，失败则 python-pptx 兜底
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
BRIEF="${1:?用法: build_deck.sh <deck_brief.yaml> <output.pptx>}"
OUT="${2:?用法: build_deck.sh <deck_brief.yaml> <output.pptx>}"

WPS_SCRIPT="$ROOT/business/skills/wps-deck/scripts/wps_build_deck.sh"
PY="$ROOT/venv/bin/python3"
[ -x "$PY" ] || PY=python3

mkdir -p "$(dirname "$OUT")"

echo "=== build_deck: 尝试 WPS 路径 ==="
if [ -x "$WPS_SCRIPT" ]; then
  if bash "$WPS_SCRIPT" "$BRIEF" "$OUT"; then
    echo "build_deck: OK (wps)"
    exit 0
  fi
  echo "build_deck: WPS 路径未成功，fallback python-pptx"
else
  echo "build_deck: wps-deck 脚本未就绪，直接用 python-pptx"
fi

echo "=== build_deck: python-pptx 兜底 ==="
"$PY" "$ROOT/business/skills/product-operations/scripts/build_deck.py" "$BRIEF" "$OUT"
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "build_deck: OK (fallback python-pptx)"
fi
exit "$rc"
