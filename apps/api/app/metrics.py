"""In-process metrics in the Prometheus text exposition format.

No new dependencies and nothing sensitive: the exposition carries only
counts and fixed labels, never identifiers, tokens, or payloads. Requests
are tallied by status class in process memory, so like any in-process
counter they restart at zero with the process. Terminal job counts come
from the database at scrape time, so they survive restarts.
"""

from __future__ import annotations

import threading

from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.models.orm import JobRow
from app.models.schemas import JobStatus

_STATUS_CLASSES = ("1xx", "2xx", "3xx", "4xx", "5xx")

TERMINAL_JOB_STATUSES = (
    JobStatus.completed.value,
    JobStatus.failed.value,
    JobStatus.cancelled.value,
)


class RequestCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_class = dict.fromkeys(_STATUS_CLASSES, 0)

    def record(self, status_code: int) -> None:
        cls = f"{status_code // 100}xx"
        with self._lock:
            if cls in self._by_class:
                self._by_class[cls] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._by_class)

    def reset(self) -> None:
        with self._lock:
            for cls in self._by_class:
                self._by_class[cls] = 0


request_counter = RequestCounter()


def reset_request_counter() -> None:
    request_counter.reset()


class RequestCounterMiddleware:
    """Count every HTTP response by status class. Pure ASGI, no buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def counting_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                request_counter.record(message["status"])
            await send(message)

        await self.app(scope, receive, counting_send)


def render_metrics(session: Session) -> str:
    lines = [
        "# HELP callparity_requests_total HTTP responses sent, by status class.",
        "# TYPE callparity_requests_total counter",
    ]
    for cls, count in sorted(request_counter.snapshot().items()):
        lines.append(f'callparity_requests_total{{status_class="{cls}"}} {count}')

    terminal = dict.fromkeys(TERMINAL_JOB_STATUSES, 0)
    rows = (
        session.query(JobRow.status, func.count(JobRow.id))
        .filter(JobRow.status.in_(TERMINAL_JOB_STATUSES))
        .group_by(JobRow.status)
        .all()
    )
    for status, count in rows:
        terminal[status] = count
    lines += [
        "# HELP callparity_jobs_total Parity jobs in a terminal status.",
        "# TYPE callparity_jobs_total gauge",
    ]
    for status in TERMINAL_JOB_STATUSES:
        lines.append(f'callparity_jobs_total{{status="{status}"}} {terminal[status]}')
    return "\n".join(lines) + "\n"
