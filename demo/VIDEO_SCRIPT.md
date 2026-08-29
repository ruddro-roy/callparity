# CallParity, 3-minute demo tape: shot-by-shot script

Four scenes, hard timeline, 441 narration words over 180 seconds (147 words per
minute). Record the screen and the narration separately; the narration column
below is the exact spoken text per scene, sized to its slot. Every command in
this script was run against the stack before it was written down.

The punchline comes first. A viewer who stops at 0:20 has already seen two real
recorded CALL-E calls merge into a restage-and-recall verdict.

## Recording prep (before capture, not on tape)

The whole demo runs offline. The import scene needs the API to read the two
recorded call fixtures over GET, so a loopback stub serves them on port 9111
exactly the way the live Calls API would:

    cat > /tmp/calle_stub.py <<'PY'
    """Loopback stub serving the two recorded CALL-E call fixtures over GET only."""
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from pathlib import Path

    FIXTURES = Path("/workspace/tests/fixtures")
    CALL_IDS = ("call_vzro922bOACJjf19ML7vQQ", "call_2kxhpDvknUJ444kKfJLsyA")
    RECORDS = {f"/v1/calls/{cid}": (FIXTURES / f"{cid}.json").read_text() for cid in CALL_IDS}


    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = RECORDS.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            print("stub:", fmt % args, flush=True)


    HTTPServer(("127.0.0.1", 9111), Handler).serve_forever()
    PY
    python3 /tmp/calle_stub.py > /tmp/calle_stub.log 2>&1 & echo $! > /tmp/calle_stub.pid

Adjust the `FIXTURES` path if the repo is not at /workspace. Then the API, on a
fresh SQLite file, seeded, fixtures on, with a 2-second playback delay so the
parity run on tape takes about 12 seconds (measured 12.4s):

    cd <repo root>
    . .venv/bin/activate
    rm -f video_demo.db
    export DATABASE_URL=sqlite+pysqlite:///./video_demo.db SEED_ON_STARTUP=true \
      PLAYBACK_DELAY_MS=2000 REDIS_OPTIONAL=true USE_FIXTURES=true \
      OPERATOR_TOKEN=callparity-demo-operator \
      CALLE_BASE_URL=http://127.0.0.1:9111 CALLE_API_TOKEN=loopback-stub-token
    uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 \
      > /tmp/api_video.log 2>&1 & echo $! > /tmp/uvicorn.pid

The default rate limit (60 mutating requests per minute) covers the whole
recording flow. Then the workbench:

    cd apps/web && npm ci && npm run dev -- --host 127.0.0.1 --port 3000

Checks before hitting record: `curl -s http://127.0.0.1:8000/readyz` is 200,
http://127.0.0.1:3000 shows FR-1842 with the amber fixture banner, and the
Live import bar with the "Import live records" button is visible on FR-1842.

Capture at 1920x1080, 100% zoom. Scenes 1, 2, and 4 are the workbench in a
browser; scene 3 is a full-screen terminal at the repo root with the venv
active. Record each scene as its own clip; the assembly step trims and
concatenates them to the timeline below.

## Timeline

| Slot | Scene | On screen | Words |
|---|---|---|---:|
| 0:00-0:20 | 1. The punchline | Workbench FR-1842, one click on Import live records | 47 |
| 0:20-1:20 | 2. The loop | Preview, the dropped leak, Run parity, graph, card | 146 |
| 1:20-2:20 | 3. Production proof | Terminal: crash convergence, 429, /metrics | 151 |
| 2:20-3:00 | 4. Impact and adoption | FR-1900 control, upstream PR 220, operations guide | 97 |

## Scene 1, 0:00-0:20, the punchline

**Shot:** The workbench already open on FR-1842. Ticket header, the
$18k/hour SLA chip, empty claim columns, the Live import bar.

**Do:** At 0:02, click **Import live records**. The card flips to
RESTAGE_AND_RECALL and the graph fills within a second (the import merges the
two recorded call fixtures over GET and completes in about 0.1s). Hold on the
card and the contradicted pallet_staged edge until 0:20.

