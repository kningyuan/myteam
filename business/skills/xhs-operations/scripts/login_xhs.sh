#!/bin/bash
# 有头模式登录小红书创作者中心并导出 cookie 到 ~/.gstack/xhs-cookies.json
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../zhihu-operations/scripts/_zhihu_browse.sh
source "$SCRIPT_DIR/../../zhihu-operations/scripts/_zhihu_browse.sh"

COOKIE_OUT="${1:-$HOME/.gstack/xhs-cookies.json}"
mkdir -p "$(dirname "$COOKIE_OUT")"

_zhihu_find_browse || exit 1

echo "=== 打开可见浏览器，请在页面中完成小红书登录 ==="
echo "    登录成功后脚本将导出 cookie 到: $COOKIE_OUT"
"$B" connect https://creator.xiaohongshu.com/login >/dev/null 2>&1 || \
  "$B" connect https://www.xiaohongshu.com >/dev/null 2>&1

echo "=== 等待创作者发布页可访问（最多 120s）==="
for _ in $(seq 1 24); do
  "$B" goto https://creator.xiaohongshu.com/publish/publish >/dev/null 2>&1
  sleep 5
  URL_NOW="$("$B" url 2>/dev/null || true)"
  case "$URL_NOW" in
    *login*|*signin*|*passport*) ;;
    *captcha*|*verify*|*unhuman*) exit 4 ;;
    *)
      echo "[login] 登录态正常: $URL_NOW"
      _zhihu_export_cookies "$COOKIE_OUT"
      if [ -s "$COOKIE_OUT" ] && [ "$(wc -c < "$COOKIE_OUT" | tr -d ' ')" -gt 4 ]; then
        echo "OK: cookie 已保存到 $COOKIE_OUT"
        exit 0
      fi
      echo "WARN: cookies 导出为空" >&2
      exit 1
      ;;
  esac
done

echo "ERROR: 超时未检测到登录，请重试" >&2
exit 2
