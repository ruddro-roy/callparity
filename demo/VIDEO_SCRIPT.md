# CallParity film, v2: real evidence first

The film opens on a real call record a human answered, places a new live call
on camera, then chains that evidence into the product. Product demo material
comes second and reuses the takes already recorded in `demo/recordings/`.

Two timelines. Timeline A includes the live call beat and runs 3:20. Timeline
B is the fallback if the live call fails on the day; it runs 3:00 and needs no
portal interaction beyond scrolling. Every scene below states which timeline
uses it, which take covers it, what gets blurred, and whether its narration
audio already exists or needs synthesis.

## The evidence and where it lives

- The warehouse call is real and sits in the CALL-E portal under the owner's
  account: thread `d2004f6b-abda-4fd6-a5b7-a2505b295269`, task text beginning
  "Call ... as an AI ops clerk. You are calling North Gate Warehouse about
  pallet PL-9F21 of refrigerated cartons". Its call id
  `call_vzro922bOACJjf19ML7vQQ` appears in the portal's call-id autocomplete.
  That thread contains a personal phone number starting +880. It gets blurred
  in every frame where the thread is visible. No exception.
- The driver call is NOT in the portal history. Its API response is committed
  byte for byte at `tests/fixtures/call_2kxhpDvknUJ444kKfJLsyA.json`
  (commit `b981c37`). The film never claims the driver record is on a portal
  screen. It shows the committed file and its git history instead.
- The workbench renders both call ids as code chips in the Live import bar
  next to the Import button (`apps/web/src/App.jsx`), so the id on the
  workbench screen visibly matches the id in the portal autocomplete and the
  fixture filename. That match is the point of scene V3.

## Timeline A, with the live beat, 3:20

| Slot | Scene | On screen | Take | Narration audio |
|---|---|---|---|---|
| 0:00-0:20 | V1 cold open | Portal: the real warehouse thread | NEW take P1 | synthesize, 48 words |
| 0:20-1:00 | V2 live beat | Portal New Chat + phone on camera | NEW take P2 | synthesize, 19 + 24 words |
| 1:00-1:20 | V3 id-match import | Workbench import, id chips | scene1_punchline.mp4 | synthesize, 46 words |
| 1:20-1:59 | V4 product loop | Dropped leak, Run parity, card | scene2_workbench.mp4 | reuse scene_2.mp3 tail, 90 words |
| 1:59-2:56 | V5 production proof | Crash, 429, /metrics terminal | scene3_production_proof.mp4 | reuse scene_3.mp3 whole, 151 words |
| 2:56-3:20 | V6 close | FR-1900, PR 220, operations guide | scene4_impact.mp4 | synthesize, 58 words |

Narration: 436 words. About 24 seconds of V2 is live call audio with no
narration, so the spoken text runs at roughly 149 words per minute.

## Timeline B, fallback without the live beat, 3:00

If the live call aborts (criteria in the runbook), V2 is dropped and the cold
open runs longer over the committed records. Everything else is identical and
shifts earlier. Nothing needs re-cutting except offsets.

| Slot | Scene | On screen | Take | Narration audio |
|---|---|---|---|---|
| 0:00-0:20 | V1 cold open | Portal: the warehouse thread | NEW take P1 | same V1 audio |
| 0:20-0:40 | V1-ext records | Portal autocomplete, then the committed driver record | P1 + NEW take P3 | synthesize, 49 words |
| 0:40-1:00 | V3 id-match import | as above | scene1_punchline.mp4 | same V3 audio |
| 1:00-1:39 | V4 product loop | as above | scene2_workbench.mp4 | same |
| 1:39-2:36 | V5 production proof | as above | scene3_production_proof.mp4 | same |
| 2:36-3:00 | V6 close | as above | scene4_impact.mp4 | same |

Narration: 442 words over 180 seconds, 147 words per minute. Synthesize the
V1-ext chunk either way so the fallback is ready before the shoot.

## Scene V1, cold open, 0:00-0:20

