#!/bin/bash
# Hub UI 依赖的关键 API 探活（需 Hub 已启动）
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"

PORT="${MYTEAM_HUB_PORT:-8765}"
BASE="${MYTEAM_HUB_URL:-http://127.0.0.1:${PORT}}"
FAIL=0

probe() {
  local path="$1"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}${path}" 2>/dev/null || echo "000")"
  if [ "$code" = "200" ]; then
    echo "OK   ${path} → ${code}"
  else
    echo "FAIL ${path} → ${code}" >&2
    FAIL=1
  fi
}

echo "=== hub-ui-debug: API 探活 ${BASE} ==="
probe "/api/obs/summary"
probe "/api/config"
probe "/api/backends"
probe "/api/agents"

if [ "$FAIL" -eq 0 ]; then
  echo "probe: PASS"
  exit 0
fi
echo "probe: FAIL（确认 Hub 已启动且端口正确）" >&2
exit 1
