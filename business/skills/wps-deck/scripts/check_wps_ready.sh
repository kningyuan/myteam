#!/usr/bin/env bash
# WPS 本地服务 (58890) + 加载项探活
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
NODE="${NODE:-node}"
[ -x "$ROOT/venv/bin/node" ] && NODE="$ROOT/venv/bin/node"

_wps_installed() {
  case "$(uname -s)" in
    Darwin)
      [ -d "/Applications/wpsoffice.app" ] || \
      [ -d "/Applications/WPS Office.app" ] || \
      [ -d "/Applications/WPSOffice.app" ]
      ;;
    *)
      command -v wps >/dev/null 2>&1
      ;;
  esac
}

echo "=== wps-deck: 环境检查 ==="

if ! _wps_installed; then
  echo "FAIL: 未检测到 WPS Office" >&2
  exit 1
fi
echo "OK   WPS 已安装"

JSADDONS="$HOME/Library/Containers/com.kingsoft.wpsoffice.mac/Data/.kingsoft/wps/jsaddons/publish.xml"
if [ -f "$JSADDONS" ] && grep -q "myteam-wps-deck" "$JSADDONS" 2>/dev/null; then
  echo "OK   加载项已在 publish.xml 注册"
else
  echo "WARN: 加载项未安装 → bash business/skills/wps-deck/scripts/install_addin_mac.sh" >&2
  exit 2
fi

if [ ! -f "$SCRIPT_DIR/../node_modules/wpsjs-rpc-sdk-new/wpsjsrpcsdk.js" ]; then
  echo "WARN: 缺少 npm 依赖 → cd business/skills/wps-deck && npm install" >&2
  exit 2
fi

if "$NODE" "$SCRIPT_DIR/wps_call.js" health >/tmp/wps_health.json 2>/tmp/wps_health.err; then
  echo "OK   WPS 本地服务 58890 可连通"
  cat /tmp/wps_health.json 2>/dev/null || true
  echo "wps-deck: READY（可直接 WpsInvoke 调 JSAPI）"
  exit 0
fi

echo "FAIL: WPS 本地服务未响应（需启动 WPS 并重启后重试）" >&2
cat /tmp/wps_health.err 2>/dev/null || true
exit 2
