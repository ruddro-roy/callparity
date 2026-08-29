# CallParity pitch deck

Seven slides. Speak each in about 20 seconds. The 90-second product demo is DEMO_SCRIPT.md.

## Slide 1 - Problem

Two humans already disagree on the phone. Email will not close it.

A dispatcher owns a ticket where Party A and Party B each hold a partial, spoken truth. TMS status is stale. SLA is burning ($18,000/hour on the seed: refrigerated insulin pallet PL-9F21). Existing voice agents confirm one recipient or schedule one event. They treat utterances as tasks, not as claims that can contradict.

Nobody has to be lying. Different clock, different door, same pallet.

## Slide 2 - Market

Every two-sided operational fact is a market.

- Cold-chain and high-value freight (detention, restage, empty miles)
- Hospital prior-auth and bed control (two offices, one clinical fact)
- Construction materials (yard vs. driver vs. GC)
- Insurance supplements (adjuster vs. contractor)

Buyers: ops coordinators and exception desks who already pay for a TMS/WMS and still call people. Willingness to pay tracks SLA burn, not AI minutes. Adjacent TAM is the exception-management layer on top of voice infrastructure, not the carrier itself.

## Slide 3 - Solution

Cross-call refutation. The second call is a test, not a recap.

1. Ingest a two-sided ticket.
2. Call Party A. Extract typed Claim records (predicate, entities, time window, polarity, evidence span, confidence).
3. Compile the cheapest question set that can confirm or falsify each hypothesis without leaking A's accusations.
4. Call Party B against a strict result schema.
5. Merge a graph: CONFIRMED | CONTRADICTED | UNTESTED | UNREACHABLE | ABSTAIN.
6. Emit one action card. Human owns commitments.

Silence, voicemail, and low-confidence extraction are first-class. They never confirm.

## Slide 4 - Architecture

One port, two adapters, one compose file.

Workbench (Vite/React) -> FastAPI (planner, extractor, merger, jobs) -> Redis + Postgres -> CallePort -> FixtureCalle or LiveCalleSdk (plan_call / run_call / get_call_run + HMAC webhook).

Idempotency is derived from ticket + party + claim-set hash, not from the HTTP attempt. Preview compiles both plans and places zero calls. The schema is boot-migrated (Alembic under a Postgres advisory lock) and crash-orphaned jobs reconcile at startup, so replicas can race and processes can die without wedging a ticket.

## Slide 5 - Competitive Advantage

Two generic follow-up skills: same script twice, no falsification, accusations leak.
Human dispatcher + email: slow, SLA burn, no claim ledger.
AI that calls the vendor: one-sided, no graph, confirms whatever it hears.
Awesome-list skills (schedule, qualify, dispatch): already shipped, not a two-call test.

Moat is the refutation compiler (disclosure budget + set-cover + fail-closed merger) plus a fixture-safe demo that still uses the real CALL-E port.

## Slide 6 - Business Model

- Pilot: per-desk seat plus usage on live CALL-E minutes (we do not resell minutes).
- Production: annual ops-desk license tied to ticket volume, plus the ClaimKill skill already merged into awesome-phone-call-agents ([#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220)).
- Expansion: domain packs (freight, prior-auth, construction) that swap entity schemas, not the planner.
- Human remains the commitment owner. We sell parity, not authority.

## Slide 7 - Roadmap

Now (hackathon ship). Fixture-complete FR-1842 / FR-1900 / FR-1888. ClaimKill skill merged upstream ([#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220)); one real CALL-E call placed through the live adapter, and two human-answered calls on the FR-1842 fact pattern merged through the GET-only import path. Hardened like a service, not a demo: boot-migrated schema under an advisory lock, crash-orphan job reconciliation, pre-auth rate limiting, zero-downtime token rotation, request-id tracing, property-fuzzed phone redaction, /metrics, 165 offline tests, and an operations guide (docs/OPERATIONS.md).

Next 30 days. Wire a real CALL-E account (CALLE_API_TOKEN), public webhook, consent-backed numbers. One live freight desk.

Next 90 days. Domain pack 2 (prior-auth). Streaming tokens in the workbench. Human override analytics.

Year one. Claim-ledger export into the customer TMS. Multi-party graphs. On-prem compose for regulated desks.
