#!/usr/bin/env bash
# diagram-build means 冒烟（ALL 过程 + draw.io 渲染）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
MEANS="$ROOT/business/means/diagram-build"
PLAY="$ROOT/business/playbooks/scripts"
PY="${ROOT}/venv/bin/python3"
[ -x "$PY" ] || PY=python3
OUT="/tmp/myteam-diagram-smoke-$$"
mkdir -p "$OUT"

echo "=== diagram-build means smoke ==="
bash "$PLAY/scaffold_process.sh" "$OUT"
bash "$MEANS/scripts/probe.sh" | tee -a "$OUT/verify.log"
cp "$MEANS/templates/diagram_brief.yaml" "$OUT/diagram_brief.yaml"
"$PY" "$MEANS/scripts/brief_to_drawio.py" "$OUT/diagram_brief.yaml" "$OUT/diagram.drawio"
bash "$MEANS/scripts/build_diagram.sh" "$OUT/diagram.drawio" "$OUT/diagram.png"
"$PY" "$MEANS/scripts/verify_diagram.py" "$OUT/diagram.drawio" --png "$OUT/diagram.png"
for f in align.md plan.md verify.log ledger.entry.yaml trace.manifest.yaml diagram.drawio diagram.png; do
  [ -f "$OUT/$f" ] || { echo "FAIL: missing $f" >&2; exit 1; }
done
echo "diagram-build smoke: PASS"
echo "  产物: $OUT/"
