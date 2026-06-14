#!/bin/bash
# 知乎 gstack browse 公共逻辑（被 login / check / publish 脚本 source）
set -uo pipefail

_zhihu_find_browse() {
  B="${GSTACK_BROWSE:-}"
  for c in "$HOME/skill/gstack/browse/dist/browse" "$HOME/.claude/skills/gstack/browse/dist/browse"; do
    [ -z "$B" ] && [ -x "$c" ] && B="$c"
  done
  if [ ! -x "$B" ]; then
    echo "ERROR: 未找到 gstack browse 二进制" >&2
    return 1
  fi
  export B
}

_zhihu_prepare_cookies() {
  COOKIE_SRC="${ZHIHU_COOKIE_SRC:-$HOME/.gstack/zhihu-cookies.json}"
  COOKIE_TMP="$(mktemp /tmp/zhihu-cookies-XXXX.json)"
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
  export COOKIE_SRC COOKIE_TMP
}

_zhihu_inject_cookies() {
  "$B" goto https://www.zhihu.com >/dev/null 2>&1
  [ -s "$COOKIE_TMP" ] && "$B" cookie-import "$COOKIE_TMP" 2>&1 | tail -1
}

_zhihu_check_login_url() {
  local url="${1:-}"
  case "$url" in
    *signin*)
      echo "ERROR: 未登录, 被重定向到 [${url}] 请运行 login_zhihu.sh 后重试" >&2
      return 2 ;;
    *unhuman*|*/account/*|*captcha*|*verify*)
      echo "ERROR: 触发知乎反爬/人机验证 [${url}] 请运行 login_zhihu.sh 或有头 browse connect" >&2
      return 4 ;;
  esac
  return 0
}

_zhihu_export_cookies() {
  local out="${1:?需要 cookie 输出路径}"
  mkdir -p "$(dirname "$out")"
  "$B" cookies > "$out"
}

_zhihu_cleanup_cookies() {
  [ -n "${COOKIE_TMP:-}" ] && rm -f "$COOKIE_TMP"
}
