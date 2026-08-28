"""The mutating routes share one fixed-window budget per actor.

The key is the operator-token fingerprint when the valid token is presented,
the client IP otherwise, so authenticated and unauthenticated traffic land in
separate buckets and neither is unlimited. The check runs before the token
gate: a flood without credentials meets 429, not an unmetered 401. healthz
and readyz never pass through the limiter.
"""

import os

import pytest
from app.ratelimit import WINDOW_SECONDS, FixedWindowLimiter
from fastapi.testclient import TestClient

OPERATOR_TOKEN = os.environ["OPERATOR_TOKEN"]
AUTH = {"Authorization": f"Bearer {OPERATOR_TOKEN}"}
LIMIT = 3


@pytest.fixture
def limited_client(tmp_path, monkeypatch):
    """Same wiring as the shared client fixture, but with a 3/minute budget."""
    db = tmp_path / "rl.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db}")
    monkeypatch.setenv("REDIS_OPTIONAL", "true")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("USE_FIXTURES", "true")
    monkeypatch.setenv("PLAYBACK_DELAY_MS", "0")
    monkeypatch.setenv("OPERATOR_TOKEN", OPERATOR_TOKEN)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(LIMIT))
    # Freeze the limiter clock inside one window so a real 60s boundary
    # cannot split a test's requests across two budgets.
    monkeypatch.setattr("app.ratelimit._now", lambda: 1_200_000.0)

    from app.config import get_settings
    from app.db import init_db, reset_engine
    from app.ratelimit import reset_rate_limiter

    get_settings.cache_clear()
    reset_engine()
    reset_rate_limiter()
    init_db()
    from seed_demo_data import seed

    seed()
    from app.main import app

    with TestClient(app) as c:
        yield c
    reset_engine()
    get_settings.cache_clear()
    reset_rate_limiter()


def test_429_after_the_budget_with_retry_after(limited_client):
    for _ in range(LIMIT):
        assert limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH).status_code == 200
    res = limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH)
    assert res.status_code == 429
    assert 1 <= int(res.headers["Retry-After"]) <= WINDOW_SECONDS
    assert "rate limit exceeded" in res.json()["detail"]
    assert str(LIMIT) in res.json()["detail"]


def test_budget_is_shared_across_all_five_mutating_routes(limited_client):
    for _ in range(LIMIT):
        assert limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH).status_code == 200
    over_budget = [
        limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH),
        limited_client.post("/v1/tickets/FR-1842/parity", headers=AUTH),
        limited_client.post(
            "/v1/tickets/FR-1842/parity/import",
            headers=AUTH,
            json={"call_id_a": "call_a", "call_id_b": "call_b"},
        ),
        limited_client.post(
            "/v1/tickets",
            headers=AUTH,
            json={"id": "FR-9999", "domain": "d", "fact": "f", "entities": {}, "parties": []},
        ),
        limited_client.post("/v1/jobs/job_none/cancel", headers=AUTH),
    ]
    assert [r.status_code for r in over_budget] == [429] * 5


def test_unauthenticated_flood_is_metered_by_ip_before_auth(limited_client):
    statuses = [
        limited_client.post("/v1/tickets/FR-1842/preview").status_code for _ in range(LIMIT + 2)
    ]
    assert statuses == [401] * LIMIT + [429] * 2


def test_operator_and_ip_buckets_are_separate(limited_client):
    for _ in range(LIMIT):
        assert limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH).status_code == 200
    # The operator budget is spent, but a tokenless request draws from the IP
    # bucket, so it reaches the auth gate and gets 401, not 429.
    assert limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH).status_code == 429
    assert limited_client.post("/v1/tickets/FR-1842/preview").status_code == 401


def test_wrong_token_counts_against_ip_not_operator(limited_client):
    bad = {"Authorization": "Bearer not-the-operator-token"}
    statuses = [
        limited_client.post("/v1/tickets/FR-1842/preview", headers=bad).status_code
        for _ in range(LIMIT + 1)
    ]
    assert statuses == [401] * LIMIT + [429]
    # The real operator still has budget: forged tokens cannot starve it.
    assert limited_client.post("/v1/tickets/FR-1842/preview", headers=AUTH).status_code == 200


def test_health_and_readiness_stay_unlimited(limited_client):
    for _ in range(LIMIT * 4):
        assert limited_client.get("/healthz").status_code == 200
        assert limited_client.get("/readyz").status_code == 200
    # Read paths stay open too; only the five mutating routes are metered.
    assert limited_client.get("/v1/tickets/FR-1842").status_code == 200


def test_window_resets_and_retry_after_counts_down():
    limiter = FixedWindowLimiter()
    window_start = 1_200_000.0  # aligned: divisible by WINDOW_SECONDS
    assert limiter.check("op_x", 2, now=window_start) is None
    assert limiter.check("op_x", 2, now=window_start + 1) is None
    assert limiter.check("op_x", 2, now=window_start + 10) == WINDOW_SECONDS - 10
    assert limiter.check("op_x", 2, now=window_start + WINDOW_SECONDS - 1) == 1
    # A new window opens with a fresh budget.
    assert limiter.check("op_x", 2, now=window_start + WINDOW_SECONDS) is None
    # Other keys are unaffected throughout.
    assert limiter.check("op_y", 2, now=window_start + 10) is None
