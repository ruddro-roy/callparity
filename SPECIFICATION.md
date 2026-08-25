# CallParity specification

## 1. Problem

Phone work fails when two parties each hold a partial, spoken truth and no system treats those utterances as claims that can contradict. Existing CALL-E skills confirm one recipient or schedule one event. They do not compile a second call as a falsification test of the first.

**Primary user:** a dispatcher / ops coordinator staring at a ticket that two humans already disagree about on the phone.

**Primary loop:** ingest a two-sided ticket -> call Party A -> extract typed claims -> compile a refutation plan for Party B -> call Party B -> merge a claim graph -> emit one action card.

## 2. Core innovation

**Cross-call refutation planner.**

After CALL-E returns a structured result + transcript for Party A, CallParity:

1. Normalizes answers into `Claim` records (`predicate`, `entity_ids`, `time_window`, `polarity`, `evidence_span`, `confidence`).
2. Builds a hypothesis set H from those claims.
3. Compiles the minimum question set Q_B that can confirm or falsify each hypothesis, subject to a disclosure budget (do not leak Party A's accusations; ask observable facts only).
4. Executes Q_B as a CALL-E task with a strict result schema.
5. Merges A and B into a graph whose edges are `CONFIRMED | CONTRADICTED | UNTESTED | UNREACHABLE | ABSTAIN`.

Silence, voicemail, and low-confidence extraction are first-class states. They never count as confirmation.

This is the non-trivial mechanism. Everything else is product around it.

## 3. Why this wins the rubric

Equal weights (25% each). Internal utility also applied Novelty 30 / Depth 30 / Impact 25 / 90s-demo 15.

| Concept | Novelty | Depth | Impact | Demo 90s | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| **A. CallParity** (locked) | 28 | 28 | 23 | 13 | **92** | Two-call test. Fixture-safe punchline. Skill merged upstream as [#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220). |
| B. Invoice voice 3-way match | 23 | 25 | 25 | 13 | 86 | Practical, closer to AI that calls the vendor. |
| C. Exception-only voice gate | 21 | 24 | 24 | 14 | 83 | Strong ops story, weaker novelty vs existing escalation skills. |

Avoided: appointment scheduling, lead qualification, generic callbacks, dispatch, approval gates, line canaries - already on [awesome-phone-call-agents](https://github.com/CALLE-AI/awesome-phone-call-agents).

Prize targeting: one submission can win only one prize. CallParity is built to score both practical (real two-sided ops tickets) and innovative (refutation compiler). Tie-break order is Impact -> Idea -> Implementation -> Demo, so the ticket must stay specific (cold-chain pallet), not abstract.

## 4. Constraints from CALL-E

Runtime contract (must actually invoke, not mention):

```
plan_call -> run_call -> get_call_run
```

plus Developer API fallback:

| Method | Path | Use |
|---|---|---|
| POST | `/v1/calls` | Create one-recipient task |
| GET | `/v1/calls/{call_id}` | Status, summary, structured result, transcript |
| GET | `/v1/calls/{call_id}/events` | Event stream |
| POST | `/calle/webhook` | Terminal result |

Rules we inherit from the community repo:

- Consent and recording disclosure on every live call.
- Masked / fictional numbers in seeds.
- Dry-run and fixture mode by default.
- Idempotency from the authorization (ticket + party + claim-set hash), not from the HTTP attempt.
- Fail-closed dispositions. Unknown is not success.
- Host owns scheduling; CALL-E owns one-shot calls.

## 5. System architecture

Monorepo:

```
/apps/web          Vite + React + Tailwind workbench
/apps/api          FastAPI + Python 3.12, Pydantic v2
/packages/shared   JSON Schema for claims, tickets, actions
/skills/callparity-claimkill   Skill merged upstream as #220, mirrored byte-identical
```

Containers (`docker-compose.yml`):

| Service | Image role |
|---|---|
| `web` | Vite / nginx workbench |
| `api` | FastAPI / uvicorn |
| `postgres` | tickets, claims, call runs, action cards |
| `redis` | queue + idempotency locks + payload pointers |

All in-cluster hostnames come from env (`API_URL`, `POSTGRES_HOST`, `REDIS_URL`, `CALLE_BASE_URL`). No `localhost` inside containers.

`GET /healthz` on API checks Postgres, Redis, and CallePort (or fixture) connectivity.

## 6. Data models

See `packages/shared/schemas`. Ticket FR-1842, Claim records, graph edges (`CONFIRMED | CONTRADICTED | UNTESTED | UNREACHABLE | ABSTAIN`), and action cards (`RESTAGE_AND_RECALL`, `RELEASE_TRUCK`, `HOLD_FOR_HUMAN`, `REDIAL_A`, `REDIAL_B`). Human owns commitments.

## 7. API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Deep health (db, redis, calle) |
| POST | `/v1/tickets` | Create ticket |
| GET | `/v1/tickets/{id}` | Ticket + latest graph |
| POST | `/v1/tickets/{id}/parity` | Start or resume the two-call loop |
| GET | `/v1/jobs/{id}` | Job status |
| GET | `/v1/tickets/{id}/events` | SSE |
| POST | `/v1/webhooks/calle` | Terminal CALL-E webhook (signed) |
| POST | `/v1/tickets/{id}/preview` | Compile both plans, place zero calls |

## 8. CallePort

`LiveCalleSdk` and `FixtureCalle` both implement plan / run / get / ping. `USE_FIXTURES=true|false` selects the adapter.

## 9. Planner algorithm

1. Drop claims with `confidence < 0.45` into `ABSTAIN`.
2. Generate candidate observables Party B could have seen, plus the naive recap a follow-up bot would ask.
3. Structural leak check: drop a question when Party B could recover what A asserted from it (reported speech of a recap subject, an asserted slot value, a verbatim 3-word quote fragment, yes/no framing of a contested predicate, blame or clinical language). Perception questions about B's own observations stay.
4. Greedy set-cover until each claim has a covering question or is `UNTESTED`.
5. Render CALL-E goal + JSON Schema. Refuse if spoken-time budget is exceeded or the ticket has no critical entity id.

## 10-15. UI, safety, demo, tests, submission

Workbench: one screen. Ticket header, Party A claims, refute plan with dropped leaks, Party B claims, action card, merged graph with quoted spans. Preview and Run parity buttons.

Safety: consent required; preview default; mask E.164 in logs and UI; structured logs; cancel before `run_call`.

Seed: `scripts/seed_demo_data.py` inserts FR-1842, FR-1900, FR-1888.

Tests: planner leak check, merger, idempotency, webhook, live adapter wire format (mocked), merged skill regressions, e2e demo loop.

Skill: `skills/callparity-claimkill`, merged upstream as [#220](https://github.com/CALLE-AI/awesome-phone-call-agents/pull/220).
