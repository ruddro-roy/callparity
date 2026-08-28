"""X-Request-ID propagation and the one-line-per-request structured log.

The response always carries X-Request-ID: the client's value when it is a
bounded log-safe token, a generated one otherwise. Each request produces
exactly one structured line with method, path, status, and latency_ms, tagged
with the same request id. The line goes through the phone redactor and never
contains the operator token, because bodies and headers are not logged.
"""

import json
import os
import re

HEX_ID = re.compile(r"^[0-9a-f]{32}$")

# Assembled at runtime so no phone-shaped literal lives in this file.
PHONE_SHAPED = "+1" + "5" * 10


def request_lines(output: str, path: str) -> list[dict]:
    lines = []
    for raw in output.splitlines():
        try:
            parsed = json.loads(raw)
        except ValueError:
            continue
        if parsed.get("event") == "request" and parsed.get("path") == path:
            lines.append(parsed)
    return lines


def test_response_carries_generated_request_id(client):
    res = client.get("/healthz")
    assert HEX_ID.fullmatch(res.headers["X-Request-ID"])


def test_valid_client_request_id_is_propagated(client):
    res = client.get("/healthz", headers={"X-Request-ID": "trace-41.A_b"})
    assert res.headers["X-Request-ID"] == "trace-41.A_b"


def test_unsafe_client_request_id_is_replaced(client):
    for hostile in ("with spaces", "x" * 129, "semi;colon"):
        res = client.get("/healthz", headers={"X-Request-ID": hostile})
        echoed = res.headers["X-Request-ID"]
        assert echoed != hostile
        assert HEX_ID.fullmatch(echoed)


def test_one_structured_line_per_request(client, capfd):
    capfd.readouterr()  # drop startup noise
    res = client.get("/healthz", headers={"X-Request-ID": "probe-1"})
    lines = request_lines(capfd.readouterr().out, "/healthz")
    assert len(lines) == 1
    line = lines[0]
    assert line["method"] == "GET"
    assert line["status"] == 200
    assert line["request_id"] == res.headers["X-Request-ID"] == "probe-1"
    assert isinstance(line["latency_ms"], (int, float)) and line["latency_ms"] >= 0


def test_error_responses_are_logged_with_their_status(client, capfd):
    capfd.readouterr()
    client.get("/v1/tickets/NOPE")
    (line,) = request_lines(capfd.readouterr().out, "/v1/tickets/NOPE")
    assert line["status"] == 404


def test_phone_shaped_path_is_redacted_in_the_log(client, capfd):
    capfd.readouterr()
    client.get(f"/v1/tickets/{PHONE_SHAPED}")
    out = capfd.readouterr().out
    assert PHONE_SHAPED not in out
    (line,) = request_lines(out, "/v1/tickets/[phone]")
    assert line["status"] == 404


def test_operator_token_never_reaches_the_log(client, capfd):
    capfd.readouterr()
    res = client.post("/v1/tickets/FR-1842/preview")  # client sends the auth header
    assert res.status_code == 200
    out = capfd.readouterr().out
    assert os.environ["OPERATOR_TOKEN"] not in out
    assert "authorization" not in out.lower()
