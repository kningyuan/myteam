#!/usr/bin/env bash
# 安装 myteam-wps-deck 加载项到 Mac WPS jsaddons（一次性）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PUBLISH_SRC="$SCRIPT_DIR/../addin/publish"
JSADDONS="$HOME/Library/Containers/com.kingsoft.wpsoffice.mac/Data/.kingsoft/wps/jsaddons"
ADDIN_NAME="${WPS_ADDIN_NAME:-myteam-wps-deck}"
VERSION="1.0.0"
TARGET="$JSADDONS/${ADDIN_NAME}_${VERSION}"

if [ ! -d "$PUBLISH_SRC" ]; then
  echo "ERROR: 找不到 $PUBLISH_SRC" >&2
  exit 1
fi

# wpsjs debug 要求 addin/ 根目录有 index.html（非仅 publish/ 子目录）
ADDIN_ROOT="$SCRIPT_DIR/../addin"
cp "$PUBLISH_SRC/index.html" "$ADDIN_ROOT/index.html"
cp "$PUBLISH_SRC/ribbon.xml" "$ADDIN_ROOT/ribbon.xml"
mkdir -p "$ADDIN_ROOT/js"
cp "$PUBLISH_SRC/js/functions.js" "$ADDIN_ROOT/js/functions.js"

mkdir -p "$JSADDONS"
rm -rf "$TARGET"
cp -R "$PUBLISH_SRC" "$TARGET"

# 本地 file:// URL（WPS Mac 离线加载项）
PUBLISH_URL="file://${TARGET}/"

PUBLISH_XML="$JSADDONS/publish.xml"
DEBUG_PORT="${WPS_DEBUG_PORT:-3889}"
PLUGIN_LINE="<jspluginonline name=\"${ADDIN_NAME}\" type=\"wpp\" url=\"http://127.0.0.1:${DEBUG_PORT}/\" debug=\"\" enable=\"enable_dev\" install=\"${ADDIN_NAME}\"/>"

_write_publish() {
  cat > "$PUBLISH_XML" <<EOF
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<jsplugins>
  ${PLUGIN_LINE}
</jsplugins>
EOF
}

if [ -f "$PUBLISH_XML" ] && grep -q "name=\"${ADDIN_NAME}\"" "$PUBLISH_XML" 2>/dev/null; then
  # 强制同步 type=wpp 与 debug 端口（WPS 可能改写为 wps/3890）
  if grep -q 'type="wpp"' "$PUBLISH_XML" && grep -q "127.0.0.1:${DEBUG_PORT}/" "$PUBLISH_XML"; then
    echo "OK: publish.xml 已含 ${ADDIN_NAME} (wpp @ ${DEBUG_PORT})"
  else
    _write_publish
    echo "OK: 已更新 publish.xml → wpp @ ${DEBUG_PORT}"
  fi
else
  if [ -f "$PUBLISH_XML" ]; then
    sed -i '' "s|</jsplugins>|  ${PLUGIN_LINE}\n</jsplugins>|" "$PUBLISH_XML" 2>/dev/null || true
  fi
  if ! grep -q "name=\"${ADDIN_NAME}\"" "$PUBLISH_XML" 2>/dev/null; then
    _write_publish
  fi
  echo "OK: 已写入 $PUBLISH_XML"
fi

echo ""
echo "=== 安装完成 ==="
echo "  加载项目录: $TARGET"
echo "  下一步:"
echo "    1) 完全退出并重启 WPS Office"
echo "    2) 终端 A: bash business/skills/wps-deck/scripts/start_wps_debug.sh"
echo "    3) 完全退出并重启 WPS Office"
echo "    4) node business/skills/wps-deck/scripts/wps_call.js health"
