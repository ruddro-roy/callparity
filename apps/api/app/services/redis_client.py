from __future__ import annotations

import structlog

from app.config import get_settings

log = structlog.get_logger("redis")

_memory: dict[str, str] = {}
_client = None
_ok: bool | None = None


def get_redis():
    global _client
    settings = get_settings()
    if settings.redis_optional:
        return None
    if _client is None:
        import redis

        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def ping_redis() -> bool:
    global _ok
    settings = get_settings()
    if settings.redis_optional:
        _ok = True
        return True
    try:
        client = get_redis()
        _ok = bool(client.ping())
        return _ok
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_ping_failed", error=str(exc))
        _ok = False
        return False


def store_pointer(sha: str, body: str) -> None:
    settings = get_settings()
    _memory[sha] = body
    if settings.redis_optional:
        return
    try:
        client = get_redis()
        client.set(f"ptr:{sha}", body)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_store_failed", error=str(exc))


def acquire_lock(key: str, ttl: int = 120) -> bool:
    settings = get_settings()
    if settings.redis_optional:
        if key in _memory:
            return False
        _memory[key] = "1"
        return True
    try:
        client = get_redis()
        return bool(client.set(f"lock:{key}", "1", nx=True, ex=ttl))
    except Exception:
        if key in _memory:
            return False
        _memory[key] = "1"
        return True
