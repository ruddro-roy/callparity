def _wait(client, job_id):
    last = None
    for _ in range(50):
        res = client.get(f"/v1/jobs/{job_id}")
        assert res.status_code == 200
        last = res.json()
        if last["status"] in {"completed", "failed"}:
            return last
    raise AssertionError(f"job stuck: {last}")


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["postgres"] == "up"
    assert body["calle"] == "up"


def test_parity_loop_fixtures(client):
    first = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "demo-1"})
    assert first.status_code == 202
    job_id = first.json()["id"]
    job = _wait(client, job_id)
    assert job["status"] == "completed"
    graph = job["result"]["graph"]
    action = job["result"]["action"]["action"]
    assert action == "RESTAGE_AND_RECALL"
    assert any(e["status"] == "CONTRADICTED" and e["predicate"] == "pallet_staged" for e in graph)
    assert job["result"]["transcript_pointers"]["a"]
    assert job["telemetry"]["claims_a"] >= 1

    second = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "demo-1"})
    assert second.status_code == 202
    assert second.json()["id"] == job_id

    fetched = client.get("/v1/tickets/FR-1842")
    assert fetched.status_code == 200
    assert fetched.json()["action"]["action"] == "RESTAGE_AND_RECALL"
    assert fetched.json()["transcript_pointers"]

    job_get = client.get(f"/v1/jobs/{job_id}")
    assert job_get.status_code == 200
    assert job_get.json()["status"] == "completed"


def test_control_ticket(client):
    res = client.post("/v1/tickets/FR-1900/parity", headers={"Idempotency-Key": "ctrl"})
    assert res.status_code == 202
    job = _wait(client, res.json()["id"])
    assert job["result"]["action"]["action"] == "RELEASE_TRUCK"


def test_preview_places_zero_calls(client):
    res = client.post("/v1/tickets/FR-1842/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["preview"] is True
    assert "PL-9F21" in body["plan_b"]["goal"]


def test_missing_ticket(client):
    res = client.get("/v1/tickets/NOPE")
    assert res.status_code == 404
