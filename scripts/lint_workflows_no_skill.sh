#!/usr/bin/env bash
# A 层规范：workflow description 不得硬编码 【Skill】路径
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WF="$ROOT/business/workflows"
FAIL=0
while IFS= read -r -d '' f; do
  if grep -q '【Skill】' "$f"; then
    echo "FAIL: $f 含 【Skill】（应写在 plan.md / catalog，不写 workflow）"
    grep -n '【Skill】' "$f" || true
    FAIL=1
  fi
done < <(find "$WF" -name '*.yaml' -print0)
if [ "$FAIL" -eq 0 ]; then
  echo "lint_workflows_no_skill: PASS"
else
  exit 1
fi
