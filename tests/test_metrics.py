"""GET /metrics: text exposition, counts only, public, nothing sensitive."""

from __future__ import annotations

import os

from app.metrics import reset_request_counter


def _value(body: str, name: str, label: str) -> int:
    prefix = f"{name}{{{label}}} "
    for line in body.splitlines():
        if line.startswith(prefix):
            return int(line.rsplit(" ", 1)[1])
    raise AssertionError(f"series {name}{{{label}}} missing from exposition:\n{body}")


def _wait_terminal(client, job_id: str) -> dict:
    last = None
    for _ in range(50):
        last = client.get(f"/v1/jobs/{job_id}").json()
        if last["status"] in {"completed", "failed", "cancelled"}:
            return last
    raise AssertionError(f"job stuck: {last}")


def test_metrics_is_public_text_exposition(client):
    res = client.get("/metrics", headers={"Authorization": ""})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "# TYPE callparity_requests_total counter" in res.text
    assert "# TYPE callparity_jobs_total gauge" in res.text
    for status in ("completed", "failed", "cancelled"):
        assert _value(res.text, "callparity_jobs_total", f'status="{status}"') == 0


def test_requests_counted_by_status_class(client):
    reset_request_counter()
    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/tickets/NOPE-0000").status_code == 404
    body = client.get("/metrics").text
    assert _value(body, "callparity_requests_total", 'status_class="2xx"') >= 1
    assert _value(body, "callparity_requests_total", 'status_class="4xx"') >= 1
    assert _value(body, "callparity_requests_total", 'status_class="5xx"') == 0


def test_completed_job_shows_up_in_terminal_counts(client):
    res = client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "metrics-1"})
    assert res.status_code == 202
    final = _wait_terminal(client, res.json()["id"])
    assert final["status"] == "completed"
    body = client.get("/metrics").text
    assert _value(body, "callparity_jobs_total", 'status="completed"') == 1
    assert _value(body, "callparity_jobs_total", 'status="failed"') == 0


def test_metrics_carries_no_sensitive_values(client):
    client.post("/v1/tickets/FR-1842/preview")
    body = client.get("/metrics").text
    assert os.environ["OPERATOR_TOKEN"] not in body
    assert "FR-1842" not in body
    for line in body.splitlines():
        assert line.startswith("#") or line.startswith("callparity_")
