#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Applying Antigravity Persian RTL patch (force)..."
python3 "$SCRIPT_DIR/antigravity_rtl.py" patch --target all --force "$@"
echo "Done! Restart Antigravity to apply changes."
