"""Request id + one structured access line. No bodies, no headers.

Incoming X-Request-ID is accepted only when it is a canonical UUID. That
keeps an operator token or an E.164 out of the id we bind and echo. Anything
else is replaced. Query strings stay off the log line; path is the path only.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
_HEADER_BYTES = b"x-request-id"

log = structlog.get_logger("callparity.http")


def parse_request_id(raw: str | None) -> str | None:
    """Return a canonical uuid4/uuid string, or None when the value is unsafe."""
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate or len(candidate) != 36:
        return None
    try:
        parsed = uuid.UUID(candidate)
    except ValueError:
        return None
    if candidate.lower() != str(parsed):
        return None
    return str(parsed)


def new_request_id() -> str:
    return str(uuid.uuid4())


def resolve_request_id(raw: str | None) -> str:
    return parse_request_id(raw) or new_request_id()


def _incoming_header(headers: list[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() == _HEADER_BYTES:
            try:
                return value.decode("ascii")
            except UnicodeDecodeError:
                return None
    return None


class RequestIdMiddleware:
    """Assign or propagate X-Request-ID, bind it, log one line, echo it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(_incoming_header(scope.get("headers") or []))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info(
                "http.request",
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                status=status,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            structlog.contextvars.clear_contextvars()
