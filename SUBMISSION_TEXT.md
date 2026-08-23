# Devpost submission text

Paste-ready. No placeholders.

## Inspiration

We kept watching phone-agent demos that successfully completed a single call and then stopped. The operational pain we actually hear from dispatchers is the opposite: two people already spoke, they already disagree, and the system has no type for contradiction. Email is a graveyard of partial truths. The awesome-phone-call-agents list is full of scheduling, qualification, and one-recipient confirmation. Nobody compiles a second call as a falsification test of the first. CallParity started from that gap, and from a cold-chain ticket where an $18,000-an-hour pallet sat between Dock 3 and Dock 4 while both sides were sure.

## What it does

CallParity ingests a two-sided ops ticket and runs a closed loop:

1. Preview compiles the Party A extraction and the Party B refutation plan without placing a call.
2. Run parity (idempotent) executes Party A through CALL-E or a high-fidelity fixture behind the same CallePort.
3. Claims are typed: predicate, entities, time window, polarity, evidence span, confidence.
4. A planner builds the cheapest observable questions that can confirm or falsify those claims without leaking Party A's accusations.
5. Party B is called against that schema. Voicemail and silence are first-class UNREACHABLE states; they never confirm.
6. A merger emits a claim graph and one action card (RESTAGE_AND_RECALL, RELEASE_TRUCK, or HOLD_FOR_HUMAN) with quoted spans.

The demo seed is ticket FR-1842 (contradiction), FR-1900 (both sides agree), and FR-1888 (driver voicemail).

## How we built it

A small monorepo: FastAPI engine, Vite/React workbench, Postgres plus Redis, and a CallePort anti-corruption layer. USE_FIXTURES=true selects FixtureCalle; false selects LiveCalleSdk (POST /v1/calls, GET /v1/calls/{id}). Jobs enqueue with an idempotency key derived from ticket + party + claim-set hash. Transcripts live behind sha256 pointers. Webhooks are HMAC-optional and fail closed when a secret is configured. Logs are structured JSON with masked E.164s. The reusable artifact is skills/callparity-refute, a skill folder that wraps the planner for the awesome-phone-call-agents contribution.

## Challenges we ran into

Keeping the second call from becoming a leaky recap of the first. The disclosure budget and leak scorer had to discard any question that would reveal Party A's accusation, while still covering each hypothesis. Treating voicemail as a first-class merger input so UNREACHABLE is proven by a fixture path, not by skipping Party B. Isolating CALL-E so the 90-second demo cannot die on a busy signal, without forking the product on USE_FIXTURES. Shipping HMAC verification that is optional in fixtures and fail-closed in production. Writing a live adapter that is honest about the remaining account and token blockers instead of pretending a localhost token exists.

## Accomplishments that we're proud of

A judge can click Preview, then Run parity, and see the exact DEMO_SCRIPT outcomes: pallet_staged CONTRADICTED, driver_arrived CONFIRMED, seal UNTESTED, action RESTAGE_AND_RECALL, plus a control ticket that releases the truck and a voicemail ticket that holds for a human. The planner, merger, idempotency, webhook, and e2e demo loop are unit- and integration-tested. The skill folder is contribution-shaped. The live path is one env toggle plus a real CALL-E token away.

## What's next

Connect a real CALL-E workspace (CALLE_API_TOKEN, public webhook, consent-backed numbers) and run FR-1842 against two humans who already agreed to be recorded. Add a prior-auth domain pack that reuses the planner. Export the claim ledger into a TMS. Then PR skills/callparity-refute to awesome-phone-call-agents and apps/typescript/callparity as the reference workbench.
