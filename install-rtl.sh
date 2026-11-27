#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Antigravity Persian RTL & Vazirmatn Installer (Linux)"
echo "============================================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is required but not found in PATH." >&2
  exit 1
fi

python3 "$SCRIPT_DIR/antigravity_rtl.py" patch --target all "$@"

echo
echo "Done! You can now launch 'Antigravity RTL' from your application menu."
echo "Note: Restart Antigravity if it is currently running to see the changes."
