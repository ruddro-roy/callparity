"""Import converges regardless of a crash: reconcile if incomplete, replay if done.

A crash mid-import (Party B unreachable) leaves no card, because import writes
nothing until both records are in hand and the request-level rollback discards
the partial work, so a retry re-fetches both records. Once a job is completed, a
later import replays the stored job and fetches nothing.
"""

import json

import httpx
from test_live_import import (
    FIXTURES,
    IMPORT_BODY,
    WAREHOUSE_CALL_ID,
    reader_override,
    recorded_get_transport,
)


def _crash_after_first_get(counter: dict) -> httpx.MockTransport:
    warehouse = json.loads((FIXTURES / f"{WAREHOUSE_CALL_ID}.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        counter["gets"] = counter.get("gets", 0) + 1
        if request.url.path == f"/v1/calls/{WAREHOUSE_CALL_ID}":
            return httpx.Response(200, json=warehouse)
        return httpx.Response(502, text="upstream crash before B completed")

    return httpx.MockTransport(handler)


def test_import_reconciles_after_crash_then_replays_completed(client):
    crash = {}
    with reader_override(_crash_after_first_get(crash)):
        crashed = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert crashed.status_code == 502
    assert crash["gets"] >= 1
    assert client.get("/v1/tickets/FR-1842").json()["action"] is None

    reconcile = {}
    with reader_override(recorded_get_transport(reconcile)):
        ok = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert ok.status_code == 200
    assert ok.json()["result"]["action"]["action"] == "RESTAGE_AND_RECALL"
    assert reconcile["gets"] == 2

    replay = {}
    with reader_override(recorded_get_transport(replay)):
        again = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert again.status_code == 200
    assert again.json()["id"] == ok.json()["id"]
    assert replay.get("gets", 0) == 0
