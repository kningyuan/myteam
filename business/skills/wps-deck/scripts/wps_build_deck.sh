#!/usr/bin/env bash
# WPS 路径生成 deck.pptx — 须 check_wps_ready exit 0
set -uo pipefail

BRIEF="${1:?用法: wps_build_deck.sh <brief.yaml> <output.pptx>}"
OUT="${2:?用法: wps_build_deck.sh <brief.yaml> <output.pptx>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/check_wps_ready.sh" || exit 1
bash "$SCRIPT_DIR/wps_invoke.sh" "$BRIEF" "$OUT"