**Narration (47 words):**
"Two people answered real phone calls about the same pallet. The warehouse
says it's staged at dock three. The driver says that dock was empty. I click
import, CallParity merges both call records, and the verdict lands: restage
the pallet, recall the driver. That took two seconds."

## Scene 2, 0:20-1:20, the loop from zero

**Shot:** Same workbench. Reload FR-1842 so the columns are driven by the
buttons, not the import result.

**Do:** At 0:22, click **Preview (0 calls)**. Party A claims fill the left
column, the refute plan fills the second. At about 0:35, point the cursor at
the "Dropped by leak check" entry, the struck-through recap question with its
reasons. At about 0:55, click **Run parity** and let the rail play: A planning,
on the call, claims extracted, then B. The run takes about 12 seconds. End the
scene holding on the merged graph and the action card.

**Narration (146 words):**
"Here's the problem. An eighteen-thousand-dollar-an-hour cold-chain ticket, and
the two people on the phone disagree. CallParity treats that disagreement as a
testable claim graph. Preview places zero calls. It turns the warehouse call
into typed claims, each with a quoted span and a confidence score, then writes
the second call as a test of the first. Watch the dropped question. A naive
follow-up bot would ask the driver to confirm the pallet, the dock, and the
time. That hands the driver the warehouse's answer. The leak check drops it
structurally, and the driver only gets observable questions. What did you see,
which dock did you pull to. Now run parity. Both calls run through the same
port that drives the live CALL-E API. The merger does the confrontation.
Pallet staged, contradicted. Driver arrived, confirmed. Seal, untested, nobody
read it. One action card. A human owns it."

## Scene 3, 1:20-2:20, production proof

**Shot:** Full-screen terminal, repo root, venv active.

**Do:** At 1:22, run:

    bash scripts/production_proof.sh

The script prints in sections; it boots a throwaway API on port 8123 and never
touches the demo stack. Pace the scroll with the narration: the crash section
(kill -9, `row after crash: status=running`, then `status=failed` and the
retry completing with RESTAGE_AND_RECALL) up to about 1:55, the rate-limit
section (`preview 3: 429 retry_after=60`, then the four no-token lines ending
in `429 retry_after=60`) to about 2:08. At 2:08, run:

    curl -s http://localhost:8000/metrics

Hold on the Prometheus output (`callparity_requests_total` by status class,
`callparity_jobs_total` by terminal status) until 2:20.

**Narration (151 words):**
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

## Scene 4, 2:20-3:00, impact and adoption

**Shot:** Back to the workbench.

**Do:** At 2:22, click **FR-1900 control**, then **Run parity**. The card
reads RELEASE_TRUCK at about 2:36. At about 2:42, switch to a window showing
the merged upstream pull request (CALLE-AI/awesome-phone-call-agents#220) and
then `docs/OPERATIONS.md` scrolled to its table of contents. End on the
workbench FR-1842 card at 2:56.

**Narration (97 words):**
"One more ticket, this time with no contradiction. Both sides agree, so the
same machinery releases the truck. The system escalates only when the facts
collide. The refutation planner is merged upstream in awesome-phone-call-agents
as ClaimKill, pull request 220, so anyone can reuse it today. And for the team
that would run this for real, the operations guide covers every environment
variable, the migration story, auth, rate limits, and crash recovery. Cold
chain is the seed. The same loop fits prior-auth, construction materials,
insurance supplements. Anywhere two people hold half the truth on the phone.
That's CallParity."

## Verified expected outputs

Ran before writing, against the stack above:

- Import: `POST /v1/tickets/FR-1842/parity/import` with the two recorded call
  ids returns a completed job, action RESTAGE_AND_RECALL, in about 0.1s.
- Run parity on FR-1842 at PLAYBACK_DELAY_MS=2000: completed in 12.4s,
  action RESTAGE_AND_RECALL.
- FR-1900 parity: completed, action RELEASE_TRUCK.
- `scripts/production_proof.sh`: exit 0; crash section converges to failed
  then RESTAGE_AND_RECALL on retry; rate-limit section ends in
  `429 retry_after=60` for both the operator and the no-token flood.
- `curl -s http://localhost:8000/metrics`: Prometheus text with
  `callparity_requests_total` and `callparity_jobs_total`.
