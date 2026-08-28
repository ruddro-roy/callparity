"""Fixed-window rate limit on the mutating routes.

The budget is per operator-token fingerprint when the request carries the
valid token, falling back to the client IP otherwise, and to one shared
bucket when no client address exists, so no request is ever unlimited. The
check runs before the operator-token gate (it is declared first in the route
decorators), which keeps unauthenticated spam IP-limited instead of stopping
at 401 unmetered.

Fail-closed by construction: a misconfigured RATE_LIMIT_PER_MINUTE refuses to
boot (Settings validates ge=1), an unknown origin still lands in a bucket,
and an unexpected error inside the check denies the request rather than
waving it through. Counters live in process memory, which matches the
single-instance compose deployment; healthz and readyz never pass through
here and stay unlimited.
"""

import threading
import time

from fastapi import Header, HTTPException, Request

from app.config import get_settings
from app.security import presented_actor

WINDOW_SECONDS = 60
# Prune stale windows once the table outgrows any sane number of concurrent
# actors, so an address scan cannot grow memory without bound.
_PRUNE_THRESHOLD = 4096


def _now() -> float:
    """Clock seam: tests freeze this so a window boundary cannot flake them."""
    return time.time()


class FixedWindowLimiter:
    """Counts requests per key in aligned windows of WINDOW_SECONDS."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def check(self, key: str, limit: int, now: float | None = None) -> int | None:
        """Count one request. None if allowed, else seconds until the window resets."""
        ts = int(_now() if now is None else now)
        window = ts - (ts % WINDOW_SECONDS)
        with self._lock:
            if len(self._counts) > _PRUNE_THRESHOLD:
                self._counts = {k: v for k, v in self._counts.items() if v[0] == window}
            start, count = self._counts.get(key, (window, 0))
            if start != window:
                start, count = window, 0
            count += 1
            self._counts[key] = (window, count)
            if count > limit:
                return max(1, WINDOW_SECONDS - (ts - window))
        return None

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


_limiter = FixedWindowLimiter()


def reset_rate_limiter() -> None:
    _limiter.reset()


def rate_limited(
    request: Request,
    authorization: str | None = Header(default=None),
    x_operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
) -> None:
    """Dependency for the mutating routes: preview, parity, import, tickets, cancel."""
    limit = get_settings().rate_limit_per_minute
    key = presented_actor(authorization, x_operator_token)
    if key is None:
        client = request.client
        key = f"ip_{client.host}" if client and client.host else "ip_unknown"
    retry_after = _limiter.check(key, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=(
                f"rate limit exceeded: more than {limit} requests per minute from "
                f"this operator or address; retry after {retry_after}s"
            ),
            headers={"Retry-After": str(retry_after)},
        )
