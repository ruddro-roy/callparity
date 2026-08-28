"""Request-id propagation and one structured log line per request.

Pure ASGI, not BaseHTTPMiddleware, so the SSE stream in
/v1/tickets/{id}/events passes through without re-buffering. The log line
carries method, path, status, and latency_ms only: never a body, a query
string, or a header, so neither the operator token nor a phone number can
enter it. The line still runs through the redaction processor in
logging_conf like every other event, and the bound request_id rides along on
everything the handler logs.
"""

import re
import time
import uuid

import structlog

REQUEST_ID_HEADER = "X-Request-ID"
# Bounded, log-safe shape. A client value that does not match is replaced
# with a generated id and never echoed back, so arbitrary bytes cannot be
# reflected into headers or smuggled into log lines.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

logger = structlog.get_logger("callparity.request")


def _incoming_request_id(scope: dict) -> str | None:
    for name, value in scope.get("headers") or ():
        if name.lower() == b"x-request-id":
            try:
                candidate = value.decode("ascii")
            except UnicodeDecodeError:
                return None
            return candidate if _VALID_REQUEST_ID.fullmatch(candidate) else None
    return None


class RequestContextMiddleware:
    """Assign or propagate X-Request-ID; echo it back; log the request once."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        # If the app crashes before sending a response, the server turns that
        # into a 500, so that is what the log line reports.
        status = 500
        start = time.perf_counter()

        async def send_with_request_id(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode("ascii"))
                )
            await send(message)

        tokens = structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            structlog.contextvars.reset_contextvars(**tokens)
