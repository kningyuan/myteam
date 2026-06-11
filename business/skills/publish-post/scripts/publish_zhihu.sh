#!/bin/bash
# 知乎专栏自动发文（动作型任务的真实执行工具）。
#
# 用法:
#   publish_zhihu.sh "标题" "正文" "证据截图输出路径.png"
#   publish_zhihu.sh "标题" @/path/to/body.md "证据截图.png"   # 长文推荐
#
# 行为:
#   1. 从 ~/.gstack/zhihu-cookies.json 注入会话 cookie；
#   2. 校验登录态（未登录 exit 2；人机验证 exit 4）；
#   3. 填标题、正文、点发布；
#   4. 输出 PUBLISHED_URL / SCREENSHOT 供 Gate 解析。
#
# 退出码: 0 成功; 2 未登录; 3 URL 非文章页; 4 人机验证
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

TITLE="${1:?需要标题}"
CONTENT="${2:?需要正文或 @正文文件.md}"
SHOT="${3:-/tmp/zhihu-post-$(date +%Y%m%d-%H%M%S).png}"

if [[ "$CONTENT" == @* ]]; then
  CONTENT_FILE="${CONTENT#@}"
  [ -f "$CONTENT_FILE" ] || { echo "ERROR: 正文文件不存在 $CONTENT_FILE"; exit 1; }
  CONTENT="$(cat "$CONTENT_FILE")"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../zhihu-operations/scripts/_zhihu_browse.sh
source "$SCRIPT_DIR/../../zhihu-operations/scripts/_zhihu_browse.sh"
trap '_zhihu_cleanup_cookies' EXIT

_zhihu_find_browse || exit 1
_zhihu_prepare_cookies

echo "=== 1. 注入会话 cookie ==="
_zhihu_inject_cookies

echo "=== 2. 进入写作页并校验登录态 ==="
"$B" goto https://zhuanlan.zhihu.com/write >/dev/null 2>&1
sleep 3
URL_NOW="$("$B" url 2>/dev/null || true)"
_zhihu_check_login_url "$URL_NOW" || exit $?
echo "[login] 登录态正常，当前页：$URL_NOW"

echo "=== 3. 填写标题 ==="
"$B" fill 'textarea[placeholder*="标题"]' "$TITLE" 2>&1 | tail -1

echo "=== 4. 填写正文 ==="
"$B" click '.public-DraftEditor-content' >/dev/null 2>&1
"$B" type "$CONTENT" >/dev/null 2>&1

echo "=== 5. 点击发布 ==="
sleep 1
"$B" js '[...document.querySelectorAll("button")].find(e => e.textContent.trim() === "发布" && e.className.includes("Button--primary"))?.click()' >/dev/null 2>&1
sleep 4

PUBLISHED_URL="$("$B" url 2>/dev/null || true)"
PUBLISHED_URL="${PUBLISHED_URL:-unknown}"
echo "=== 6. 截图回证 ==="
mkdir -p "$(dirname "$SHOT")"
TMP_SHOT="$(mktemp /tmp/zhihu-shot-XXXX.png)"
if "$B" screenshot "$TMP_SHOT" >/dev/null 2>&1; then
  cp "$TMP_SHOT" "$SHOT" 2>/dev/null || true
  rm -f "$TMP_SHOT" 2>/dev/null || true
fi

echo "PUBLISHED_URL=${PUBLISHED_URL}"
echo "SCREENSHOT=${SHOT}"

if printf '%s' "${PUBLISHED_URL}" | grep -q 'zhuanlan.zhihu.com/p/'; then
  echo "[ok] 发布成功"
  exit 0
fi
echo "WARN: 发布后 URL 非文章页(${PUBLISHED_URL})，疑似未真正发布或需人工处理"
exit 3
