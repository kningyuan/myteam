#!/bin/bash
# 仅校验知乎登录态，不发布文章。
# 退出码: 0 已登录; 2 未登录; 4 人机验证; 1 环境错误
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_zhihu_browse.sh
source "$SCRIPT_DIR/_zhihu_browse.sh"
trap '_zhihu_cleanup_cookies' EXIT

_zhihu_find_browse || exit 1
_zhihu_prepare_cookies

echo "=== 注入 cookie 并打开写作页 ==="
_zhihu_inject_cookies
"$B" goto https://zhuanlan.zhihu.com/write >/dev/null 2>&1
sleep 3
URL_NOW="$("$B" url 2>/dev/null || true)"
echo "[url] $URL_NOW"

if _zhihu_check_login_url "$URL_NOW"; then
  echo "OK: 知乎登录态正常"
  exit 0
fi
exit $?
