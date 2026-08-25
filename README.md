# CallParity

**Two phones. One operational fact. A live contradiction graph.**

CallParity turns a two-sided ops ticket into a test. It places (or fixtures) a CALL-E call to Party A, extracts typed claims, compiles a refutation plan that can falsify those claims without leaking accusations, calls Party B, and merges a claim graph whose edges are CONFIRMED, CONTRADICTED, UNTESTED, UNREACHABLE, or ABSTAIN. Silence and voicemail never count as confirmation.

The seed that judges see: ticket **FR-1842**, pallet **PL-9F21**, $18,000/hour cold-chain SLA. Warehouse says Dock 3. Driver says Dock 3 was empty.

![CallParity workbench after the FR-1842 fixture run](demo/workbench-fr1842.png)

## Value proposition

Existing phone-agent skills confirm one recipient or schedule one event. They do not compile a second call as a falsification test of the first. Dispatchers stare at two spoken truths and an email thread. CallParity emits one action card (RESTAGE_AND_RECALL, RELEASE_TRUCK, or HOLD_FOR_HUMAN) with quoted transcript spans on every edge.

Same loop for freight, prior-auth, construction materials, or insurance supplements. The reusable piece is the ClaimKill skill, merged into the community list as [CALLE-AI/awesome-phone-call-agents#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220) and mirrored byte-identical in `skills/callparity-claimkill`.

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

Vite in apps/web proxies /v1 to 127.0.0.1:8000 (`npm install && npm run dev`). Seed is idempotent.

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

CallePort adapters: FixtureCalle when USE_FIXTURES=true; LiveCalleSdk when false (POST /v1/calls, GET /v1/calls/{id}). UI, planner, and tests never branch on the toggle except a fixture banner. GET /healthz checks Postgres, Redis, and CallePort.ping, and reports the mode. Compose uses service DNS; no localhost inside containers.

## The leak check is structural, not a token list

The planner never forwards Party A's accusation. A candidate question for Party B is dropped when B could recover what A asserted from it:

- **attribution**: reported speech of a recap subject ("the warehouse said", "according to...").
- **asserted_value**: it names a slot value that exists only because A said it (dock 3, 06:40), or repeats three or more consecutive words of A's quoted span.
- **polar_hypothesis**: yes/no framing of a contested predicate ("Was the pallet staged?"). Questions about B's own perception ("Did you see PL-9F21 on a jack?") stay.
- **blame / clinical**: second-person fault language, or cargo labels drifting into patient content.

The planner also generates the naive recap a follow-up bot would ask ("Can you confirm PL-9F21 pallet staged at dock 3 and at 06:40?") and shows it dropped in the workbench, with reasons. `tests/test_planner.py` proves the recap always drops, the golden observables always survive, a ticket without its critical entity id refuses to plan, and voicemail never confirms.

## How this hits each judging criterion

**Impact (tie-break 1).** Specific $18k/hour cold-chain miss, not an abstract caller. Ops gets a restage/recall card with quoted words. FR-1900 proves the same machinery can release a truck when both sides agree.

**Idea (tie-break 2).** Cross-call refutation: hypotheses from A, minimum observable questions for B, disclosure budget, structural leak check. The second call is a test of the first. Merged into awesome-phone-call-agents as [#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220).

**Implementation (tie-break 3).** FastAPI, Pydantic, fixture + live adapters behind one port, mocked wire-format tests for POST /v1/calls, HMAC-optional webhook (fail closed), authorization-based idempotency, structured JSON logs, SSE phases, 70 tests across planner, merger, idempotency, webhook, live adapter, operator script, skill, and the e2e demo loop (the compose smoke skips when the stack is down).

**Demo (tie-break 4).** One screen: A claims, refute plan with the dropped leak, B claims, action card, merged graph. DEMO_SCRIPT.md walks it in 90 seconds. Fixtures so a busy signal cannot kill the punchline.

## Live CALL-E proof

The live adapter has placed one real CALL-E call: `call_id 855acdb09cbb4b62a3c95c51988727b8`, a public restaurant-hours IVR check. The numbers used were released afterward. That call proves the adapter, token, and polling path work against the real API. It is not an FR-1842 parity run; no live two-party FR-1842 call has happened.

## Place one live hours call (operator path)

`scripts/live_hours_call.py` places one outbound call that asks a public business for its hours of operation. It is a separate operator path. FR-1842 / FR-1900 / FR-1888 stay fixtures, and compose stays `USE_FIXTURES=true`, so judges never need live keys.

Secrets and the destination live only in the shell environment. Never commit a token or a phone number. `.env` is gitignored and the seeds use fictional +1555 numbers.

    export CALLE_BASE_URL=      # your CALL-E workspace API base URL
    export CALLE_API_TOKEN=     # token from that workspace
    export CALLE_LIVE_TO_PHONE= # destination in E.164: + then 8 to 15 digits
    export CALLE_CONSENT=yes    # confirms the callee may be dialed and recorded
    python scripts/live_hours_call.py

The script refuses to dial when a variable is missing, when the phone is not E.164, or when consent is not `yes`. It exits 2 and names the variable to fix. On success stdout carries only two kinds of lines, `call_id <id>` and `status <status>`. Adapter logs go to stderr with the destination masked, and the token is never printed.

The workspace's default outbound number places the call. Renting or assigning a dedicated from-number is an operator step in the CALL-E workspace, outside this repo. The POST body carries no `from_number` field because the pinned wire format (SPECIFICATION.md, `tests/test_live_adapter.py`) does not define one, so a `CALLE_FROM_NUMBER` variable would be dead config and is not read.

## Safety

- No call without stored consent on that party (403 otherwise).
- The hours script refuses to dial without CALLE_CONSENT=yes, and its errors never echo the destination or the token.
- Preview is the default path when live keys are missing; USE_FIXTURES=true never dials.
- E.164 values are masked in logs and in the workbench (+1555***0001).
- Structured logging only (structlog JSON). No raw print in the API.
- Insulin is a cargo SKU, not a patient conversation. The leak check refuses clinical drift.
- If CALLE_WEBHOOK_SECRET is set, missing or wrong HMAC is 401.
- POST /v1/jobs/{id}/cancel is honored before run_call.
- Unknown, voicemail, and low-confidence extraction never confirm.

## CALL-E runtime contract

CallParity invokes the runtime (or a fixture that implements the same port):

    plan_call -> run_call -> get_call_run

Developer API used by LiveCalleSdk: POST /v1/calls, GET /v1/calls/{call_id}, events poll, POST /v1/webhooks/calle. The wire format is pinned by mocked-transport tests in `tests/test_live_adapter.py`; CI never dials.

Rules: consent and recording disclosure on every live call; masked fictional numbers in seeds; dry-run and fixture mode by default; fail-closed dispositions; host owns scheduling, CALL-E owns one-shot calls.

### Remaining blockers for a live FR-1842 run (account/consent, not code)

The hours call above needs only a token, a base URL, a destination, and consent. A live two-party FR-1842 parity run also needs:

1. USE_FIXTURES=false, CALLE_BASE_URL, and CALLE_API_TOKEN in .env.
2. Public HTTPS webhook URL plus CALLE_WEBHOOK_SECRET shared with CALL-E.
3. Real E.164 numbers with stored consent on both parties (seeds use +1555 fictionals).
4. Carrier / workspace credits and a from-number allocated on the CALL-E side.

Until those exist, ship and demo on fixtures. The live adapter refuses to plan, run, or poll while CALLE_API_TOKEN or CALLE_BASE_URL is missing, and names the variable to set.

## Layout

    apps/web                     Vite + React + Tailwind workbench
    apps/api                     FastAPI engine
    packages/shared              JSON Schema
    scripts/seed_demo_data.py
    scripts/live_hours_call.py   One live hours-of-operation call (operator path)
    skills/callparity-claimkill  Skill merged upstream as #220, mirrored byte-identical
    demo/                        Workbench screenshot
    DEMO_SCRIPT.md PITCH_DECK.md SUBMISSION_TEXT.md

## Tests

    pytest -q
