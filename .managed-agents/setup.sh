#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Managed Agents setup for hwells4/create-hooks"
echo "Boot mode: ${MANAGED_AGENTS_BOOT_MODE:-unknown}"

# This repository is documentation/templates plus Python helper scripts.
# There are no project dependencies, builds, migrations, or seed steps to bake.
# If future Pi npm extension packages are added under .pi/npm, install them at
# image-build time rather than during start.sh.
if [ -f ".pi/npm/package-lock.json" ]; then
  npm ci --prefix .pi/npm
elif [ -f ".pi/npm/package.json" ]; then
  npm install --prefix .pi/npm
fi

python3 --version >/dev/null

echo "Setup complete."
