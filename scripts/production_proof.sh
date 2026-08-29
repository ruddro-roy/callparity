#!/usr/bin/env bash
# Production proof in about 60 seconds, on a throwaway API instance.
#
# Boots the API on its own port and SQLite file, then demonstrates:
#   1. crash convergence  - SIGKILL mid-parity, reboot, the orphaned job reads
#                           failed with a clear error, a deliberate retry
#                           completes with RESTAGE_AND_RECALL
#   2. rate limiting      - the operator budget runs out into 429 + Retry-After,
#                           and an unauthenticated flood is metered by client IP
#   3. /metrics           - Prometheus text exposition, counts only
#
# Run from the repo root with the local venv active (see README quickstart).
# It never touches the compose stack on port 8000 and cleans up after itself.
set -u

PORT=8123
BASE="http://127.0.0.1:${PORT}"
DB=/tmp/callparity_proof.db
PIDFILE=/tmp/callparity_proof.pid
LOG=/tmp/callparity_proof.log
TOKEN=callparity-demo-operator
AUTH="Authorization: Bearer ${TOKEN}"

boot() {
  DATABASE_URL="sqlite+pysqlite:///${DB}" SEED_ON_STARTUP=true \
    REDIS_OPTIONAL=true USE_FIXTURES=true PLAYBACK_DELAY_MS="$1" \
    OPERATOR_TOKEN="${TOKEN}" MUTATING_RATE_LIMIT=3 MUTATING_RATE_WINDOW_SECONDS=60 \
    uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port "${PORT}" \
    >>"${LOG}" 2>&1 &
  echo $! >"${PIDFILE}"
  for _ in $(seq 1 40); do
    curl -sf "${BASE}/readyz" >/dev/null 2>&1 && return 0
    sleep 0.25
  done
  echo "API did not become ready; see ${LOG}" >&2
  return 1
}

stop() {
  if [ -f "${PIDFILE}" ]; then
    kill -9 "$(cat "${PIDFILE}")" 2>/dev/null
    rm -f "${PIDFILE}"
  fi
}
trap stop EXIT

job_field() {
  curl -s "${BASE}/v1/jobs/$1" | python -c "import json,sys; print(json.load(sys.stdin)$2)"
}

rm -f "${DB}" "${LOG}"
echo "== 1. crash convergence =="
boot 2000 || exit 1
JOB=$(curl -s -X POST "${BASE}/v1/tickets/FR-1842/parity" -H "${AUTH}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "parity started: ${JOB}"
sleep 2
echo "kill -9 $(cat "${PIDFILE}") mid-run"
stop
sleep 1
python - "${DB}" "${JOB}" <<'PY'
import sqlite3, sys
row = sqlite3.connect(sys.argv[1]).execute(
    "SELECT status, error FROM jobs WHERE id = ?", (sys.argv[2],)
).fetchone()
print(f"row after crash: status={row[0]} error={row[1]}")
PY
echo "rebooting on the same database..."
boot 0 || exit 1
echo "same job after reboot: status=$(job_field "${JOB}" '["status"]')"
echo "                       error=$(job_field "${JOB}" '["error"]')"
RETRY=$(curl -s -X POST "${BASE}/v1/tickets/FR-1842/parity" -H "${AUTH}" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
for _ in $(seq 1 60); do
  S=$(job_field "${RETRY}" '["status"]')
  { [ "$S" = completed ] || [ "$S" = failed ]; } && break
  sleep 0.5
done
echo "deliberate retry: ${RETRY} status=${S} action=$(job_field "${RETRY}" '["result"]["action"]["action"]')"

echo
echo "== 2. rate limiting (limit 3 per 60s on this instance) =="
echo "-- operator runs out of budget --"
for i in 1 2 3; do
  printf 'preview %s: %s\n' "$i" "$(curl -s -o /dev/null \
    -w '%{http_code} retry_after=%header{Retry-After}' \
    -X POST "${BASE}/v1/tickets/FR-1842/preview" -H "${AUTH}")"
done
echo "-- an unauthenticated flood is metered by client IP, pre-401 --"
for i in 1 2 3 4; do
  printf 'no token %s: %s\n' "$i" "$(curl -s -o /dev/null \
    -w '%{http_code} retry_after=%header{Retry-After}' \
    -X POST "${BASE}/v1/tickets/FR-1842/preview")"
done

echo
echo "== 3. /metrics =="
curl -s "${BASE}/metrics"
echo
echo "production proof complete"
