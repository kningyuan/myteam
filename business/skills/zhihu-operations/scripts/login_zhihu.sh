#!/bin/bash
# 有头模式登录知乎并导出 cookie 到 ~/.gstack/zhihu-cookies.json
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_zhihu_browse.sh
source "$SCRIPT_DIR/_zhihu_browse.sh"

COOKIE_OUT="${1:-$HOME/.gstack/zhihu-cookies.json}"
mkdir -p "$(dirname "$COOKIE_OUT")"

_zhihu_find_browse || exit 1

echo "=== 打开可见浏览器，请在页面中完成知乎登录 ==="
echo "    登录成功后脚本将导出 cookie 到: $COOKIE_OUT"
"$B" connect https://www.zhihu.com/signin >/dev/null 2>&1 || "$B" connect https://www.zhihu.com >/dev/null 2>&1

echo "=== 等待写作页可访问（最多 120s）==="
for _ in $(seq 1 24); do
  "$B" goto https://zhuanlan.zhihu.com/write >/dev/null 2>&1
  sleep 5
  URL_NOW="$("$B" url 2>/dev/null || true)"
  if _zhihu_check_login_url "$URL_NOW"; then
    echo "[login] 登录态正常: $URL_NOW"
    _zhihu_export_cookies "$COOKIE_OUT"
    if [ -s "$COOKIE_OUT" ] && [ "$(wc -c < "$COOKIE_OUT" | tr -d ' ')" -gt 4 ]; then
      echo "OK: cookie 已保存到 $COOKIE_OUT"
      exit 0
    fi
    echo "WARN: cookies 导出为空，请确认 browse 会话已登录" >&2
    exit 1
  fi
  rc=$?
  [ "$rc" -eq 4 ] && exit 4
done

echo "ERROR: 超时未检测到登录，请重试" >&2
exit 2
