import json

import httpx
import pytest

from app.ports.calle import CallTask, Plan, RunRef
from app.ports.live import LiveCalleSdk, require_e164_phones


def test_require_e164_refuses_empty():
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones([])
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones(["", "  "])
    with pytest.raises(ValueError, match="E.164"):
        require_e164_phones(["5550100001"])
    assert require_e164_phones(["+15550100002"]) == ["+15550100002"]


def test_live_plan_and_run_refuse_empty_phones():
    sdk = LiveCalleSdk("https://example.invalid", token="tok")
    with pytest.raises(ValueError, match="empty to_phones"):
        sdk.plan(
            CallTask(
                ticket_id="FR-1842",
                party_role="B",
                to_phones=[],
                goal="g",
                consent=True,
            )
        )
    plan = Plan(
        plan_id="p",
        ticket_id="FR-1842",
        party_role="B",
        ready_to_run=True,
        authorized=True,
        goal="g",
        to_phones=[],
    )
    with pytest.raises(ValueError, match="empty to_phones"):
        sdk.run(plan)


def test_run_posts_v1_calls_with_bearer_token():
    """Mocked transport: run_call must POST /v1/calls with auth and parse the call id."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": "call_mock_123", "status": "queued"})

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )
    task = CallTask(
        ticket_id="FR-1842",
        party_role="B",
        to_phones=["+15550100002"],
        goal="Ask only observable facts.",
        result_schema={"type": "object"},
        consent=True,
    )
    plan = sdk.plan(task)
    assert plan.ready_to_run and plan.authorized
    run = sdk.run(plan)
    assert run.run_id == "call_mock_123"
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/calls"
    assert seen["auth"] == "Bearer test-token"
    assert seen["body"]["to_phones"] == ["+15550100002"]
    assert seen["body"]["consent_disclosed"] is True
    assert seen["body"]["goal"] == "Ask only observable facts."


def test_get_reads_v1_calls_by_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/calls/call_mock_123"
        assert request.headers.get("Authorization") == "Bearer test-token"
        return httpx.Response(
            200,
            json={
                "id": "call_mock_123",
                "status": "completed",
                "structured_result": {"arrived": True},
                "transcript": "I pulled to the North Gate.",
                "summary": "done",
            },
        )

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )
    view = sdk.get(RunRef(run_id="call_mock_123", plan_id="p"))
    assert view.status == "completed"
    assert view.structured_result == {"arrived": True}
    assert "North Gate" in view.transcript


def test_missing_token_refuses_live_calls():
    sdk = LiveCalleSdk("https://api.call-e.invalid", token="")
    task = CallTask(
        ticket_id="FR-1842",
        party_role="B",
        to_phones=["+15550100002"],
        goal="g",
        consent=True,
    )
    with pytest.raises(RuntimeError, match="CALLE_API_TOKEN"):
        sdk.plan(task)
    with pytest.raises(RuntimeError, match="CALLE_API_TOKEN"):
        sdk.get(RunRef(run_id="x", plan_id="p"))


def test_claim_evidence_quote():
    from app.models.schemas import Claim, PartyRole, Polarity

    c = Claim(
        id="clm_x",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="pallet_staged",
        evidence_span="rolled nine-foxtrot out of dock three",
        polarity=Polarity.asserted,
        confidence=0.81,
    )
    assert c.evidence == {"quote": "rolled nine-foxtrot out of dock three"}
