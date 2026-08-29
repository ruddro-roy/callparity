# Devpost submission fields

Paste each section into the matching Devpost form field. Two values are left
for the owner to fill in:

- Video URL: `<<OWNER: paste the YouTube URL of the demo video here>>`
- CALL-E account email: `<<OWNER: paste the CALL-E account email here>>`

## Project name

CallParity

## Tagline

Turns two disagreeing phone calls into one action card

The tagline is 54 characters.

## Inspiration

Phone-agent demos complete one call and stop. The expensive case at an ops
desk is the opposite one. Two people already spoke, they already disagree,
and no system has a type for that. Our seed ticket is that case exactly: a
refrigerated insulin pallet, PL-9F21, burning an $18,000-per-hour SLA while
the warehouse insists it staged the pallet at Dock 3 and the driver insists
Dock 3 was empty. Nobody has to be lying. Different clock, different door,
same pallet. Email will not close it.

The community skill list, awesome-phone-call-agents, is full of scheduling,
qualification, and one-recipient confirmation. Nothing there compiles a
second call as a falsification test of the first. We built CallParity to do
that.

## What it does

CallParity ingests a two-sided ops ticket and runs one loop. It calls Party
A through CALL-E and extracts typed claims with a predicate, entities, a time
window, polarity, an evidence span, and a confidence score. A planner then
writes the second call as a test of the first: the cheapest observable
questions that could falsify what A said. A structural leak check drops any
question that would tell Party B what Party A asserted. It catches reported
speech, asserted slot values like "dock 3", three-word fragments of A's
quotes, and yes/no framing of the contested fact. The workbench shows the
naive recap question a follow-up bot would ask, struck through, with the
reasons it was dropped. Party B answers against a strict result schema. A
merger emits a claim graph whose edges read CONFIRMED, CONTRADICTED,
UNTESTED, UNREACHABLE, or ABSTAIN, and one action card: RESTAGE_AND_RECALL,
RELEASE_TRUCK, or HOLD_FOR_HUMAN. Every edge quotes the transcript words
that produced it. Voicemail and silence never confirm. A human owns the
card.

On the seed ticket FR-1842 the graph marks pallet_staged CONTRADICTED and
the card says restage and recall. FR-1900 is the control where both sides
agree and the truck is released. FR-1888 sends the driver to voicemail and
holds for a human.

The live proof runs on record, not on a fixture. We placed two real CALL-E
calls on the FR-1842 fact pattern, one to the warehouse role and one to the
driver role, and a person answered each. Their structured results disagree
on whether PL-9F21 is staged at Dock 3. The import endpoint fetches both
records over GET, merges them, and produces the same RESTAGE_AND_RECALL
card. The import path has no dial branch, so it cannot place a call.

## How we built it

A small monorepo. FastAPI engine, React workbench built with Vite and
Tailwind, Postgres and Redis, and one CallePort with two adapters.
USE_FIXTURES=true serves the recorded fact patterns; false uses the live
Calls API, POST /v1/calls to create and GET /v1/calls/{id} to poll.
Mocked-transport tests pin the exact wire format, and CI never receives
live credentials, so no pipeline can dial. One compose command boots the
whole thing seeded.

Then we hardened it, because an ops desk cannot run a demo. Alembic migrates
the schema at boot under a Postgres advisory lock, so replicas booting
together serialize instead of racing DDL; we proved it with four concurrent
migrator processes on Postgres 16. Kill -9 the API mid-parity and on reboot
the orphaned job converges to failed with a clear operator error, and the
ticket is free for a deliberate retry. Nothing redials on its own, because
in live mode that would call humans back. The five mutating routes share a
rate limit per operator-token fingerprint, and a flood without a valid token
is metered by client IP into 429s before the 401 goes out. The operator
token rotates with zero downtime through comma-separated values, each
keeping its own audit fingerprint. Every response carries an X-Request-ID,
logs are structured JSON with phone numbers redacted, and Hypothesis fuzzes
the redaction with property-based tests. GET /metrics serves Prometheus
text, counts only. docs/OPERATIONS.md documents every environment variable
and runtime behavior for the operator who deploys it, and
scripts/production_proof.sh runs the crash drill, the rate-limit
demonstration, and a metrics scrape in about 60 seconds.

## Challenges we ran into

The leak check. A token blacklist was not enough, because a recap can leak
without any banned phrase. "Can you confirm PL-9F21 left dock 3 at 06:40?"
contains no forbidden word and still hands the driver the asserted dock and
time. The check had to become structural. It scores attribution, asserted
slot values, verbatim quote overlap, and polar framing of the contested
fact, while keeping perception questions like "Which dock did you pull to?"
alive.

Crash recovery had one hard constraint: never re-execute automatically,
because a retry in live mode dials a human back. So the reconciler marks
orphans failed, releases the idempotency key, and waits for an operator.

Rate limiting had an ordering problem. Metering after authentication means a
forged-token flood gets unmetered 401s and can hammer the token check
forever. We meter unauthenticated requests by client IP before the 401 goes
out, so spam gets throttled and the real operator keeps a separate budget.

## Accomplishments we're proud of

The refutation planner is merged into CALLE-AI/awesome-phone-call-agents as
PR 220. Merged, not pending. Two humans answered real CALL-E calls on the
FR-1842 fact pattern, and importing their records produces the
restage-and-recall card without placing a new call. 165 offline tests and
one skip cover the planner, merger, idempotency, webhook, live adapter wire
format, live-record import, operator auth and rotation, audit, redaction
fuzz, migrations, request ids, rate limiting, crash reconciliation, metrics,
and the end-to-end demo loop. A judge runs one compose command and reads the
whole loop on one screen. And when a judge asks "is this real",
scripts/production_proof.sh answers with a live kill -9 and the job
converging on reboot, in about a minute.

## What we learned

Falsification is a planning constraint, not a prompt. The useful second call
asks what B could have observed and never what A asserted, and enforcing
that takes structure, not a word list. Fail-closed defaults have to be
designed in from the start: silence never confirms, unknown is not success,
unset credentials deny. And production behaviors are testable if you build
for it. A SIGKILL drill, racing migrators, and an unauthenticated flood all
run in CI as ordinary tests, so the claims in this text are assertions the
suite executes.

## What's next

A live two-party FR-1842 run needs an account and consent, not code: a
CALL-E workspace token, a public webhook URL, and consent-backed numbers for
both parties. After that, domain packs that swap entity schemas without
touching the planner, starting with hospital prior-auth and construction
materials, and export of the claim ledger into the customer's TMS.

## Built with

Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis, structlog, httpx, uvicorn, React, Vite, Tailwind CSS, Docker Compose, pytest, Hypothesis, CALL-E Calls API