**Shot (take P1, new):** The portal signed in, open on thread
`d2004f6b-abda-4fd6-a5b7-a2505b295269`. Scroll slowly through the task text
("...calling North Gate Warehouse about pallet PL-9F21 of refrigerated
cartons") and the call outcome. Hold on the structured result.

**Blur:** the line containing the +880 number, every frame it is visible.
Also blur any other phone number the portal renders anywhere in frame,
including the thread list in the left sidebar.

**Narration (48 words, synthesize):**
"This is a real call record, not a mockup. A phone agent called North Gate
Warehouse about pallet PL-9F21, refrigerated cartons, and a human answered.
The warehouse put the pallet at dock three at six forty. Keep that claim in
mind. Someone is about to disagree with it."

## Scene V2, the live beat, 0:20-1:00 (timeline A only)

**Shot (take P2, new, one continuous recording):** The portal New Chat pane
and the owner's phone both in frame (screen capture plus the phone propped in
view of the camera, ringer audible). The owner pastes the prompt, sends it,
the phone rings, they answer in character, and the transcript forms in the
portal in real time.

**The prompt the owner types** (fill the placeholder off camera before
recording; the number itself must never be readable in the final cut):

    Call <your number> as an AI ops clerk. Disclose you are an AI assistant
    at the start of the call. You are calling the driver assigned to pickup
    ticket FR-1842. Ask only what the driver could observe directly: which
    dock they pulled to, what they saw there, and whether they saw pallet
    PL-9F21. Do not repeat what anyone else has said about this ticket.
    Keep the call under one minute, thank the driver, and end the call.

The disclosure line matches the account's earlier calls. The questions are
observable-only, the same rule the product's leak check enforces: no dock
number asserted, no time asserted, nothing from the warehouse call repeated.

**What the owner says when answering, in character, short and plain:**

1. "This is the driver on the FR-1842 pickup."
2. "I pulled up to dock three. It was empty, nothing staged."
3. "I never saw that pallet. The yard marshal waved me off."

Let the agent close the call. Stay on the transcript for ten seconds while it
finishes forming.

**Blur:** the typed number in the prompt box and in the sent message bubble,
any recipient line the new thread shows, and the phone's screen if the
incoming-call UI shows a readable number. Prefer framing the phone so the
screen is angled away; blur is the backstop.

**Pacing within the slot:** 0:20-0:28 typing and send (speed up the typing in
the edit if needed), 0:28-0:52 ring and conversation as live audio, no
narration over the owner or the agent speaking, 0:52-1:00 the transcript view.

**Narration chunk V2a (19 words, synthesize), over the typing:**
"Now the same thing, live. I ask the agent to call me, and I will answer as
the driver."

**Narration chunk V2b (24 words, synthesize), over the transcript view:**
"That transcript formed while we talked. One rule in the prompt: disclose you
are an assistant, and ask only what the driver could see."

**If the live call fails on the day:** drop to timeline B. No other scene
changes.

## Scene V1-ext, the committed records, 0:20-0:40 (timeline B only)

**Shot:** Two parts. First (take P1 material): the portal call-id autocomplete
showing `call_vzro922bOACJjf19ML7vQQ`. Second (take P3, new, terminal plus
editor): `tests/fixtures/call_2kxhpDvknUJ444kKfJLsyA.json` open in an editor
beside a terminal running:

    git log --follow --oneline -- tests/fixtures/call_2kxhpDvknUJ444kKfJLsyA.json

which prints commit `b981c37`. Hold on the structured result in the JSON:
arrived true, dock 3 empty, never saw PL-9F21.

**Blur:** same portal rule as V1 for the autocomplete shot. The fixture file
contains no phone fields (that is by design and is checked by tests), so the
editor shot needs no blur.

**Narration (49 words, synthesize):**
"The warehouse record lives in the account history. Its call id is right there
in the portal. The driver answered a second call. That record is committed to
the repository, byte for byte, with its own history. Two spoken answers about
one pallet, and they do not line up."

## Scene V3, the id-match import, 1:00-1:20 (A) / 0:40-1:00 (B)

