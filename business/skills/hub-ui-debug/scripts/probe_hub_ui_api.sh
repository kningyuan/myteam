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

# 项目概览须含发起配置字段（旧 Hub 进程会缺 launch/created_at → 需 ./run.sh stop && ./run.sh start）
if curl -s --max-time 5 "${BASE}/api/obs/projects" -o /tmp/myteam_ov.json 2>/dev/null; then
  pid="$(python3 -c "import json; d=json.load(open('/tmp/myteam_ov.json')); ps=d.get('projects') or []; print(ps[0]['id'] if ps else '')" 2>/dev/null || true)"
  if [ -n "$pid" ] && curl -s --max-time 5 "${BASE}/api/obs/projects/${pid}/overview" -o /tmp/myteam_ov_detail.json 2>/dev/null; then
    if python3 -c "
import json, sys
d = json.load(open('/tmp/myteam_ov_detail.json'))
missing = {'launch', 'created_at'} - set(d.keys())
if missing:
    print('FAIL overview missing keys:', ', '.join(sorted(missing)), file=sys.stderr)
    print('HINT: restart Hub — cd myteam && ./run.sh stop && ./run.sh start', file=sys.stderr)
    sys.exit(1)
if not isinstance(d.get('launch'), dict):
    print('FAIL overview.launch not object', file=sys.stderr)
    sys.exit(1)
print('OK   /api/obs/projects/${pid}/overview → launch snapshot')
"; then
      :
    else
      FAIL=1
    fi
  fi
fi

if [ "$FAIL" -eq 0 ]; then
  echo "probe: PASS"
  exit 0
fi
echo "probe: FAIL（确认 Hub 已启动且端口正确）" >&2
exit 1
