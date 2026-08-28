#!/usr/bin/env bash
# Run the CallParity FastAPI engine on 127.0.0.1:8000 using the Docker-free
# local path (SQLite + Redis-optional + fixtures). Seeds on startup if empty.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
. .venv/bin/activate

export DATABASE_URL="sqlite+pysqlite:///${REPO_ROOT}/callparity.db"
export REDIS_OPTIONAL=true
export USE_FIXTURES=true
export SEED_ON_STARTUP=true
export PYTHONPATH="${REPO_ROOT}/apps/api"

exec uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --no-access-log