**Shot (reuse `demo/recordings/scene1_punchline.mp4`, 53.4s raw):** the
workbench on FR-1842 with the Live import bar visible. Trim to about 20
seconds: in-point a few seconds before the Import live records click, with the
two id chips (`A call_vzro922bOACJjf19ML7vQQ`, `B call_2kxhpDvknUJ444kKfJLsyA`)
readable; out-point holding on the RESTAGE_AND_RECALL card and the
contradicted pallet_staged edge. If the chips are not legible at final
resolution, insert a two-second zoom on the import bar before the click.

**Blur:** none. Call ids are not phone numbers, and the workbench masks
party numbers by design.

**Narration (46 words, synthesize):**
"Back in the product. These two records are committed to the repo, byte for
byte. I import them, no new call placed, and the graph flips: pallet staged,
contradicted. Restage and recall. Check the id on screen. It is the same id
sitting in the portal."

## Scene V4, the product loop condensed, 1:20-1:59 (A) / 1:00-1:39 (B)

**Shot (reuse `demo/recordings/scene2_workbench.mp4`, 180.3s raw):** two
sub-cuts totaling 39 seconds. Cut one, about 14s: the Preview results with the
"Dropped by leak check" entry, the struck-through recap question and its
reasons, cursor on it. Cut two, about 25s: the Run parity click through the
rail phases to the card flip (the parity run in the take is about 12s; keep
the claims filling and the graph lighting up).

**Narration (90 words, REUSE `scene_2.mp3` trimmed):** cut the mp3 at the
silence before "Watch the dropped question", about 22.6s in, and keep the tail
(36.3s). Audio starts 2 seconds into the slot. Spoken text of the tail:
"Watch the dropped question. A naive follow-up bot would ask the driver to
confirm the pallet, the dock, and the time. That hands the driver the
warehouse's answer. The leak check drops it structurally, and the driver only
gets observable questions. What did you see, which dock did you pull to. Now
run parity. Both calls run through the same port that drives the live CALL-E
API. The merger does the confrontation. Pallet staged, contradicted. Driver
arrived, confirmed. Seal, untested, nobody read it. One action card. A human
owns it."

## Scene V5, production proof, 1:59-2:56 (A) / 1:39-2:36 (B)

**Shot (reuse `demo/recordings/scene3_production_proof.mp4`, 186.0s raw):**
trim to 57 seconds in three sub-cuts aligned to the narration: the
`production_proof.sh` crash section (kill -9, `status=running` frozen row,
reboot, `status=failed`, retry to RESTAGE_AND_RECALL) for the first 33
seconds of the slot, the rate-limit lines ending in `429 retry_after=60` for
the next 13, the `/metrics` exposition for the last 11.

**Narration (151 words, REUSE `scene_3.mp3` whole, 56.3s):** unchanged text,
still accurate:
"Ops software earns trust when things break, so let me break it. This script
boots a throwaway copy of the API and kills it, dash nine, in the middle of a
parity run. The job row is frozen at running in the database. One reboot
later, that same job reads failed with an error an operator can act on, and
the ticket is free. A deliberate retry completes with the same restage card.
Nothing redials on its own, because in live mode a silent retry would call two
humans back. Next, rate limits. Every mutating route draws from a budget per
operator token, and a flood without a valid token gets metered by client IP
before the 401 goes out. There's the 429, with a Retry-After header. And the
service exposes metrics in Prometheus format. Requests by status class, jobs
by terminal status. Counts only, nothing sensitive. 165 tests, all offline."

## Scene V6, close, 2:56-3:20 (A) / 2:36-3:00 (B)

**Shot (reuse `demo/recordings/scene4_impact.mp4`, 308.4s raw):** trim to 24
seconds: the FR-1900 RELEASE_TRUCK card (about 10s), the merged upstream pull
request CALLE-AI/awesome-phone-call-agents#220 (about 7s), docs/OPERATIONS.md
scrolled to its contents (about 7s).

**Narration (58 words, synthesize):**
"When both sides agree, the same machinery releases the truck. It escalates
only on contradiction. The refutation planner is merged upstream as ClaimKill,
pull request two twenty, so anyone can reuse it today. The operations guide
covers every environment variable, migrations, auth, rate limits, and crash
recovery. Two real calls went in. One decision came out. That's CallParity."

