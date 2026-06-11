#!/usr/bin/env bash
# 启动 wpsjs 本地服务供 WPS 加载项在线模式（默认 3889，占用时自动递增）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDIN="$(cd "$SCRIPT_DIR/../addin" && pwd)"
cd "$ADDIN"
[ -f index.html ] || { echo "ERROR: 缺少 index.html，请先运行 install_addin_mac.sh"; exit 1; }

echo "=== wpsjs debug @ $ADDIN ==="
echo "请保持本终端运行；另开终端跑 wps_call / wps_beautify"
echo "启动后若端口非 3889，请: WPS_DEBUG_PORT=<port> bash scripts/install_addin_mac.sh"

npx wpsjs debug 2>&1 | while IFS= read -r line; do
  echo "$line"
  if echo "$line" | grep -qE '127\.0\.0\.1:[0-9]+'; then
    port="$(echo "$line" | sed -nE 's/.*127\.0\.0\.1:([0-9]+).*/\1/p' | head -1)"
    if [ -n "$port" ] && [ "$port" != "3889" ]; then
      echo "HINT: 检测到端口 $port → WPS_DEBUG_PORT=$port bash $SCRIPT_DIR/install_addin_mac.sh && 重启 WPS"
    fi
  fi
done
