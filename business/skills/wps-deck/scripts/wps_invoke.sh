#!/usr/bin/env bash
# HTTP 调用 WPS 加载项 RPC build_deck
set -uo pipefail

BRIEF="${1:?用法: wps_invoke.sh <brief.yaml> <output.pptx>}"
OUT="${2:?用法: wps_invoke.sh <brief.yaml> <output.pptx>}"
WPS_RPC_URL="${WPS_RPC_URL:-http://127.0.0.1:19074}"

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
PY="${ROOT}/venv/bin/python3"
[ -x "$PY" ] || PY=python3

# brief yaml → json
BRIEF_JSON="$("$PY" -c "
import json, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit(2)
p = Path(sys.argv[1])
print(json.dumps(yaml.safe_load(p.read_text(encoding='utf-8')), ensure_ascii=False))
" "$BRIEF" 2>/dev/null)" || {
  echo "ERROR: brief 转 JSON 失败（需 PyYAML）" >&2
  exit 1
}

OUT_ABS="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"

payload="$("$PY" -c "
import json, sys
brief = json.loads(sys.argv[1])
print(json.dumps({
    'briefPath': sys.argv[2],
    'outputPath': sys.argv[3],
    'brief': brief,
}, ensure_ascii=False))
" "$BRIEF_JSON" "$BRIEF" "$OUT_ABS")"

resp="$(curl -s -w '\n%{http_code}' --max-time 120 \
  -H 'Content-Type: application/json' \
  -d "$payload" \
  "${WPS_RPC_URL}/build_deck" 2>/dev/null || echo -e '\n000')"
body="$(echo "$resp" | head -n -1)"
code="$(echo "$resp" | tail -n 1)"

if [ "$code" = "200" ] && [ -f "$OUT_ABS" ]; then
  echo "OK: wps_invoke → $OUT_ABS"
  echo "$body"
  exit 0
fi

echo "FAIL: wps_invoke HTTP $code" >&2
echo "$body" >&2
exit 1
