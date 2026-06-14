#!/bin/bash
# 小红书笔记发布辅助（gstack browse）。
#
# 用法:
#   publish_xhs.sh "标题" "正文" "证据截图.png"
#   publish_xhs.sh "标题" @/path/to/body.md "证据截图.png"
#
# 说明:
#   小红书笔记通常需人工上传配图；本脚本打开创作者发布页、尝试填标题/正文并截图。
#   若无法自动发布，须人工完成发布后更新 PUBLISHED_URL。
#
# 退出码: 0 成功(URL 含 xiaohongshu.com); 2 未登录; 3 URL 非笔记页; 4 人机验证
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

TITLE="${1:?需要标题}"
CONTENT="${2:?需要正文或 @正文文件.md}"
SHOT="${3:-/tmp/xhs-post-$(date +%Y%m%d-%H%M%S).png}"

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

COOKIE_SRC="${XHS_COOKIE_SRC:-$HOME/.gstack/xhs-cookies.json}"
COOKIE_TMP="$(mktemp /tmp/xhs-cookies-XXXX.json)"
export COOKIE_SRC COOKIE_TMP
if [ -f "$COOKIE_SRC" ]; then
  python3 - "$COOKIE_SRC" "$COOKIE_TMP" <<'PY'
import json, sys
src = json.load(open(sys.argv[1]))
keep = {".xiaohongshu.com", "www.xiaohongshu.com", "creator.xiaohongshu.com"}
sel = [c for c in src if any(d in c.get("domain", "") for d in keep)]
json.dump(sel, open(sys.argv[2], "w"), ensure_ascii=False)
PY
fi

echo "=== 1. 注入 cookie 并进入创作者发布页 ==="
"$B" goto https://www.xiaohongshu.com >/dev/null 2>&1
[ -s "$COOKIE_TMP" ] && "$B" cookie-import "$COOKIE_TMP" 2>&1 | tail -1
"$B" goto https://creator.xiaohongshu.com/publish/publish >/dev/null 2>&1
sleep 3
URL_NOW="$("$B" url 2>/dev/null || true)"
case "$URL_NOW" in
  *login*|*signin*|*passport*)
    echo "ERROR: 未登录 [$URL_NOW]" >&2; exit 2 ;;
  *captcha*|*verify*)
    echo "ERROR: 人机验证 [$URL_NOW]" >&2; exit 4 ;;
esac

echo "=== 2. 尝试填写标题/正文（页面结构变化时需人工发布）==="
"$B" fill 'input[placeholder*="标题"], textarea[placeholder*="标题"]' "$TITLE" 2>&1 | tail -1 || true
"$B" click '.ql-editor, [contenteditable="true"]' >/dev/null 2>&1 || true
"$B" type "$CONTENT" >/dev/null 2>&1 || true

echo "WARN: 小红书须人工上传配图并点击发布；等待 30s 供人工操作..."
sleep 30

PUBLISHED_URL="$("$B" url 2>/dev/null || true)"
mkdir -p "$(dirname "$SHOT")"
TMP_SHOT="$(mktemp /tmp/xhs-shot-XXXX.png)"
"$B" screenshot "$TMP_SHOT" >/dev/null 2>&1 && cp "$TMP_SHOT" "$SHOT" 2>/dev/null || true
rm -f "$TMP_SHOT" 2>/dev/null || true

echo "PUBLISHED_URL=${PUBLISHED_URL:-unknown}"
echo "SCREENSHOT=${SHOT}"

if printf '%s' "${PUBLISHED_URL}" | grep -q 'xiaohongshu.com'; then
  echo "[ok] 当前页含 xiaohongshu.com（请确认是否为已发布笔记 URL）"
  exit 0
fi
echo "WARN: 未检测到笔记 URL，请人工发布后在交付物中填写真实链接"
exit 3
