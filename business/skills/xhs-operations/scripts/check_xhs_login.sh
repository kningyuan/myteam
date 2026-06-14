#!/bin/bash
# 仅校验小红书创作者登录态，不发布笔记。
# 退出码: 0 已登录; 2 未登录; 4 人机验证; 1 环境错误
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../zhihu-operations/scripts/_zhihu_browse.sh
source "$SCRIPT_DIR/../../zhihu-operations/scripts/_zhihu_browse.sh"
trap '_zhihu_cleanup_cookies' EXIT

_zhihu_find_browse || exit 1
_zhihu_prepare_cookies

COOKIE_SRC="${XHS_COOKIE_SRC:-$HOME/.gstack/xhs-cookies.json}"
if [ -f "$COOKIE_SRC" ]; then
  python3 - "$COOKIE_SRC" "$COOKIE_TMP" <<'PY'
import json, sys
src = json.load(open(sys.argv[1]))
keep = {".xiaohongshu.com", "www.xiaohongshu.com", "creator.xiaohongshu.com"}
sel = [c for c in src if any(d in c.get("domain", "") for d in keep)]
json.dump(sel, open(sys.argv[2], "w"), ensure_ascii=False)
print(f"[cookie] 过滤可注入 cookie {len(sel)}/{len(src)} 条")
PY
  [ -s "$COOKIE_TMP" ] && "$B" cookie-import "$COOKIE_TMP" 2>&1 | tail -1
fi

echo "=== 打开创作者发布页 ==="
"$B" goto https://creator.xiaohongshu.com/publish/publish >/dev/null 2>&1
sleep 3
URL_NOW="$("$B" url 2>/dev/null || true)"
echo "[url] $URL_NOW"

case "$URL_NOW" in
  *login*|*signin*|*passport*)
    echo "ERROR: 未登录, 被重定向到 [${URL_NOW}] 请运行 login_xhs.sh 后重试" >&2
    exit 2 ;;
  *captcha*|*verify*|*unhuman*)
    echo "ERROR: 触发小红书人机验证 [${URL_NOW}] 请有头 browse connect 人工通过后重试" >&2
    exit 4 ;;
esac
echo "OK: 小红书登录态正常"
exit 0
