#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Managed Agents start for hwells4/create-hooks"
echo "Boot mode: ${MANAGED_AGENTS_BOOT_MODE:-unknown}"

# No long-running dev server is required for this repository.
# Keep this hook launch-only and fast.
exit 0
