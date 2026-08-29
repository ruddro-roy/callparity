# CallParity, 90-second demo script

**One line:** Two phones, one operational fact, a live contradiction graph.

**Recut note:** the submission tape stays v8 (https://www.youtube.com/watch?v=mLR6RTOi64c). Recut only if a single continuous pass shows the live import and the RESTAGE card in the first 20 seconds a stranger would feel. The FR-1842 "Import live records" control now makes that pass possible, and the beat below scripts it. No recut is uploaded from this PR.

**Recording setup:** `docker compose up -d --build`, then a 1920x1080 screen capture of http://localhost:3000 at 100% zoom. The whole demo is the running workbench. No slides, no stills. Fixtures are on (`USE_FIXTURES=true`), so the punchline never depends on a live carrier; the amber banner says so on screen.

**Seeded scenario:** Ticket `FR-1842`. Pallet `PL-9F21`, refrigerated insulin cartons as cargo. Warehouse (Party A) says it left Dock 3 at 06:40. Driver (Party B) says dock 3 was empty and they were waved off. SLA burn: $18k/hour of delayed cold-chain.

---

## 0:00-0:15, the problem on screen

**Do:** Nothing yet. FR-1842 is already loaded: ticket id, the fact question, the $18k/hour SLA chip, masked party numbers, empty columns.

**Say:**
"This is an $18,000-an-hour cold-chain miss. The warehouse says the pallet left Dock 3. The driver says Dock 3 was empty. Nobody is lying on purpose. Email will not close this. CallParity treats the disagreement as a testable claim graph."

---

## 0:15-0:35, Preview: zero calls

**Do:** Click **Preview (0 calls)**. Party A claims fill the left column. The refute plan fills the second column.

**Say:**
"Preview compiles everything without placing a call. Party A's transcript becomes typed claims with quoted spans and confidence. Then the planner writes the second call as a test of the first: the cheapest observable questions that could falsify what A said."

**Point at:** the "Dropped by leak check" entry. The struck-through question "Can you confirm PL-9F21 pallet staged at dock 3 and at 06:40?" with its reasons.

**Say:**
"This is the question a naive follow-up bot would ask. It hands the driver the warehouse's answer. The leak check drops it structurally, asserted values and polar framing, not a banned-word list. The driver never hears what the warehouse asserted."

---

## 0:35-1:00, Run parity: the punchline

**Do:** Click **Run parity**. Watch the rail status line: A planning, on the call, claims extracted; then B. Party B claims fill. The graph lights up. The action card flips.

**Say:**
"Both calls run through the same CallePort that drives the live CALL-E API. Party B answers observable questions only. The merger does the confrontation: pallet_staged CONTRADICTED, driver_arrived CONFIRMED, seal UNTESTED because nobody read it. One action card: restage PL-9F21 and recall the driver. Every edge quotes the words that produced it. A human owns the card."

---

## Alt open, live import in one pass (recut only)

**Do:** On FR-1842, click **Import live records** in the Live import bar. The action card flips to RESTAGE_AND_RECALL and the graph fills.

**Say:**
"These are two real CALL-E calls a human already answered, the warehouse and the driver. Import merges their records over GET, places no call, and shows no phone numbers. pallet_staged CONTRADICTED, driver_arrived CONFIRMED, one restage-and-recall card. That is the live proof path a dispatcher runs, gated behind an operator token."

---

## 1:00-1:20, controls: agreement and silence

**Do:** Click **FR-1900 control**, then **Run parity**. The card reads RELEASE_TRUCK. Click **FR-1888 voicemail**, then **Run parity**. The card reads HOLD_FOR_HUMAN.

**Say:**
"Same machinery, no contradiction: release the truck. And when the driver's phone goes to voicemail, silence is not confirmation. Unreachable holds for a human."

---

## 1:20-1:30, close

**Do:** Show the terminal: `docker compose up -d --build`, then `pytest -q` green.

**Say:**
"One compose command boots it, 165 tests cover it. The refutation planner is merged into awesome-phone-call-agents as ClaimKill, PR 220. The live adapter has placed a real CALL-E call where a person answered and gave a closing time; the FR-1842 graph you saw runs on fixtures until two consenting parties are on the line."

---

## Optional +60 seconds, production proof (when someone asks "is this real?")

This beat is for a judge or a CALL-E engineer who wants proof the engineering
survives contact with production. Every command below is copy-pasteable and
was run before it was written down.

**Do:** In a terminal at the repo root with the local venv active (README
local quickstart), run the one-shot proof. It boots a throwaway API on port
8123, never touches the compose demo, and cleans up after itself:

    bash scripts/production_proof.sh

**Say (while the crash section prints):**
"Mid-parity I kill dash nine the API process. The job row is frozen at running in the database. One reboot later that same job reads failed with an operator-facing error, the ticket is free, and a deliberate retry completes with the same restage-and-recall card. Nothing redials on its own; in live mode that would call humans back."

**Point at:** the `429 retry_after=60` lines in the rate-limit section.

**Say:**
"Every mutating route shares a per-operator budget, and a flood without a valid token is metered by client IP before the 401. Spam gets throttled; the real operator keeps their budget."

**Then, against the running compose stack:**

    curl -s http://localhost:8000/metrics

**Say:**
"Observable like a production service: requests by status class, jobs by terminal status. Counts only, nothing sensitive."

**Optional, same stack — walk the default rate limit (60 per minute) into a 429:**

    for i in $(seq 1 61); do curl -s -o /dev/null -w '%{http_code}\n' -X POST \
      http://localhost:8000/v1/tickets/FR-1842/preview \
      -H "Authorization: Bearer ${OPERATOR_TOKEN:-callparity-demo-operator}"; done | uniq -c

Expect sixty 200s and one 429. The Retry-After header on the denied request
says when the budget returns.
