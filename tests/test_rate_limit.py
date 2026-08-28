"""Mutating routes are limited per actor; healthz and reads stay unlimited."""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.rate_limit import MemoryLimiter, check_mutating_rate, limit_key, reset_rate_limiter
from fastapi import HTTPException


def test_limit_key_prefers_fingerprint_then_ip():
    assert limit_key("op_abc", "203.0.113.9") == "op:op_abc"
    assert limit_key("", "203.0.113.9") == "ip:203.0.113.9"
    with pytest.raises(HTTPException) as exc:
        limit_key("", None)
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"


def test_memory_limiter_separates_keys_and_respects_zero():
    lim = MemoryLimiter()
    assert lim.hit("a", 2, 60.0) == (True, 0)
    assert lim.hit("a", 2, 60.0) == (True, 0)
    allowed, retry = lim.hit("a", 2, 60.0)
    assert allowed is False
    assert retry >= 1
    assert lim.hit("b", 2, 60.0)[0] is True
    assert lim.hit("a", 0, 60.0)[0] is True


def test_memory_limiter_fails_closed_on_bad_config():
    lim = MemoryLimiter()
    assert lim.hit("a", -1, 60.0) == (False, 60)
    assert lim.hit("a", 5, 0) == (False, 60)
    assert lim.hit("a", 5, -3) == (False, 60)


def test_memory_limiter_bounds_keys_and_reclaims_stale_buckets(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("app.rate_limit.time.monotonic", lambda: now[0])
    lim = MemoryLimiter(max_keys=2)

    assert lim.hit("a", 2, 60.0).allowed
    assert lim.hit("b", 2, 60.0).allowed
    denied = lim.hit("c", 2, 60.0)
    assert not denied.allowed
    assert denied.retry_after_seconds == 60

    now[0] = 61.0
    assert lim.hit("c", 2, 60.0).allowed


def test_preview_exceeds_limit_returns_429(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "2")
    monkeypatch.setenv("MUTATING_RATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    reset_rate_limiter()
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    res = client.post("/v1/tickets/FR-1842/preview")
    assert res.status_code == 429
    assert res.json()["detail"] == "rate limit exceeded; retry later"
    assert int(res.headers["Retry-After"]) >= 1


def test_limit_is_shared_across_mutating_routes(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "2")
    get_settings.cache_clear()
    reset_rate_limiter()
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    assert client.post("/v1/tickets/FR-1842/parity", headers={"Idempotency-Key": "rl-1"}).status_code == 202
    denied = client.post("/v1/jobs/does-not-exist/cancel")
    assert denied.status_code == 429
    assert "Retry-After" in denied.headers


def test_healthz_readyz_and_gets_stay_unlimited(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "1")
    get_settings.cache_clear()
    reset_rate_limiter()
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 429
    for _ in range(8):
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        assert client.get("/v1/tickets/FR-1842").status_code == 200


def test_unlimited_when_limit_is_zero(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "0")
    get_settings.cache_clear()
    reset_rate_limiter()
    for _ in range(6):
        assert client.post("/v1/tickets/FR-1842/preview").status_code == 200


def test_missing_token_is_still_401_not_429(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "1")
    get_settings.cache_clear()
    reset_rate_limiter()
    res = client.post("/v1/tickets/FR-1842/preview", headers={"Authorization": ""})
    assert res.status_code == 401


def test_invalid_tokens_fall_back_to_client_ip_bucket(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "2")
    monkeypatch.setenv("MUTATING_RATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    reset_rate_limiter()
    invalid = {"Authorization": "Bearer wrong"}

    assert client.post("/v1/tickets/FR-1842/preview", headers=invalid).status_code == 401
    assert client.post("/v1/tickets/FR-1842/preview", headers=invalid).status_code == 401
    denied = client.post("/v1/tickets/FR-1842/preview", headers=invalid)
    assert denied.status_code == 429
    assert denied.json()["detail"] == "rate limit exceeded; retry later"
    assert int(denied.headers["Retry-After"]) >= 1

    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 429


def test_invalid_tokens_stay_401_when_limit_is_zero(client, monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "0")
    get_settings.cache_clear()
    reset_rate_limiter()

    for _ in range(6):
        response = client.post(
            "/v1/tickets/FR-1842/preview",
            headers={"Authorization": "Bearer wrong"},
        )
        assert response.status_code == 401


def test_check_mutating_rate_uses_settings(monkeypatch):
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "1")
    monkeypatch.setenv("MUTATING_RATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    reset_rate_limiter()
    check_mutating_rate("op_one", "127.0.0.1")
    with pytest.raises(HTTPException) as exc:
        check_mutating_rate("op_one", "127.0.0.1")
    assert exc.value.status_code == 429
    check_mutating_rate("op_two", "127.0.0.1")
    get_settings.cache_clear()
    reset_rate_limiter()
