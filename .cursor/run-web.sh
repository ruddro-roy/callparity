#!/usr/bin/env bash
# Run the CallParity Vite + React workbench on 0.0.0.0:3000.
# Vite proxies /v1 and /healthz to the API on 127.0.0.1:8000.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/apps/web"

exec npm run dev -- --host 0.0.0.0 --port 3000
