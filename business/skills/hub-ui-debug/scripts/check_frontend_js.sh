#!/bin/bash
# 扫描 frontend/*.js：语法检查 + 跨文件重复 let 全局变量
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
FRONTEND="$ROOT/frontend"
FAIL=0

echo "=== hub-ui-debug: frontend JS 检查 ==="

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: 需要 node（用于 --check）" >&2
  exit 1
fi

echo "--- 语法 (node --check) ---"
while IFS= read -r -d '' f; do
  rel="${f#"$ROOT"/}"
  if ! node --check "$f" 2>/dev/null; then
    echo "FAIL syntax: $rel"
    node --check "$f" 2>&1 | head -5
    FAIL=1
  else
    echo "OK   $rel"
  fi
done < <(find "$FRONTEND" -maxdepth 1 -name '*.js' -print0 | sort -z)

echo ""
echo "--- 跨文件重复 let（仅顶层，行首 let） ---"
TMP="$(mktemp)"
find "$FRONTEND" -maxdepth 1 -name '*.js' -print0 | sort -z | while IFS= read -r -d '' f; do
  rel="${f#"$ROOT"/}"
  grep -nE '^let[[:space:]]+[A-Za-z_$][A-Za-z0-9_$]*' "$f" 2>/dev/null \
    | while IFS= read -r line; do
      name="$(sed -E 's/.*^let[[:space:]]+([A-Za-z_$][A-Za-z0-9_$]*).*/\1/' <<<"$line")"
      echo "${name}|${rel}|${line}"
    done
done > "$TMP"

DUPES="$(cut -d'|' -f1 "$TMP" | sort | uniq -d)"
if [ -n "$DUPES" ]; then
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    echo "FAIL duplicate let: ${name}"
    grep "^${name}|" "$TMP" || true
    FAIL=1
  done <<< "$DUPES"
else
  echo "OK   无跨文件重复 let"
fi
rm -f "$TMP"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "hub-ui-debug: PASS"
  exit 0
fi
echo "hub-ui-debug: FAIL" >&2
exit 1
