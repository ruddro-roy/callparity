"""Parity from two recorded live CALL-E calls, with no network.

tests/fixtures holds the GET /v1/calls/{id} bodies of the two real calls
humans answered on the FR-1842 fact pattern. The structured results are what
the live API returned. transcript and summary are empty because the spoken
words are not part of the committed record and an invented quote would fake
evidence. No phone field appears anywhere. A MockTransport replays the two
records; any POST, or any fetch beyond those two paths, fails the test.
"""

import json
from contextlib import contextmanager
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
WAREHOUSE_CALL_ID = "call_vzro922bOACJjf19ML7vQQ"
DRIVER_CALL_ID = "call_2kxhpDvknUJ444kKfJLsyA"
IMPORT_BODY = {"call_id_a": WAREHOUSE_CALL_ID, "call_id_b": DRIVER_CALL_ID}


def refuse_to_dial(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected HTTP request: {request.method} {request.url.path}")


@contextmanager
def reader_override(transport: httpx.BaseTransport):
    from app.deps import get_live_reader
    from app.main import app
    from app.ports.live import LiveCalleSdk

    app.dependency_overrides[get_live_reader] = lambda: LiveCalleSdk(
        "https://api.call-e.invalid", token="test-token", transport=transport
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_live_reader, None)


def recorded_get_transport(counter: dict) -> httpx.MockTransport:
    records = {
        f"/v1/calls/{cid}": json.loads((FIXTURES / f"{cid}.json").read_text())
        for cid in (WAREHOUSE_CALL_ID, DRIVER_CALL_ID)
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", f"import must never {request.method} {request.url.path}"
        assert request.url.path in records, f"unexpected path {request.url.path}"
        counter["gets"] = counter.get("gets", 0) + 1
        return httpx.Response(200, json=records[request.url.path])

    return httpx.MockTransport(handler)


def test_import_two_live_calls_emits_restage_and_recall(client):
    counter: dict = {}
    with reader_override(recorded_get_transport(counter)):
        res = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert res.status_code == 200
    job = res.json()
    assert job["status"] == "completed"
    result = job["result"]
    assert result["action"]["action"] == "RESTAGE_AND_RECALL"
    assert result["mode"] == "live_import"
    assert result["call_ids"] == {"a": WAREHOUSE_CALL_ID, "b": DRIVER_CALL_ID}
    assert counter["gets"] == 2

    staged = next(e for e in result["graph"] if e["predicate"] == "pallet_staged")
    assert staged["status"] == "CONTRADICTED"
    arrived = next(e for e in result["graph"] if e["predicate"] == "driver_arrived")
    assert arrived["status"] == "CONFIRMED"

    assert {c["call_run_id"] for c in result["claims_a"]} == {WAREHOUSE_CALL_ID}
    assert {c["call_run_id"] for c in result["claims_b"]} == {DRIVER_CALL_ID}

    # The bot ended the driver call early (task_completed false); the deny still counts.
    denied = next(c for c in result["claims_b"] if c["predicate"] == "pallet_visible_to_driver")
    assert denied["polarity"] == "denied"

    fetched = client.get("/v1/tickets/FR-1842").json()
    assert fetched["action"]["action"] == "RESTAGE_AND_RECALL"

    job_get = client.get(f"/v1/jobs/{job['id']}")
    assert job_get.status_code == 200
    assert job_get.json()["telemetry"]["mode"] == "live_import"


def test_import_replays_identical_job_without_refetching(client):
    counter: dict = {}
    with reader_override(recorded_get_transport(counter)):
        first = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
        second = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert counter["gets"] == 2


def test_import_blank_or_missing_call_id_fails_closed(client):
    with reader_override(httpx.MockTransport(refuse_to_dial)):
        blank = client.post(
            "/v1/tickets/FR-1842/parity/import",
            json={"call_id_a": "  ", "call_id_b": DRIVER_CALL_ID},
        )
        missing = client.post(
            "/v1/tickets/FR-1842/parity/import", json={"call_id_a": WAREHOUSE_CALL_ID}
        )
    assert blank.status_code == 422
    assert missing.status_code == 422
    assert client.get("/v1/tickets/FR-1842").json()["action"] is None


def test_import_without_live_config_fails_closed(client):
    res = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert "CALLE_API_TOKEN" in detail and "CALLE_BASE_URL" in detail
    # Fixture mode has no copy of a real call record; the remedy must not point there.
    assert "USE_FIXTURES" not in detail
    assert client.get("/v1/tickets/FR-1842").json()["action"] is None


def test_import_unknown_ticket_is_404(client):
    with reader_override(httpx.MockTransport(refuse_to_dial)):
        res = client.post("/v1/tickets/NOPE/parity/import", json=IMPORT_BODY)
    assert res.status_code == 404


def test_import_maps_upstream_404_to_502(client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(404, text="no such call")

    with reader_override(httpx.MockTransport(handler)):
        res = client.post(
            "/v1/tickets/FR-1842/parity/import",
            json={"call_id_a": "call_mock_missing", "call_id_b": DRIVER_CALL_ID},
        )
    assert res.status_code == 502
    assert "call id" in res.json()["detail"]
    assert client.get("/v1/tickets/FR-1842").json()["action"] is None


def test_recorded_call_fixtures_hold_no_phone_digits():
    from app.ports.live import redact_phones

    for cid in (WAREHOUSE_CALL_ID, DRIVER_CALL_ID):
        text = (FIXTURES / f"{cid}.json").read_text()
        assert redact_phones(text) == text
        assert "+" not in text
