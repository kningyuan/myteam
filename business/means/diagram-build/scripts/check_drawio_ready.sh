#!/usr/bin/env bash
# 探活 draw.io 桌面 CLI
set -uo pipefail

_find_drawio() {
  for c in "${DRAWIO_BIN:-}" drawio draw.io "/Applications/draw.io.app/Contents/MacOS/draw.io"; do
    [ -n "$c" ] || continue
    if [ -x "$c" ] 2>/dev/null || command -v "$c" >/dev/null 2>&1; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

echo "=== diagram-build: 环境检查 ==="
CLI="$(_find_drawio)" || { echo "FAIL: 未找到 draw.io CLI（brew install --cask drawio）" >&2; exit 1; }
ver="$("$CLI" --version 2>&1 | head -1)" || true
echo "OK   draw.io CLI: $CLI ($ver)"
echo "diagram-build: READY"
exit 0