## Narration audio: reuse and re-synthesis list

Existing mp3s (branch `ruddro-roy/narration-assets-6d37`, voice Brian):
scene_1 18.4s, scene_2 58.9s, scene_3 56.3s, scene_4 35.4s.

- REUSE `scene_3.mp3` whole for V5 (text unchanged).
- REUSE `scene_2.mp3` for V4 with one head cut at the silence before "Watch
  the dropped question" (about 22.6s in), keeping the 36.3s tail.
- RETIRE `scene_1.mp3` and `scene_4.mp3`: their texts open on "two people
  answered real phone calls" and close on the old spine; both are replaced.
- SYNTHESIZE six new chunks, same voice: V1 (48 words), V1-ext (49, fallback
  insurance), V2a (19), V2b (24), V3 (46), V6 (58). 244 words total, about
  100 seconds of new audio.

## Assembly map

All video normalized to 1080p30 H.264 as in the existing assembly plan; audio
chunks placed with adelay at the offsets below, live-call audio from take P2
kept as diegetic sound in its slot (duck it under V2b).

Timeline A offsets (200s total): V1 audio at 0s, V2a at 20s, P2 live audio
28-52s, V2b at 52s, V3 at 60s, scene_2 tail at 82s, scene_3 at 119s, V6 at
176s. Video: P1 0-20, P2 20-60, scene1_punchline trim 60-80, scene2 trims
80-119, scene3 trims 119-176, scene4 trims 176-200.

Timeline B offsets (180s total): V1 at 0s, V1-ext at 20s, V3 at 40s, scene_2
tail at 62s, scene_3 at 99s, V6 at 156s. Video: P1 0-20, P1-autocomplete +
P3 20-40, then as above shifted 20s earlier.

Blur regions, complete list so far: the +880 line in thread d2004f6b (V1, and
V2 wherever the sidebar shows history), the typed number in the New Chat
prompt box and sent bubble (V2), any recipient line in the new thread (V2),
the phone's incoming-call screen if readable (V2), any other phone number the
portal renders in any frame. The workbench, terminal, and fixture shots need
no blur; they mask or omit numbers by design.

## Shoot runbook: the live beat

Pre-shoot checklist:

- Portal tab clean: signed in, warehouse thread bookmarked, every other
  thread scrolled out of frame or the sidebar collapsed. No other tabs, no
  bookmarks bar, no extension icons with account names.
- Browser at 1920x1080, 100% zoom. OS notifications off on the recording
  machine. Recorder set to capture system audio (the transcript pane is
  silent; the room mic picks up the phone).
- Phone: ringer at full volume, do-not-disturb off, propped in frame with the
  screen angled away from the camera. Quiet room.
- The prompt text above copied to the clipboard with the real number filled
  in. Never show the clipboard manager on screen.
- One rehearsal of the three driver lines out loud.

Sequence, in order:

1. Start the recorder.
2. Open the warehouse thread. Scroll it slowly top to bottom, pause two
   seconds on the task text and two on the result. This is the V1 material.
3. Open the call-id autocomplete and let `call_vzro922bOACJjf19ML7vQQ` be
   visible for three seconds (V1-ext insurance material, cheap to grab now).
4. Click New Chat. Paste the prompt. Pause one second. Send.
5. When the phone rings, let it ring twice, answer on camera, deliver the
   three driver lines, let the agent close.
6. Hold on the portal until the transcript stops updating, plus ten seconds.
7. Stop the recorder. Review immediately: number never legible, disclosure
   heard, all three lines audible, transcript formed.

Abort criteria, any one of these and the film ships timeline B:

- No ring within 60 seconds of sending, twice in a row.
- The call lands in voicemail or drops mid-conversation.
- The agent does not disclose it is an AI assistant on the call.
- The transcript pane has not started updating within 15 seconds of hangup.
- Anything personal appears on screen that blur cannot cleanly cover.
- More than two total attempts. Do not burn call credits chasing the take.

The fallback needs nothing from this shoot except step 2 and step 3, which
are risk-free, so record them regardless of how the live call goes.
