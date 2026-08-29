# CALL-E platform feedback (Most Valuable Feedback survey)

Paste-ready answers. Everything below comes from real usage during the
hackathon, verifiable in github.com/ruddro-roy/callparity.

---

We built CallParity, a tool that places a second call as a falsification test
of the first and diffs the answers. We integrated deeply. We placed real calls
through both POST /v1/calls (an httpx adapter with the wire format pinned by
mocked tests in `tests/test_live_adapter.py`) and the dashboard's New Chat,
polled GET /v1/calls/{id}, committed recorded response bodies as fixtures, and
merged a skill upstream as awesome-phone-call-agents PR 220. Six findings,
five problems and one thing that worked.

## 1. Dashboard calls fail quietly; API calls do not

**What happened.** Several New Chat calls on our account connected but the
agent never spoke, or the thread showed "The call was declined before a live
exchange was established". Under that banner a transcript still rendered, as
if a conversation had happened. API-placed calls with the same kind of task
succeeded reliably on the same account.

**How to reproduce.** Send a short question-asking task from New Chat, then
send the same task via POST /v1/calls. When the dashboard call is declined,
look below the error banner.

**Suggestion.** Make dashboard failures loud (a status chip, a retry button),
and never render a transcript under a declined-call banner. We lost real time
deciding whether that transcript was real.

## 2. Call ids are not first-class in the portal

**What happened.** A call id our account owns appears in the Call ID
autocomplete, yet date-filtered search returns "No call records found" across
ranges that should include it. Thread URLs use internal UUIDs, so a call id
cannot be deep-linked or shared.

**How to reproduce.** Pick a completed id from the autocomplete (ours,
`call_vzro922bOACJjf19ML7vQQ`) and search for it with any date range applied.

**Suggestion.** Make call ids searchable regardless of date filters and
routable in URLs. The call id is the join key between the API and the portal.
Right now it only works on one side.

## 3. GET /v1/calls/{id} drifted without notice

**What happened.** Bodies we recorded earlier in the hackathon (committed at
`tests/fixtures/*.json`) contain a top-level `transcript` field. Current
responses omit it and add fields such as `evidence`, `completion_confidence`,
and `recipients`. Our adapter read `transcript` directly, so the drift
silently emptied a field we display.

**How to reproduce.** Diff one of our committed fixture bodies against a
current GET /v1/calls/{id} response.

**Suggestion.** Version the response shape or publish a changelog. Additive
fields are fine. Removals need warning.

## 4. No caller id field on call records

**What happened.** Call records expose `recipients[].phones` but nothing that
says which number placed the call. Our audit trail logs every call against a
ticket, and the from side is a hole in it.

**How to reproduce.** GET any call and look for a `from_number` or caller
field.

**Suggestion.** Add the originating number, maskable, to the call record.

## 5. structured_result carries raw ASR

**What happened.** Answer values reflect raw speech recognition. A speaker
said "dock three"; the structured answer stored "top three". Logic that
compares answers across calls has to guess when a value is a mishearing.

**How to reproduce.** Ask for a short spoken token (a dock number, a code) in
`result_schema` and compare the structured answer against the audio.

**Suggestion.** Attach a confidence or normalized-value field per answer, ASR
word confidence lifted to the result level.

## 6. What worked well

The `result_schema` contract earned its keep. Per-question objects with answer
strings gave us stable keys to extract claims from two different calls and
compare them, which is CallParity's whole premise, and it never wobbled. POST
idempotency via the Idempotency-Key header also behaved exactly as documented,
same key, same call, no double dials. We pinned both behaviors in mocked
wire-format tests and they held against the live API.
