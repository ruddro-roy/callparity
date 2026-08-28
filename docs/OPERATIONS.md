# CallParity operations guide

This is the reference for running the CallParity API in production: every
environment variable the process reads, how the schema reaches the database,
which endpoints require which credentials, what the service tells you at
runtime, and what happens after a crash. Everything here describes code that
exists on main; nothing is aspirational.

## Configuration

Settings load from the process environment, with a `.env` file in the working
directory as a fallback (`apps/api/app/config.py`). Unknown variables are
ignored.

| Variable | Default | Effect |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+pysqlite:///./callparity.db` | SQLAlchemy URL. A `postgres...` URL is migrated with Alembic at startup; any other URL (SQLite in local dev and tests) gets `create_all`. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for transcript pointers and job locks. Ignored when `REDIS_OPTIONAL=true`. |
| `REDIS_OPTIONAL` | `false` | `true` replaces Redis with an in-process store: no Redis client is created, `healthz` reports redis up, pointers and locks live in process memory. For single-process setups and offline tests. |
| `USE_FIXTURES` | `true` | `true` serves the recorded FR-1842 / FR-1900 / FR-1888 fact patterns through `FixtureCalle`; `false` uses the live CALL-E adapter. `healthz` reports the mode. |
| `CALLE_BASE_URL` | empty | Base URL of the CALL-E API. Required for live mode and for `parity/import` reads; the live adapter refuses to send anything without it. |
| `CALLE_API_TOKEN` | empty | Bearer token for the CALL-E Calls API. Same requirement as `CALLE_BASE_URL`. |
| `CALLE_WEBHOOK_SECRET` | empty | When set, `POST /v1/webhooks/calle` requires a valid HMAC-SHA256 signature over the raw body (`X-Calle-Signature` or `X-Signature` header) and fails closed with 401 otherwise. When empty, the webhook accepts unsigned posts. |
| `OPERATOR_TOKEN` | empty | Gates the five mutating routes. Empty denies everyone (the API still boots). Accepts several comma-separated tokens so a rotation can overlap the old and new credential; each token keeps its own audit fingerprint and rate bucket, and a value with an empty segment (`a,,b`, a lone comma) refuses to boot. |
| `MUTATING_RATE_LIMIT` | `60` | Requests allowed per fingerprint (or per client IP pre-auth) within the window, shared across all five mutating routes. `0` disables the limiter. A negative value denies every mutating call. |
| `MUTATING_RATE_WINDOW_SECONDS` | `60` | Sliding window for the limit above. A non-positive value denies every mutating call. |
| `LOG_LEVEL` | `INFO` | Level for the structured JSON logs on stdout. |
| `SEED_ON_STARTUP` | `true` | Seeds the three demo tickets at boot when the tickets table is empty. A non-empty table is never touched. |
| `PLAYBACK_DELAY_MS` | `180` | Pace of fixture transcript playback in the parity loop. Read directly from the environment (not part of `Settings`). Set `0` in tests for instant runs. |

## Database migrations

At startup (`prepare_schema` in `apps/api/app/db.py`):

- A Postgres `DATABASE_URL` runs `apply_migrations` (`apps/api/app/migrate.py`).
  It converges from any starting state: an empty database is upgraded to
  head, a complete pre-Alembic `create_all` schema is stamped at head so its
  data survives, an already-versioned database gets a no-op upgrade, and a
  partial schema is refused with a `RuntimeError` naming the missing tables
  rather than guessed at.
- Inspection and DDL run on one connection inside one transaction, and on
  Postgres that transaction first takes `pg_advisory_xact_lock` on a fixed
  key. Replicas booting at the same moment queue on the lock: the first one
  migrates, the rest re-inspect the committed schema and no-op. The lock
  releases itself on commit, rollback, or a dead connection.
- SQLite (local dev, tests) keeps `Base.metadata.create_all` and never sees
  Alembic or the lock. The schemas are identical either way, which
  `tests/test_migrations.py` proves against autogenerate.

To migrate manually, from the repo root:

    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db \
      alembic -c apps/api/alembic.ini upgrade head

`alembic/env.py` reads `DATABASE_URL` through the app settings, so the same
value the API uses is the only input.

## Endpoints and authentication

Public, no credentials:

