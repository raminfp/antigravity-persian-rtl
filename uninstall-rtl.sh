#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Antigravity Persian RTL Uninstaller (Linux)"
echo "============================================================"
echo

python3 "$SCRIPT_DIR/antigravity_rtl.py" restore-shortcuts "$@"
python3 "$SCRIPT_DIR/antigravity_rtl.py" restore --target all "$@"

echo
echo "Restored Antigravity to original state and removed RTL shortcuts."
