"""Fail-closed rate limit for mutating operator routes.

Keyed by operator-token fingerprint, or by client IP when no actor is bound.
limit=0 is unlimited. A negative limit or a non-positive window denies every
mutating call. The store is in-process so compose's single uvicorn worker and
the offline test path share one implementation. healthz and readyz never call
this.
"""

from __future__ import annotations

import threading
import time

from fastapi import Depends, HTTPException, Request

from app.config import get_settings
from app.security import require_operator

_DENIED_DETAIL = "rate limit exceeded; retry later"


class MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Fail closed on bad config."""
        if limit == 0:
            return True, 0
        if limit < 0 or window_s <= 0:
            return False, 60
        now = time.monotonic()
        cutoff = now - window_s
        with self._lock:
            times = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(times) >= limit:
                self._hits[key] = times
                retry = int(times[0] + window_s - now) + 1
                return False, max(1, retry)
            times.append(now)
            self._hits[key] = times
            return True, 0


_limiter = MemoryLimiter()


def reset_rate_limiter() -> None:
    _limiter.reset()


def limit_key(actor: str, client_host: str | None) -> str:
    if actor:
        return f"op:{actor}"
    if client_host:
        return f"ip:{client_host}"
    raise HTTPException(
        status_code=429,
        detail=_DENIED_DETAIL,
        headers={"Retry-After": "60"},
    )


def check_mutating_rate(actor: str, client_host: str | None) -> None:
    settings = get_settings()
    allowed, retry_after = _limiter.hit(
        limit_key(actor, client_host),
        settings.mutating_rate_limit,
        float(settings.mutating_rate_window_seconds),
    )
    if allowed:
        return
    raise HTTPException(
        status_code=429,
        detail=_DENIED_DETAIL,
        headers={"Retry-After": str(retry_after)},
    )


def require_operator_within_rate(
    request: Request,
    actor: str = Depends(require_operator),
) -> str:
    host = request.client.host if request.client else None
    check_mutating_rate(actor, host)
    return actor