| Route | Behavior |
| --- | --- |
| `GET /` | Service name and whether fixtures are on. |
| `GET /healthz` | `postgres`, `redis`, `calle` each up or down, plus the mode (`fixture` or `live`). Status `ok` only when all three are up, else `degraded`. Always 200. |
| `GET /readyz` | 200 `{"status": "ready"}` when the database answers, else 503. Kubernetes-style readiness. |
| `GET /metrics` | Prometheus text exposition; see observability. |
| `GET /v1/tickets/{id}` | Ticket detail. |
| `GET /v1/jobs/{id}` | Job status, result, and error. |
| `GET /v1/tickets/{id}/events` | Server-sent events for a running parity job; pings while idle, closes after the terminal event. |

Operator-gated and rate-limited (the five mutating routes). Present the
token as `Authorization: Bearer <token>` or in `X-Operator-Token`:

| Route | Behavior |
| --- | --- |
| `POST /v1/tickets` | Create a ticket. |
| `POST /v1/tickets/{id}/preview` | Plan-B question preview; no call placed. |
| `POST /v1/tickets/{id}/parity` | Start a parity job (202 with the job). Consent is checked per party first (403 without it). Honors `Idempotency-Key`. |
| `POST /v1/tickets/{id}/parity/import` | Run parity on two existing CALL-E call records. Read-only against CALL-E (GET only, never places a call) and writes an import audit row. Consent is checked the same way. |
| `POST /v1/jobs/{id}/cancel` | Cancel a job. |

Webhook: `POST /v1/webhooks/calle` is gated by the HMAC signature when
`CALLE_WEBHOOK_SECRET` is set, as described in the configuration table.

Rate limiting semantics (`apps/api/app/rate_limit.py`): one sliding-window
budget of `MUTATING_RATE_LIMIT` requests per `MUTATING_RATE_WINDOW_SECONDS`,
shared across all five mutating routes, keyed by the operator-token
fingerprint. Requests without a valid token are metered against the client
IP before the 401 goes out, so an unauthenticated or forged-token flood
receives 429 instead of unmetered 401s and cannot drain a real operator's
budget. A denied request gets 429 with a `Retry-After` header in seconds.
The store is in-process (compose runs a single uvicorn worker) and bounds
its tracked keys, failing closed under key-space pressure. Health, readiness,
metrics, and reads are never limited.

## Observability

- Request ids: every response carries `X-Request-ID`. A client-supplied
  value is honored only when it is a canonical UUID; anything else is
  replaced, so a token or phone-shaped string can never become an id the
  server echoes and logs. Unhandled errors still return the id on the 500.
- Access logs: exactly one JSON line per request (`http.request`) with
  method, path, status, latency in ms, and the bound request id. Bodies,
  headers, and query strings never appear.
- All logs are structured JSON on stdout via structlog, level from
  `LOG_LEVEL`.
- Redaction: the final logging processor recursively scrubs E.164-shaped
  runs from every log value, replacing them with `[phone]`. This is a
  safety net over call sites that already mask; property-based tests fuzz
  it (`tests/test_redaction_properties.py`).
- Metrics: `GET /metrics` exposes `callparity_requests_total` (counter,
  responses by status class, counted in process) and
  `callparity_jobs_total` (gauge, parity jobs in a terminal status —
  completed, failed, cancelled — read from the database at scrape time, so
  it survives restarts). The exposition carries only counts and fixed
  labels: no identifiers, tokens, or payloads.

## Crash recovery

Parity jobs execute as in-process background tasks and die with the
process. At startup the API reconciles rows a crash left `queued` or
`running`: each becomes `failed` with the operator-facing error
"interrupted by a restart before completion; run parity again to start a
fresh job", and its idempotency key is released by suffixing
`#interrupted:<job_id>`, so the ticket is never wedged behind a dead job
and a deliberate retry starts a fresh run under the original key. Nothing
re-executes automatically: in live mode that would redial humans. Terminal
rows are untouched, so a second boot is a no-op.

## Security posture

- Fail closed everywhere: an unset operator token denies all mutating
  requests, a malformed multi-token value refuses to boot, the live CALL-E
  adapter refuses to act without both base URL and API token, and a
  configured webhook secret rejects unsigned or mismatched posts.
- Token comparison uses `hmac.compare_digest` for every configured
  candidate, and every candidate is always compared.
- Audit rows (`import_audit`) store the actor as a non-reversible
  fingerprint (`op_` + SHA-256 prefix), never the raw token, alongside the
  ticket, the two call ids, the resulting action, and the job id. During a
  token rotation the old and new credential produce distinct fingerprints,
  so the audit trail tells them apart.
- No phone digits reach logs (redaction above) or this repository's files;
  the test suite enforces both structurally.
- CI runs entirely offline and never receives `CALLE_API_TOKEN` or
  `CALLE_BASE_URL`, so no pipeline can place a call.
