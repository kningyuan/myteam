#!/usr/bin/env bash
# 用本机 draw.io CLI 导出图表（Mac 默认路径）
set -euo pipefail

INPUT="${1:?用法: render_drawio.sh <file.drawio> [output.png]}"
OUT="${2:-}"
FORMAT="${DRAWIO_FORMAT:-png}"

if [ -z "$OUT" ]; then
  base="${INPUT%.*}"
  OUT="${base}.${FORMAT}"
fi

DRAWIO="${DRAWIO_BIN:-}"
if [ -z "$DRAWIO" ]; then
  for c in drawio draw.io "/Applications/draw.io.app/Contents/MacOS/draw.io"; do
    if [ -x "$c" ] 2>/dev/null || command -v "$c" >/dev/null 2>&1; then
      DRAWIO="$c"
      break
    fi
  done
fi
[ -n "$DRAWIO" ] || { echo "ERROR: 未找到 draw.io CLI" >&2; exit 1; }
[ -f "$INPUT" ] || { echo "ERROR: 找不到 $INPUT" >&2; exit 1; }

mkdir -p "$(dirname "$OUT")"
echo "=== render_drawio: $INPUT → $OUT ($FORMAT) ==="
"$DRAWIO" -x -f "$FORMAT" -e -o "$OUT" "$INPUT"
echo "OK: $OUT"
