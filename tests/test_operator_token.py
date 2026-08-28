"""The operator token gates every mutating route; health and readiness stay public."""

from fastapi.testclient import TestClient

from test_live_import import DRIVER_CALL_ID, WAREHOUSE_CALL_ID


def _anon() -> TestClient:
    # Same app and already-seeded DB as the authed fixture, minus the default token.
    from app.main import app

    return TestClient(app)


def test_preview_without_token_is_401(client):
    assert _anon().post("/v1/tickets/FR-1842/preview").status_code == 401


def test_parity_without_token_is_401(client):
    assert _anon().post("/v1/tickets/FR-1842/parity").status_code == 401


def test_import_without_token_is_401(client):
    res = _anon().post(
        "/v1/tickets/FR-1842/parity/import",
        json={"call_id_a": WAREHOUSE_CALL_ID, "call_id_b": DRIVER_CALL_ID},
    )
    assert res.status_code == 401


def test_wrong_token_is_401(client):
    res = client.post("/v1/tickets/FR-1842/preview", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_valid_token_allows_preview(client):
    res = client.post("/v1/tickets/FR-1842/preview")
    assert res.status_code == 200
    assert res.json()["preview"] is True


def test_valid_token_allows_parity(client):
    res = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "tok-parity"})
    assert res.status_code == 202


def test_health_and_ready_are_public(client):
    anon = _anon()
    assert anon.get("/healthz").status_code == 200
    ready = anon.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
