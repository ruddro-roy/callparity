# Devpost submission text

Paste-ready. No placeholders.

## Inspiration

We kept watching phone-agent demos that completed a single call and stopped. The operational pain is the opposite case: two people already spoke, they already disagree, and the system has no type for contradiction. Email is a graveyard of partial truths. The awesome-phone-call-agents list is full of scheduling, qualification, and one-recipient confirmation. Nobody compiles a second call as a falsification test of the first. CallParity started from that gap, and from a cold-chain ticket where an $18,000-an-hour pallet sat between Dock 3 and Dock 4 while both sides were sure.

## What it does

CallParity ingests a two-sided ops ticket and runs a closed loop:

1. Preview compiles the Party A extraction and the Party B refutation plan without placing a call.
2. Run parity (idempotent) executes Party A through CALL-E or a high-fidelity fixture behind the same CallePort.
3. Claims are typed: predicate, entities, time window, polarity, evidence span, confidence.
4. A planner builds the cheapest observable questions that can confirm or falsify those claims. The leak check is structural: a question is dropped when Party B could recover what Party A asserted from it, via reported speech, an asserted slot value like "dock 3", a verbatim quote fragment, or yes/no framing of the contested fact. The workbench shows the naive recap question being dropped, with reasons.
5. Party B is called against that schema. Voicemail and silence are first-class UNREACHABLE states; they never confirm.
6. A merger emits a claim graph and one action card (RESTAGE_AND_RECALL, RELEASE_TRUCK, or HOLD_FOR_HUMAN) with quoted spans on every edge.

The demo seed is ticket FR-1842 (contradiction), with FR-1900 (both sides agree) and FR-1888 (driver voicemail) as controls.

## How we built it

A small monorepo: FastAPI engine, Vite/React workbench, Postgres plus Redis, and a CallePort anti-corruption layer. USE_FIXTURES=true selects FixtureCalle; false selects LiveCalleSdk (POST /v1/calls, GET /v1/calls/{id}), and mocked-transport tests pin the exact wire format so CI never dials. Jobs enqueue with an idempotency key derived from ticket + party + claim-set hash. Transcripts live behind sha256 pointers. Webhooks are HMAC-optional and fail closed when a secret is configured. Logs are structured JSON with masked E.164s. `docker compose up -d --build` boots the whole thing seeded.

Then we hardened it to production grade, because an ops desk cannot run a demo. The Postgres schema is migrated at boot under an advisory lock, so replicas booting together serialize instead of racing DDL. A process killed mid-parity cannot wedge its ticket: on reboot the orphaned job converges to failed with a clear error and a deliberate retry starts fresh (nothing auto-redials — that would call humans back). Mutating routes are rate limited per operator-token fingerprint, and floods without a valid token are metered by client IP into 429s before the 401. The operator token rotates with zero downtime, each credential keeping its own audit fingerprint. Every response carries an X-Request-ID with exactly one access log line, phone redaction is fuzzed with Hypothesis property tests, and GET /metrics serves Prometheus counters. docs/OPERATIONS.md documents all of it for the operator who deploys it.

The reusable piece is ClaimKill, merged into the community list as CALLE-AI/awesome-phone-call-agents#220 (https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220): a standalone leak-drop planner with fixtures and twelve regression tests, mirrored byte-identical in this repo under skills/callparity-claimkill.

The live proof is one real human conversation: call_Sv3d5Dt3jj0YabV9IJZh7g (provider_call_id 504d94e961ec48578060a4ea7844a4f6), placed to a public diner, Tom's Restaurant. A person answered. The transcript beat: bot Hello / person Hello / bot What time do you close today / person Yeah. 11. / bot Thank you, bye. The structured result: reached=human, spoke_with_human=yes, closing_time=11. It is not an FR-1842 parity run, and we do not claim a live two-party run happened.

## Challenges we ran into

Keeping the second call from becoming a leaky recap of the first. A token blacklist ("warehouse said") was not enough, because a recap can leak without any banned phrase: "Can you confirm PL-9F21 left dock 3 at 06:40?" hands Party B the asserted dock and time. The leak check had to become structural, scoring attribution, asserted values, verbatim quote overlap, and polar framing of the contested fact, while keeping observable questions like "Which dock did you pull to?" alive. Treating voicemail as a first-class merger input so UNREACHABLE is proven by a fixture path, not by skipping Party B. Isolating CALL-E so the 90-second demo cannot die on a busy signal, without forking the product on USE_FIXTURES.

## Accomplishments that we're proud of

A judge can run one compose command, click Preview, then Run parity, and read the whole loop on one screen: Party A claims with quoted spans, the refutation plan with its dropped leak, Party B claims, the graph (pallet_staged CONTRADICTED, driver_arrived CONFIRMED, seal UNTESTED), and the RESTAGE_AND_RECALL card. The control ticket releases the truck; the voicemail ticket holds for a human. 165 tests cover the planner, merger, idempotency, webhook, live adapter wire format, live-record import, operator token and rotation, audit, redaction (including property-based fuzz), migrations, request ids, rate limiting, crash reconciliation, metrics, the operator script, the merged skill, and the e2e demo loop. The skill is merged upstream, not pending. And the whole thing survives contact with production: kill -9 the API mid-parity and it converges on reboot — scripts/production_proof.sh shows it in one minute.

## What's next

Run FR-1842 live against two consenting parties on a CALL-E workspace (the remaining blockers are account and consent, not code: token, public webhook, consent-backed numbers). Add domain packs that swap entity schemas without touching the planner (prior-auth, construction materials). Export the claim ledger into a TMS.
