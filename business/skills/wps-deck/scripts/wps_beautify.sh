#!/usr/bin/env bash
# 直接通过 WPS 加载项 JSAPI 美化 pptx；失败则 beautify_deck.py 兜底
set -uo pipefail

PPTX="${1:?用法: wps_beautify.sh <deck.pptx>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
PY="${ROOT}/venv/bin/python3"
[ -x "$PY" ] || PY=python3
NODE="${NODE:-node}"

PPTX_ABS="$(cd "$(dirname "$PPTX")" && pwd)/$(basename "$PPTX")"
DIR="$(dirname "$PPTX_ABS")"
cp -f "$PPTX_ABS" "$DIR/deck-before-wps.pptx"

PARAM="$( "$PY" -c "import json; print(json.dumps({'inputPath':'$PPTX_ABS','outputPath':'$PPTX_ABS','themeIndex':1}))" )"

echo "=== wps_beautify: 尝试 WPS 直连 (WpsInvoke → beautifyDeck) ==="
if bash "$SCRIPT_DIR/check_wps_ready.sh" 2>/dev/null; then
  if "$NODE" "$SCRIPT_DIR/wps_call.js" beautifyDeck "$PARAM"; then
    echo "OK: WPS JSAPI 美化完成 → $PPTX_ABS"
    exit 0
  fi
  echo "WARN: WPS beautifyDeck 调用失败，fallback python"
else
  echo "WARN: WPS 未就绪（加载项/58890），fallback python"
  echo "      一次性安装: bash business/skills/wps-deck/scripts/install_addin_mac.sh"
fi

"$PY" "$SCRIPT_DIR/beautify_deck.py" "$PPTX_ABS" -o "$PPTX_ABS"
if [ -d "/Applications/wpsoffice.app" ]; then
  open -a wpsoffice "$PPTX_ABS" 2>/dev/null || true
fi
echo "wps_beautify: DONE (python fallback) → $PPTX_ABS"
