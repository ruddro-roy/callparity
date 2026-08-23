"""Full demo loop: preview then parity, matching DEMO_SCRIPT.md outcomes."""


def _wait(client, job_id):
    last = None
    for _ in range(50):
        res = client.get(f"/v1/jobs/{job_id}")
        last = res.json()
        if last["status"] in {"completed", "failed"}:
            return last
    raise AssertionError(f"job stuck: {last}")


def test_demo_script_preview_then_parity(client):
    preview = client.post("/v1/tickets/FR-1842/preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["preview"] is True
    goal = body["plan_b"]["goal"].lower()
    assert "pl-9f21" in goal
    assert "dock" in goal
    questions = " ".join(q["question"].lower() for q in body["plan_b"]["selected_questions"])
    assert "dock" in questions
    assert "jack" in questions or "see" in questions
    staged = next(c for c in body["claims_a"] if c["predicate"] == "pallet_staged")
    assert abs(staged["confidence"] - 0.81) < 0.05
    assert "dock" in staged["evidence_span"].lower() or "rolled" in staged["evidence_span"].lower()

    run = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "demo-script"})
    assert run.status_code == 202
    job = _wait(client, run.json()["id"])
    assert job["status"] == "completed"
    graph = job["result"]["graph"]
    by_pred = {e["predicate"]: e for e in graph}
    assert by_pred["pallet_staged"]["status"] == "CONTRADICTED"
    assert by_pred["driver_arrived"]["status"] == "CONFIRMED"
    assert by_pred["seal_recorded"]["status"] in {"UNTESTED", "ABSTAIN"}
    assert job["result"]["action"]["action"] == "RESTAGE_AND_RECALL"
    assert "restage" in job["result"]["action"]["rationale"].lower()


def test_voicemail_fixture_unreachable(client):
    res = client.post("/v1/tickets/FR-1888/parity", headers={"Idempotency-Key": "vm"})
    assert res.status_code == 202
    job = _wait(client, res.json()["id"])
    assert job["status"] == "completed"
    assert any(e["status"] == "UNREACHABLE" for e in job["result"]["graph"])
    assert job["result"]["action"]["action"] == "HOLD_FOR_HUMAN"
    assert job["result"]["claims_b"] == []
