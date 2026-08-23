# CallParity - 90-second demo script

**One line:** Two phones, one operational fact, a live contradiction graph.

**Seeded scenario (always on):** Ticket `FR-1842`. Pallet `PL-9F21` of 40 refrigerated insulin cartons. Warehouse (Party A) says it left Dock 3 at 06:40. Driver (Party B) says they were waved off because the pallet was never staged. Ops is stuck in email. SLA burn: $18k/hour of delayed cold-chain.

Demo boots from fixtures (`USE_FIXTURES=true`) so the punchline never depends on a live carrier. A live CALL-E path is one toggle away.

---

## 0:00-0:20 - The visceral problem

**On screen:** Ops console, ticket FR-1842. Two chat threads and a stale TMS status that disagree. Clock showing 47 minutes past pickup.

**Say:**
"This is a $18,000-an-hour cold-chain miss. The warehouse says the pallet left. The driver says it never existed on the dock. Nobody is lying on purpose. Both sides are working from a different clock and a different door. Email will not close this."

**Show:** Highlight the two conflicting sentences. Show the cost ticker.

---

## 0:20-0:45 - The novel mechanism

**On screen:** Split view. Left: typed claim graph extracted from Party A (warehouse). Right: a *refutation plan* compiled for Party B (driver), not a second copy of the same script.

**Say:**
"CallParity does not run two generic follow-up calls. The first CALL-E run returns structured claims with transcript spans. A planner then compiles the cheapest set of questions that could *falsify* those claims. The second call is a test, not a recap."

**Show:**
- Claim `pallet_staged_dock_3 @ 06:40` (confidence 0.81, span highlighted).
- Compiled B-questions: "Which dock did you pull to?", "Did you see PL-9F21 on a jack?", "Who waved you off?"
- Goal text and result schema that will be sent to CALL-E `plan_call` -> `run_call`.

---

## 0:45-1:15 - The live punchline

**On screen:** Two live call rails (fixture playback that looks like CALL-E status: planning -> ringing -> talking -> structured result). Then the merge.

**Do:**
1. Click **Run parity** on FR-1842 (idempotent).
2. Watch Party A complete. Claims appear as nodes.
3. Watch Party B compile and run automatically.
4. The graph lights: one CONFIRMED (driver did arrive), one CONTRADICTED (pallet on Dock 3), one UNTESTED (seal number never asked).

**Say:**
"Fourteen seconds after the second hang-up, ops has a ticket they can act on: restage PL-9F21 at Dock 3, call the driver back to door, do not resend the truck empty. Every edge quotes the words that produced it."

**Show:** Action card auto-generated: `RESTAGE_AND_RECALL`. Evidence chips. Latency and token telemetry in the footer.

---

## 1:15-1:30 - Architecture, scale, market

**On screen:** One diagram. Vite workbench -> FastAPI planner -> Redis job queue -> CALL-E SDK (`plan_call` / `run_call` / `get_call_run` + webhook) -> Postgres claim ledger. Fixture adapter sits behind the same port.

**Say:**
"Same loop for any two-sided operational fact: freight, prior-auth, construction materials, insurance supplements. We isolate CALL-E behind a queue and high-fidelity fixtures so the demo never dies on a busy signal. One compose command boots it. The reusable piece is the skill: compile a refutation call from another party's structured claims."

**Close card:** `docker compose up --build` . PR destination `apps/typescript/callparity` + `skills/callparity-refute`.
