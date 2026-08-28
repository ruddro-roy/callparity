#!/usr/bin/env bash
# Idempotent bootstrap for the CallParity Cloud Agent environment.
# Uses the Docker-free local path from README.md: SQLite + Redis-optional +
# fixtures, so no Docker/Postgres/Redis/CALL-E credentials are needed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The stock Debian/Ubuntu python3 ships without ensurepip; venv creation fails
# without it. Install python3-venv only when it is actually missing.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Python API dependencies in an isolated virtualenv.
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip
pip install -r apps/api/requirements.txt pytest

# Web workbench dependencies.
( cd apps/web && npm install --no-audit --no-fund )

# Seed the local SQLite database (idempotent: only inserts missing tickets).
export DATABASE_URL="sqlite+pysqlite:///${REPO_ROOT}/callparity.db"
export REDIS_OPTIONAL=true
export USE_FIXTURES=true
export PYTHONPATH="${REPO_ROOT}/apps/api"
python scripts/seed_demo_data.py

echo "CallParity install complete."
