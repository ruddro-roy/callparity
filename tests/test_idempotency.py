from app.services.idempotency import derive_idempotency_key


def test_key_stable_for_same_claims():
    claims = [{"id": "a"}, {"id": "b"}]
    k1 = derive_idempotency_key("FR-1842", "AB", claims)
    k2 = derive_idempotency_key("FR-1842", "AB", list(reversed(claims)))
    assert k1 == k2
    k3 = derive_idempotency_key("FR-1842", "AB", [{"id": "c"}])
    assert k1 != k3


def test_key_includes_ticket_and_party():
    a = derive_idempotency_key("FR-1842", "A", [])
    b = derive_idempotency_key("FR-1842", "B", [])
    c = derive_idempotency_key("FR-1900", "A", [])
    assert a != b != c
    assert a.startswith("FR-1842:A:")


def _wait(client, job_id):
    for _ in range(40):
        body = client.get(f"/v1/jobs/{job_id}").json()
        if body["status"] in {"completed", "failed"}:
            return body
    raise AssertionError("job did not finish")


def test_double_post_same_key_debounced(client):
    first = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "same-key"})
    second = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "same-key"})
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    done = _wait(client, first.json()["id"])
    assert done["status"] == "completed"
