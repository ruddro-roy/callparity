"""Place one live CALL-E call that asks a public business for its hours.

Operator path, separate from the FR-1842 / FR-1900 / FR-1888 fixtures. Refuses
to dial unless the environment carries CALLE_API_TOKEN, CALLE_BASE_URL, an
E.164 CALLE_LIVE_TO_PHONE, and CALLE_CONSENT=yes. Prints only call_id and
status; the destination number and the token never reach stdout or stderr.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Mapping

import httpx
import structlog

ROOTS = [
    Path(__file__).resolve().parent.parent / "apps" / "api",
    Path("/app"),
]
for root in ROOTS:
    if (root / "app").exists() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

from app.ports.calle import CallTask
from app.ports.live import E164, LiveCalleSdk

GOAL = (
    "Recording and consent disclosure first: say the call may be recorded and "
    "ask if that is okay. Then ask for today's opening and closing times and "
    "the regular weekly hours of operation. Thank them and end the call."
)
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "hours_today": {"type": "object", "properties": {"answer": {"type": "string"}}},
        "hours_weekly": {"type": "object", "properties": {"answer": {"type": "string"}}},
    },
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "unreachable", "voicemail", "no_answer"}


def _refuse(reason: str) -> int:
    print(f"refusing to dial: {reason}", file=sys.stderr)
    return 2


def main(
    env: Mapping[str, str],
    transport: httpx.BaseTransport | None = None,
    poll_interval_s: float = 5.0,
    max_polls: int = 60,
) -> int:
    token = (env.get("CALLE_API_TOKEN") or "").strip()
    base_url = (env.get("CALLE_BASE_URL") or "").strip()
    to_phone = (env.get("CALLE_LIVE_TO_PHONE") or "").strip()
    consent = (env.get("CALLE_CONSENT") or "").strip().lower()

    missing = [
        name
        for name, value in (
            ("CALLE_API_TOKEN", token),
            ("CALLE_BASE_URL", base_url),
            ("CALLE_LIVE_TO_PHONE", to_phone),
        )
        if not value
    ]
    if missing:
        return _refuse(f"set {' and '.join(missing)}")
    if consent != "yes":
        return _refuse("set CALLE_CONSENT=yes to confirm the callee may be dialed and recorded")
    if not E164.match(to_phone):
        return _refuse("CALLE_LIVE_TO_PHONE is not E.164 (+ then 8 to 15 digits)")

    # stdout is the contract: only call_id and status lines land there.
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
    sdk = LiveCalleSdk(base_url, token=token, transport=transport)
    task = CallTask(
        ticket_id="LIVE-HOURS",
        party_role="B",
        to_phones=[to_phone],
        goal=GOAL,
        result_schema=RESULT_SCHEMA,
        consent=True,
    )
    try:
        # A rerun of the script is a new operation, not a retry, so each
        # invocation gets its own Idempotency-Key.
        run = sdk.run(sdk.plan(task), idempotency_key=f"live-hours-{uuid.uuid4().hex[:12]}")
    except (RuntimeError, ValueError, PermissionError) as exc:
        print(f"call failed: {exc}", file=sys.stderr)
        return 1

    print(f"call_id {run.run_id}")
    status = ""
    for _ in range(max_polls):
        try:
            view = sdk.get(run)
        except RuntimeError as exc:
            print(f"poll failed: {exc}", file=sys.stderr)
            return 1
        if view.status != status:
            status = view.status
            print(f"status {status}")
        if status in TERMINAL_STATUSES:
            break
        time.sleep(poll_interval_s)
    return 0


if __name__ == "__main__":
    sys.exit(main(os.environ))
