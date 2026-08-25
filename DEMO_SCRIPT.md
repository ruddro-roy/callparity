# CallParity, 90-second demo script

**One line:** Two phones, one operational fact, a live contradiction graph.

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

## 1:00-1:20, controls: agreement and silence

**Do:** Click **FR-1900 control**, then **Run parity**. The card reads RELEASE_TRUCK. Click **FR-1888 voicemail**, then **Run parity**. The card reads HOLD_FOR_HUMAN.

**Say:**
"Same machinery, no contradiction: release the truck. And when the driver's phone goes to voicemail, silence is not confirmation. Unreachable holds for a human."

---

## 1:20-1:30, close

**Do:** Show the terminal: `docker compose up -d --build`, then `pytest -q` green.

**Say:**
"One compose command boots it, 49 tests cover it. The refutation planner is merged into awesome-phone-call-agents as ClaimKill, PR 220. The live adapter has placed a real CALL-E call on a public IVR line; the FR-1842 graph you saw runs on fixtures until two consenting parties are on the line."
