#!/usr/bin/env bash
# 兼容入口 → business/means/diagram-build/scripts/run_smoke.sh
ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
exec bash "$ROOT/business/means/diagram-build/scripts/run_smoke.sh"
