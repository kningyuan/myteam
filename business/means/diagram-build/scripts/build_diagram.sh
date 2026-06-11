#!/usr/bin/env bash
# 统一入口：.drawio → .png（经本机 draw.io CLI）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRAWIO="${1:?用法: build_diagram.sh <diagram.drawio> <diagram.png>}"
PNG="${2:?用法: build_diagram.sh <diagram.drawio> <diagram.png>}"

bash "$SCRIPT_DIR/check_drawio_ready.sh"
bash "$SCRIPT_DIR/render_drawio.sh" "$DRAWIO" "$PNG"
echo "build_diagram: OK → $PNG"
