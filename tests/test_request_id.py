"""Request id is a UUID we assign or propagate; the access line stays header-free."""

from __future__ import annotations

import json
import uuid

from app.request_id import parse_request_id, resolve_request_id

SAMPLE = "+1" + "5" * 10
KNOWN = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _lines(capsys) -> list[dict]:
    out = capsys.readouterr().out
    rows = []
    for raw in out.splitlines():
        raw = raw.strip()
        if not raw.startswith("{"):
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def _access(capsys) -> dict:
    hits = [row for row in _lines(capsys) if row.get("event") == "http.request"]
    assert hits, "expected one http.request line"
    return hits[-1]


def test_parse_accepts_canonical_uuid_only():
    assert parse_request_id(KNOWN) == KNOWN
    assert parse_request_id(KNOWN.upper()) == KNOWN
    assert parse_request_id("  " + KNOWN + "  ") == KNOWN
    assert parse_request_id(None) is None
    assert parse_request_id("") is None
    assert parse_request_id("not-a-uuid") is None
    assert parse_request_id("test-operator-token") is None
    assert parse_request_id(KNOWN.replace("-", "")) is None
    assert parse_request_id(SAMPLE) is None
    assert parse_request_id("urn:uuid:" + KNOWN) is None


def test_resolve_replaces_unsafe_values():
    assert resolve_request_id(KNOWN) == KNOWN
    generated = resolve_request_id("test-operator-token")
    uuid.UUID(generated)
    assert generated != "test-operator-token"


def test_healthz_assigns_and_echoes_request_id(client):
    res = client.get("/healthz", headers={"X-Request-ID": ""})
    assert res.status_code == 200
    rid = res.headers["X-Request-ID"]
    uuid.UUID(rid)


def test_propagates_canonical_incoming_id(client):
    res = client.get("/readyz", headers={"X-Request-ID": KNOWN})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == KNOWN


def test_rejects_token_and_phone_shaped_incoming_ids(client):
    token = client.get("/healthz", headers={"X-Request-ID": "test-operator-token"})
    assert token.headers["X-Request-ID"] != "test-operator-token"
    uuid.UUID(token.headers["X-Request-ID"])

    phone = client.get("/healthz", headers={"X-Request-ID": SAMPLE})
    assert phone.headers["X-Request-ID"] != SAMPLE
    uuid.UUID(phone.headers["X-Request-ID"])


def test_access_line_has_method_path_status_latency_and_id(client, capsys):
    res = client.get("/readyz", headers={"X-Request-ID": KNOWN})
    line = _access(capsys)
    assert res.headers["X-Request-ID"] == KNOWN
    assert line["request_id"] == KNOWN
    assert line["method"] == "GET"
    assert line["path"] == "/readyz"
    assert line["status"] == 200
    assert isinstance(line["latency_ms"], int)
    assert line["latency_ms"] >= 0


def test_access_line_omits_headers_body_query_and_token(client, capsys):
    secret = "should-not-appear-in-logs"
    res = client.post(
        "/v1/tickets/FR-1842/preview?token=test-operator-token",
        headers={"X-Request-ID": KNOWN, "X-Operator-Token": "test-operator-token"},
        json={"note": secret},
    )
    assert res.status_code == 200
    out = capsys.readouterr().out
    assert "test-operator-token" not in out
    assert secret not in out
    assert "Authorization" not in out
    assert "X-Operator-Token" not in out
    assert "Bearer" not in out
    line = [json.loads(s) for s in out.splitlines() if s.startswith("{") and "http.request" in s][-1]
    assert line["path"] == "/v1/tickets/FR-1842/preview"
    assert "query" not in line
    assert "headers" not in line
    assert "body" not in line
    assert line["request_id"] == KNOWN


def test_401_still_echoes_request_id(client):
    res = client.post(
        "/v1/tickets/FR-1842/preview",
        headers={"Authorization": "Bearer wrong", "X-Request-ID": KNOWN},
    )
    assert res.status_code == 401
    assert res.headers["X-Request-ID"] == KNOWN


def test_successive_requests_do_not_leak_request_id(client):
    first = client.get("/healthz").headers["X-Request-ID"]
    second = client.get("/readyz").headers["X-Request-ID"]
    assert first != second
    uuid.UUID(first)
    uuid.UUID(second)
