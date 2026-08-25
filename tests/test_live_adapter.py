import json

import httpx
import pytest

from app.ports.calle import CallTask, Plan, RunRef
from app.ports.live import CalleApiError, LiveCalleSdk, require_e164_phones


def refuse_to_dial(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected HTTP request: {request.method} {request.url.path}")


def ready_plan(to_phones: list[str]) -> Plan:
    return Plan(
        plan_id="p",
        ticket_id="FR-1842",
        party_role="B",
        ready_to_run=True,
        authorized=True,
        goal="g",
        to_phones=to_phones,
    )


def test_require_e164_refuses_empty():
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones([])
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones(["", "  "])
    with pytest.raises(ValueError, match="E.164"):
        require_e164_phones(["5550100001"])
    assert require_e164_phones(["+15550100002"]) == ["+15550100002"]


def test_require_e164_refuses_mixed_empty_entries():
    with pytest.raises(ValueError, match=r"positions \[1\]"):
        require_e164_phones(["+15550100002", ""])
    with pytest.raises(ValueError, match=r"positions \[1\]"):
        require_e164_phones(["+15550100002", "   "])


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
    """Mocked transport: run_call must POST the official task/recipients body."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["idempotency_key"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json={"id": "call_mock_123", "status": "queued"})

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
    assert seen["idempotency_key"]
    assert set(seen["body"]) == {"task", "recipients", "result_schema", "metadata"}
    assert seen["body"]["task"] == "Ask only observable facts."
    assert seen["body"]["recipients"] == [{"phones": ["+15550100002"]}]
    assert seen["body"]["result_schema"] == {"type": "object"}
    assert seen["body"]["metadata"] == {
        "ticket_id": "FR-1842",
        "party_role": "B",
        "consent_disclosed": True,
    }


FORBIDDEN_WIRE_FIELDS = {"to_phones", "goal", "from_number"}


def json_keys(node):
    """Yield every dict key in the tree, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from json_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from json_keys(item)


def test_json_keys_sees_nested_keys():
    assert "goal" in set(json_keys({"metadata": [{"goal": "x"}]}))


def test_post_body_is_official_shape_only():
    """No network: the wire body is exactly task/recipients/result_schema/metadata,
    and to_phones, goal, and from_number appear nowhere in it."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["idempotency_key"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json={"id": "call_mock_123"})

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(handler),
    )
    plan = sdk.plan(
        CallTask(
            ticket_id="FR-1842",
            party_role="B",
            to_phones=["+15550100002"],
            goal="Ask observable dock facts only.",
            result_schema={
                "type": "object",
                "properties": {"arrived": {"type": "boolean"}},
            },
            consent=True,
        )
    )
    sdk.run(plan)
    body = seen["body"]
    assert set(body) == {"task", "recipients", "result_schema", "metadata"}
    assert body["recipients"] == [{"phones": ["+15550100002"]}]
    assert seen["idempotency_key"]
    assert not FORBIDDEN_WIRE_FIELDS.intersection(json_keys(body))


def test_idempotency_key_stable_per_plan_content():
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers.get("Idempotency-Key"))
        return httpx.Response(201, json={"id": "call_mock_123"})

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(handler),
    )
    plan = ready_plan(["+15550100002"])
    sdk.run(plan)
    sdk.run(plan)
    sdk.run(plan.model_copy(update={"goal": "different"}))
    sdk.run(plan, idempotency_key="operator-supplied")
    assert keys[0] == keys[1]
    assert keys[2] != keys[0]
    assert keys[3] == "operator-supplied"


def test_run_refuses_response_without_id():
    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(lambda request: httpx.Response(201, json={"status": "queued"})),
    )
    with pytest.raises(CalleApiError, match="no call id"):
        sdk.run(ready_plan(["+15550100002"]))


def test_ping_treats_405_collection_as_up():
    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(lambda request: httpx.Response(405)),
    )
    assert sdk.ping() is True
    down = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )
    assert down.ping() is False


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
                "task_completed": True,
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


def test_missing_base_url_refuses_live_calls():
    sdk = LiveCalleSdk("", token="tok", transport=httpx.MockTransport(refuse_to_dial))
    with pytest.raises(RuntimeError, match="CALLE_BASE_URL"):
        sdk.run(ready_plan(["+15550100002"]))
    with pytest.raises(RuntimeError, match="CALLE_BASE_URL"):
        sdk.get(RunRef(run_id="x", plan_id="p"))


def test_missing_token_and_base_url_named_together():
    sdk = LiveCalleSdk("", token="")
    with pytest.raises(RuntimeError, match="CALLE_API_TOKEN and CALLE_BASE_URL"):
        sdk.get(RunRef(run_id="x", plan_id="p"))


def test_consent_false_never_posts():
    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(refuse_to_dial),
    )
    plan = sdk.plan(
        CallTask(
            ticket_id="FR-1842",
            party_role="B",
            to_phones=["+15550100002"],
            goal="g",
            consent=False,
        )
    )
    assert not plan.ready_to_run and not plan.authorized
    with pytest.raises(PermissionError, match="consent"):
        sdk.run(plan)


def test_e164_error_never_echoes_number():
    with pytest.raises(ValueError) as err:
        require_e164_phones(["5550100001"])
    assert "5550100001" not in str(err.value)
    assert "positions [0]" in str(err.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "Check CALLE_API_TOKEN"),
        (403, "Check CALLE_API_TOKEN"),
        (404, "Check CALLE_BASE_URL"),
        (429, "rate-limited"),
        (500, "server error"),
        (503, "server error"),
    ],
)
def test_http_errors_map_to_operator_messages(status: int, expected: str):
    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="secret-token",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, text="nope")),
    )
    with pytest.raises(CalleApiError) as err:
        sdk.run(ready_plan(["+15550100002"]))
    message = str(err.value)
    assert expected in message
    assert "secret-token" not in message
    assert "+15550100002" not in message


def test_rejected_request_detail_redacts_phones():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="cannot dial +15550100002 today")

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CalleApiError) as err:
        sdk.run(ready_plan(["+15550100002"]))
    assert "+15550100002" not in str(err.value)
    assert "[phone]" in str(err.value)


def test_timeout_maps_to_operator_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    sdk = LiveCalleSdk(
        "https://api.call-e.invalid",
        token="tok",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CalleApiError, match="timed out"):
        sdk.run(ready_plan(["+15550100002"]))
    with pytest.raises(CalleApiError, match="timed out"):
        sdk.get(RunRef(run_id="x", plan_id="p"))


@pytest.fixture
def clean_settings(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_fixture_mode_ignores_live_env(clean_settings):
    clean_settings.setenv("USE_FIXTURES", "true")
    clean_settings.setenv("CALLE_BASE_URL", "")
    clean_settings.setenv("CALLE_API_TOKEN", "")
    from app.deps import get_calle
    from app.fixtures.calle import FixtureCalle

    assert isinstance(get_calle(), FixtureCalle)


def test_live_mode_without_config_fails_at_first_plan(clean_settings):
    clean_settings.setenv("USE_FIXTURES", "false")
    clean_settings.setenv("CALLE_BASE_URL", "")
    clean_settings.setenv("CALLE_API_TOKEN", "")
    from app.deps import get_calle

    sdk = get_calle()
    assert isinstance(sdk, LiveCalleSdk)
    task = CallTask(
        ticket_id="FR-1842",
        party_role="B",
        to_phones=["+15550100002"],
        goal="g",
        consent=True,
    )
    with pytest.raises(RuntimeError, match="CALLE_API_TOKEN and CALLE_BASE_URL"):
        sdk.plan(task)


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
