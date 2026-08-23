# CallParity

**Two phones. One operational fact. A live contradiction graph.**

CallParity turns a two-sided ops ticket into a test. It places (or fixtures) a CALL-E call to Party A, extracts typed claims, compiles a refutation plan that can falsify those claims without leaking accusations, calls Party B, and merges a claim graph whose edges are CONFIRMED, CONTRADICTED, UNTESTED, UNREACHABLE, or ABSTAIN. Silence and voicemail never count as confirmation.

The seed that judges see: ticket **FR-1842**, pallet **PL-9F21**, $18,000/hour cold-chain SLA. Warehouse says Dock 3. Driver says Dock 3 was empty.

## Value proposition

Existing phone-agent skills confirm one recipient or schedule one event. They do not compile a second call as a falsification test of the first. Dispatchers stare at two spoken truths and an email thread. CallParity emits one action card (RESTAGE_AND_RECALL, RELEASE_TRUCK, or HOLD_FOR_HUMAN) with quoted transcript spans on every edge.

Same loop for freight, prior-auth, construction materials, or insurance supplements. The reusable piece is the skill: `skills/callparity-refute`.

## Quickstart (compose)

    cp .env.example .env
    docker compose up -d --build

- Workbench: http://localhost:3000
- Health: http://localhost:8000/healthz
- Seeded tickets: **FR-1842** (contradiction), **FR-1900** (control / CONFIRMED), **FR-1888** (Party B voicemail / UNREACHABLE)

`USE_FIXTURES=true` is the default. Click Preview then Run parity on FR-1842. Expect pallet_staged CONTRADICTED, driver_arrived CONFIRMED, seal_recorded UNTESTED, action RESTAGE_AND_RECALL.

If Docker is not installed, use the local path below.

## Quickstart (local, no Docker)

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r apps/api/requirements.txt pytest
    export DATABASE_URL=sqlite+pysqlite:///./callparity.db
    export REDIS_OPTIONAL=true
    export USE_FIXTURES=true
    export PYTHONPATH=apps/api
    python scripts/seed_demo_data.py
    uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
    pytest -q

Vite in apps/web proxies /v1 to 127.0.0.1:8000. Seed is idempotent.

## Architecture

    UI -- POST /v1/tickets/{id}/preview --> API   (zero calls)
    UI -- POST /v1/tickets/{id}/parity  --> API
                                          | enqueue job (idempotency key)
                                          | Party A: CallePort.plan / run / get
                                          | ClaimExtractor
                                          | RefutationPlanner -> Party B task
                                          | Party B: CallePort.plan / run / get
                                          | GraphMerger
                                          + ActionCard + SSE

CallePort adapters: FixtureCalle when USE_FIXTURES=true; LiveCalleSdk when false (POST /v1/calls, GET /v1/calls/{id}). UI, planner, and tests never branch on the toggle except a fixture banner. GET /healthz checks Postgres, Redis, and CallePort.ping. Compose uses service DNS; no localhost inside containers.

## How this hits each judging criterion

**Impact (tie-break 1).** Specific $18k/hour cold-chain miss, not an abstract caller. Ops gets a restage/recall card with quoted words. FR-1900 proves the same machinery can release a truck when both sides agree.

**Idea (tie-break 2).** Cross-call refutation planner: hypotheses from A, minimum observable questions for B, disclosure budget. The second call is a test of the first. Not on the awesome-phone-call-agents list.

**Implementation (tie-break 3).** FastAPI, Pydantic, fixture + live adapters behind one port, HMAC-optional webhook (fail closed), authorization-based idempotency, structured JSON logs, SSE phases, pytest unit + integration + e2e demo loop.

**Demo (tie-break 4).** DEMO_SCRIPT.md is 90 seconds. Preview then Run parity. Fixtures so a busy signal cannot kill the punchline.

## Safety

- No call without stored consent on that party (403 otherwise).
- Preview is the default path when live keys are missing; USE_FIXTURES=true never dials.
- E.164 values are masked in logs (+1555***0001).
- Structured logging only (structlog JSON). No raw print in the API.
- Insulin is a cargo SKU, not a patient conversation. The planner refuses leaky phrasing.
- If CALLE_WEBHOOK_SECRET is set, missing or wrong HMAC is 401.
- POST /v1/jobs/{id}/cancel is honored before run_call.
- Unknown, voicemail, and low-confidence extraction never confirm.

## CALL-E runtime contract

CallParity invokes the runtime (or a fixture that implements the same port):

    plan_call -> run_call -> get_call_run

Developer API used by LiveCalleSdk: POST /v1/calls, GET /v1/calls/{call_id}, events poll, POST /v1/webhooks/calle.

Rules: consent and recording disclosure on every live call; masked fictional numbers in seeds; dry-run and fixture mode by default; fail-closed dispositions; host owns scheduling, CALL-E owns one-shot calls.

### Remaining blockers for a real live call (account/token, not code)

1. A CALL-E developer account and CALLE_API_TOKEN (Bearer).
2. USE_FIXTURES=false and a reachable CALLE_BASE_URL (not the fixture hostname).
3. Public HTTPS webhook URL plus CALLE_WEBHOOK_SECRET shared with CALL-E.
4. Real E.164 numbers with stored consent (seeds use +1555 fictionals).
5. Carrier / workspace credits and a from-number allocated on the CALL-E side.

Until those exist, ship and demo on fixtures. The live adapter raises if the token is missing.

## Layout

    apps/web                   Vite + React + Tailwind workbench
    apps/api                   FastAPI engine
    packages/shared            JSON Schema
    scripts/seed_demo_data.py
    skills/callparity-refute   Agent skill
    DEMO_SCRIPT.md PITCH_DECK.md SUBMISSION_TEXT.md

## Tests

    pytest -q
