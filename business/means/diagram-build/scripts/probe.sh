#!/usr/bin/env bash
# ALL Launch 前探针 — 委托 check_drawio_ready.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/check_drawio_ready.sh"
