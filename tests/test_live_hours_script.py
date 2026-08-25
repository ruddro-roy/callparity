import json

import httpx
import pytest
import structlog

import live_hours_call

PHONE = "+15550100002"


@pytest.fixture(autouse=True)
def fresh_structlog():
    """Undo logger state cached by earlier app tests, then restore defaults.

    In a real run the script is a fresh process, configures structlog before
    the first log call, and the adapter log lands on stderr. Inside the suite,
    app tests already configured structlog to stdout and the adapter's lazy
    proxy cached that binding, so drop the cache to reproduce the fresh state.
    """
    from app.ports import live

    structlog.reset_defaults()
    live.log.__dict__.pop("bind", None)
    yield
    structlog.reset_defaults()
    live.log.__dict__.pop("bind", None)

FULL_ENV = {
    "CALLE_API_TOKEN": "test-token",
    "CALLE_BASE_URL": "https://api.call-e.invalid",
    "CALLE_LIVE_TO_PHONE": PHONE,
    "CALLE_CONSENT": "yes",
}


def refuse_to_dial(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected HTTP request: {request.method} {request.url.path}")


@pytest.mark.parametrize(
    "missing", ["CALLE_API_TOKEN", "CALLE_BASE_URL", "CALLE_LIVE_TO_PHONE"]
)
def test_refuses_when_env_missing(missing, capsys):
    env = {k: v for k, v in FULL_ENV.items() if k != missing}
    code = live_hours_call.main(env, transport=httpx.MockTransport(refuse_to_dial))
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert missing in err


def test_refuses_without_consent(capsys):
    env = {**FULL_ENV, "CALLE_CONSENT": ""}
    code = live_hours_call.main(env, transport=httpx.MockTransport(refuse_to_dial))
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert "CALLE_CONSENT=yes" in err


def test_refuses_non_e164_without_echoing_it(capsys):
    env = {**FULL_ENV, "CALLE_LIVE_TO_PHONE": "555-0100"}
    code = live_hours_call.main(env, transport=httpx.MockTransport(refuse_to_dial))
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert "E.164" in err
    assert "555-0100" not in err and "5550100" not in err


def test_places_call_and_prints_only_call_id_and_status(capsys):
    polls = {"n": 0}
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["path"] = request.url.path
            seen["auth"] = request.headers.get("Authorization")
            seen["idempotency_key"] = request.headers.get("Idempotency-Key")
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(201, json={"id": "call_live_1", "status": "queued"})
        polls["n"] += 1
        status = "queued" if polls["n"] == 1 else "completed"
        return httpx.Response(200, json={"id": "call_live_1", "status": status})

    code = live_hours_call.main(
        FULL_ENV, transport=httpx.MockTransport(handler), poll_interval_s=0
    )
    out, err = capsys.readouterr()
    assert code == 0
    assert out == "call_id call_live_1\nstatus queued\nstatus completed\n"
    assert PHONE not in out and "test-token" not in out
    assert PHONE not in err and "test-token" not in err
    assert "+1555***0002" in err
    assert seen["path"] == "/v1/calls"
    assert seen["auth"] == "Bearer test-token"
    assert seen["idempotency_key"].startswith("live-hours-")
    assert seen["body"]["recipients"] == [{"phones": [PHONE]}]
    assert seen["body"]["metadata"]["consent_disclosed"] is True
    assert "hours of operation" in seen["body"]["task"]


def test_api_rejection_stays_secret_free(capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad token")

    code = live_hours_call.main(FULL_ENV, transport=httpx.MockTransport(handler))
    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    assert "CALLE_API_TOKEN" in err
    assert "test-token" not in err
    assert PHONE not in err
