#!/bin/bash
# 知乎专栏自动发文（动作型任务的真实执行工具）。
#
# 用法:
#   publish_zhihu.sh "标题" "正文" "证据截图输出路径.png"
#
# 行为:
#   1. 自动从 ~/.gstack/zhihu-cookies.json 过滤出可导入的会话 cookie 并注入；
#   2. 进入写作页，校验登录态（未登录则退出码 2，提示需重新登录）；
#   3. 填标题、填正文、点发布；
#   4. 截图回证，并以 KEY=VALUE 形式打印 PUBLISHED_URL / SCREENSHOT，供门禁/上游解析。
#
# 退出码: 0 成功; 2 未登录; 3 发布后 URL 异常(疑似未真正发布)。
set -uo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

TITLE="${1:?需要标题}"
CONTENT="${2:?需要正文}"
SHOT="${3:-/tmp/zhihu-post-$(date +%Y%m%d-%H%M%S).png}"

# 定位 gstack browse 二进制
B="${GSTACK_BROWSE:-}"
for c in "$HOME/skill/gstack/browse/dist/browse" "$HOME/.claude/skills/gstack/browse/dist/browse"; do
  [ -z "$B" ] && [ -x "$c" ] && B="$c"
done
[ -x "$B" ] || { echo "ERROR: 未找到 gstack browse 二进制"; exit 1; }

COOKIE_SRC="$HOME/.gstack/zhihu-cookies.json"
COOKIE_TMP="$(mktemp /tmp/zhihu-cookies-XXXX.json)"
trap 'rm -f "$COOKIE_TMP"' EXIT

# cookie-import 按当前页域严格匹配，故只保留可在 www.zhihu.com 注入的域。
if [ -f "$COOKIE_SRC" ]; then
  python3 - "$COOKIE_SRC" "$COOKIE_TMP" <<'PY'
import json, sys
src = json.load(open(sys.argv[1]))
keep = {".zhihu.com", "www.zhihu.com"}
sel = [c for c in src if c.get("domain", "") in keep]
json.dump(sel, open(sys.argv[2], "w"), ensure_ascii=False)
print(f"[cookie] 过滤可注入 cookie {len(sel)}/{len(src)} 条")
PY
fi

echo "=== 1. 注入会话 cookie ==="
"$B" goto https://www.zhihu.com >/dev/null 2>&1
[ -s "$COOKIE_TMP" ] && "$B" cookie-import "$COOKIE_TMP" 2>&1 | tail -1

echo "=== 2. 进入写作页并校验登录态 ==="
"$B" goto https://zhuanlan.zhihu.com/write >/dev/null 2>&1
sleep 3
URL_NOW="$("$B" url 2>/dev/null)"
case "$URL_NOW" in
  *signin*)
    echo "ERROR: 未登录, 被重定向到 [${URL_NOW}] 请先用有头模式登录知乎后重试"; exit 2 ;;
  *unhuman*|*/account/*|*captcha*|*verify*)
    echo "ERROR: 触发知乎反爬/人机验证 [${URL_NOW}] 无头模式被拦截，请改用有头反爬模式:"
    echo "       ${B} connect   # 打开可见浏览器，必要时人工通过验证后再重试本脚本"
    exit 4 ;;
esac
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
# gstack 截图仅允许写入 /tmp，故先截到临时文件再拷贝到目标路径。
TMP_SHOT="$(mktemp /tmp/zhihu-shot-XXXX.png)"
if "$B" screenshot "$TMP_SHOT" >/dev/null 2>&1; then
  cp "$TMP_SHOT" "$SHOT" 2>/dev/null || true
  rm -f "$TMP_SHOT" 2>/dev/null || true
fi

echo "PUBLISHED_URL=${PUBLISHED_URL}"
echo "SCREENSHOT=${SHOT}"

# 已发布文章页形如 zhuanlan.zhihu.com/p/<id>；仍停在 /write 视为未真正发布。
if printf '%s' "${PUBLISHED_URL}" | grep -q 'zhuanlan.zhihu.com/p/'; then
  echo "[ok] 发布成功"
  exit 0
fi
echo "WARN: 发布后 URL 非文章页(${PUBLISHED_URL})，疑似未真正发布或需人工处理"
exit 3
