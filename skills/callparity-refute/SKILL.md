---
name: callparity-refute
description: >
  Compile a disclosure-budgeted CALL-E task that can falsify another party's
  structured claims. Use after Party A returns a structured result and transcript.
  Never leak accusations. Treat voicemail and silence as UNREACHABLE, not success.
license: MIT
metadata:
  author: CallParity
  runtime: plan_call -> run_call -> get_call_run
  awesome_list: awesome-phone-call-agents
---

# callparity-refute

Compile the cheapest CALL-E goal and result schema that can confirm or falsify a set of Party A claims, then merge Party B's structured result into a claim graph.

## When to use

- Two parties already disagree about one operational fact (location, staging, arrival, seal, authorization).
- You have Party A's structured result and transcript spans.
- You must not disclose Party A's accusations to Party B.
- You need a closed action for a human (RESTAGE_AND_RECALL, RELEASE_TRUCK, HOLD_FOR_HUMAN).

Do not use this skill for generic follow-up, appointment scheduling, or lead qualification.

## Inputs

- ticket: id, entities (must include the critical entity id, e.g. pallet), parties with E.164 and consent.
- claims_a: list of id, predicate, entity_ids, slot, polarity, confidence, evidence_span.
- disclosure_budget: max questions (default 4).

## Procedure

1. Drop claims with confidence below 0.45 into ABSTAIN.
2. For each remaining claim, generate observable questions Party B could have seen (who / what / where / when).
3. Discard any question that leaks an accusation. See references/disclosure.md.
4. Greedy set-cover until each live claim has at least one covering question or is UNTESTED.
5. Render CALL-E goal text and JSON Schema. Refuse if spoken-time budget (about 90s) is exceeded or a critical entity id is missing.
6. Invoke the runtime, do not merely mention it: plan_call then run_call then get_call_run.
7. Merge A and B. Statuses: CONFIRMED, CONTRADICTED, UNTESTED, UNREACHABLE, ABSTAIN.
   Voicemail, empty transcript, or unreachable true means UNREACHABLE and HOLD_FOR_HUMAN.

## Consent and safety

- Refuse to run_call without stored consent on that party.
- Disclose recording on the live call (CALL-E host policy).
- Mask E.164 in logs.
- Insulin and similar tokens are cargo labels, not clinical advice.

## Output

Planner payload handed to plan_call: to_phones (Party B only), goal (observables only), result_schema keyed to hypothesis ids.

## References

- references/planner.md - algorithm and golden FR-1842 questions.
- references/disclosure.md - leak tokens.
- references/runtime.md - CALL-E contract, fixtures, webhook HMAC.
- scripts/ - host-side seed note; this skill does not shell out during a live call.

## Contribution note

This folder is the intended PR payload for awesome-phone-call-agents: SKILL.md, references/, scripts/. The engine that executes it lives in the CallParity API (app.services.planner, app.services.merger).
