"""Fail-closed rate limit for mutating operator routes.

Keyed by operator-token fingerprint, or by client IP when no actor is bound.
limit=0 is unlimited. A negative limit or a non-positive window denies every
mutating call. The store is in-process so compose's single uvicorn worker and
the offline test path share one implementation. healthz and readyz never call
this.
"""

from __future__ import annotations

import math
import threading
import time
from typing import NamedTuple

from fastapi import Header, HTTPException, Request

from app.config import get_settings
from app.security import require_operator

_DENIED_DETAIL = "rate limit exceeded; retry later"
_MAX_TRACKED_KEYS = 10_000


class RateDecision(NamedTuple):
    allowed: bool
    retry_after_seconds: int


class MemoryLimiter:
    def __init__(self, max_keys: int = _MAX_TRACKED_KEYS) -> None:
        if max_keys <= 0:
            raise ValueError("max_keys must be positive")
        self._max_keys = max_keys
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def hit(self, key: str, limit: int, window_s: float) -> RateDecision:
        """Return the decision for one key. Fail closed on bad config or storage pressure."""
        if limit == 0:
            return RateDecision(True, 0)
        if limit < 0 or window_s <= 0:
            return RateDecision(False, 60)
        now = time.monotonic()
        cutoff = now - window_s
        with self._lock:
            times = [t for t in self._hits.get(key, []) if t > cutoff]
            if times:
                self._hits[key] = times
            else:
                self._hits.pop(key, None)
            if len(times) >= limit:
                retry = math.ceil(times[0] + window_s - now)
                return RateDecision(False, max(1, retry))
            if key not in self._hits and len(self._hits) >= self._max_keys:
                stale_keys = [
                    tracked_key
                    for tracked_key, tracked_times in self._hits.items()
                    if tracked_times[-1] <= cutoff
                ]
                for stale_key in stale_keys:
                    del self._hits[stale_key]
                if len(self._hits) >= self._max_keys:
                    retry = min(
                        tracked_times[-1] + window_s - now
                        for tracked_times in self._hits.values()
                    )
                    return RateDecision(False, max(1, math.ceil(retry)))
            times.append(now)
            self._hits[key] = times
            return RateDecision(True, 0)


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
    authorization: str | None = Header(default=None),
    x_operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
) -> str:
    """Charge valid operators by fingerprint and invalid attempts by client IP."""
    host = request.client.host if request.client else None
    try:
        actor = require_operator(authorization, x_operator_token)
    except HTTPException:
        check_mutating_rate("", host)
        raise
    check_mutating_rate(actor, host)
    return actor
