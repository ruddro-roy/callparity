from __future__ import annotations

import hashlib
import re
from typing import Any

import httpx
import structlog

from app.logging_conf import mask_e164
from app.ports.calle import CallTask, Plan, RunRef, RunView

log = structlog.get_logger("calle.live")

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_DIGIT_RUN = re.compile(r"\+?\d[\d\s().-]{6,}\d")

_RUN_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
_GET_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class CalleApiError(RuntimeError):
    """Operator-facing CALL-E failure. Messages carry no token and no full phone."""


def redact_phones(text: str) -> str:
    """Replace anything that could be a phone number with a placeholder."""
    return _DIGIT_RUN.sub("[phone]", text)


def require_e164_phones(phones: list[str] | None) -> list[str]:
    """Refuse empty or non-E.164 destinations. Never invent or echo a number."""
    if not phones:
        raise ValueError("empty to_phones: refuse live POST /v1/calls")
    cleaned = [p.strip() for p in phones if p and str(p).strip()]
    if not cleaned:
        raise ValueError("empty to_phones: refuse live POST /v1/calls")
    bad = [i for i, p in enumerate(cleaned) if not E164.match(p)]
    if bad:
        raise ValueError(
            f"to_phones entries at positions {bad} are not E.164 "
            "(+ then 8 to 15 digits): refuse live POST /v1/calls"
        )
    return cleaned


def default_idempotency_key(plan: Plan, phones: list[str]) -> str:
    """Stable per authorization: same plan content retries as the same call."""
    digest = hashlib.sha256("|".join([plan.goal, *sorted(phones)]).encode("utf-8")).hexdigest()
    return f"{plan.plan_id}-{digest[:12]}"


class LiveCalleSdk:
    """CALL-E Calls API adapter (docs.heycall-e.com/calls).

    POST /v1/calls sends task, recipients[].phones, result_schema, and metadata
    with an Idempotency-Key header; GET /v1/calls/{call_id} reads the state.
    Fails closed: a missing CALLE_API_TOKEN or CALLE_BASE_URL, a non-E.164
    destination, or an unauthorized plan means no request leaves the process.
    Tests inject an httpx transport; production uses the default network one.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self._transport = transport

    def _require_config(self) -> None:
        missing = [
            name
            for name, value in (
                ("CALLE_API_TOKEN", self.token),
                ("CALLE_BASE_URL", self.base_url),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"{' and '.join(missing)} not set. Live calls need both. "
                "Set them in the environment or run with USE_FIXTURES=true."
            )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        timeout: httpx.Timeout,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = self._headers()
        if extra_headers:
            headers.update(extra_headers)
        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as client:
                resp = client.request(
                    method, f"{self.base_url}{path}", json=json_body, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise CalleApiError(
                f"CALL-E request timed out: {method} {path}. Retry, or check CALLE_BASE_URL."
            ) from exc
        except httpx.TransportError as exc:
            raise CalleApiError(
                f"cannot reach CALL-E at {self.base_url} ({type(exc).__name__}). Check CALLE_BASE_URL."
            ) from exc
        if resp.status_code >= 400:
            raise CalleApiError(self._describe_failure(method, path, resp))
        try:
            data = resp.json()
        except ValueError as exc:
            raise CalleApiError(
                f"CALL-E returned non-JSON (HTTP {resp.status_code}) on {method} {path}."
            ) from exc
        return data if isinstance(data, dict) else {}

    def _describe_failure(self, method: str, path: str, resp: httpx.Response) -> str:
        status = resp.status_code
        where = f"{method} {path}"
        if status in (401, 403):
            return f"CALL-E rejected the token (HTTP {status}) on {where}. Check CALLE_API_TOKEN."
        if status == 404:
            return f"CALL-E returned 404 on {where}. Check CALLE_BASE_URL and the call id."
        if status == 429:
            return f"CALL-E rate-limited the request (HTTP 429) on {where}. Retry later."
        if status >= 500:
            return f"CALL-E server error (HTTP {status}) on {where}. Retry later."
        detail = redact_phones(resp.text[:200])
        return f"CALL-E rejected the request (HTTP {status}) on {where}: {detail}"

    def ping(self) -> bool:
        # GET on the collection is 405 on the real API, so any response
        # below 500 proves the service is reachable.
        if not self.base_url:
            return False
        try:
            with httpx.Client(timeout=3.0, transport=self._transport) as client:
                resp = client.get(f"{self.base_url}/v1/calls", headers=self._headers())
                return resp.status_code < 500
        except httpx.HTTPError:
            return False

    def plan(self, task: CallTask) -> Plan:
        self._require_config()
        if not task.consent:
            return Plan(
                plan_id=f"plan_{task.ticket_id}_{task.party_role}",
                ticket_id=task.ticket_id,
                party_role=task.party_role,
                ready_to_run=False,
                authorized=False,
                goal=task.goal,
                result_schema=task.result_schema,
                to_phones=list(task.to_phones or []),
            )
        return Plan(
            plan_id=f"plan_{task.ticket_id}_{task.party_role}",
            ticket_id=task.ticket_id,
            party_role=task.party_role,
            ready_to_run=True,
            authorized=True,
            goal=task.goal,
            result_schema=task.result_schema,
            to_phones=require_e164_phones(task.to_phones),
        )

    def run(self, plan: Plan, idempotency_key: str | None = None) -> RunRef:
        self._require_config()
        if not plan.ready_to_run or not plan.authorized:
            raise PermissionError(
                "plan is not authorized: consent was not disclosed, so no POST /v1/calls"
            )
        phones = require_e164_phones(plan.to_phones)
        # The Calls API has no from_number request field; the workspace's
        # default outbound number places the call.
        body: dict[str, Any] = {
            "task": plan.goal,
            "recipients": [{"phones": phones}],
            "result_schema": plan.result_schema,
            "metadata": {
                "ticket_id": plan.ticket_id,
                "party_role": plan.party_role,
                "consent_disclosed": True,
            },
        }
        log.info(
            "calle_run_call",
            ticket_id=plan.ticket_id,
            party=plan.party_role,
            plan_id=plan.plan_id,
            to=[mask_e164(p) for p in phones],
        )
        data = self._request(
            "POST",
            "/v1/calls",
            _RUN_TIMEOUT,
            json_body=body,
            extra_headers={
                "Idempotency-Key": idempotency_key or default_idempotency_key(plan, phones)
            },
        )
        call_id = data.get("id")
        if not call_id:
            raise CalleApiError("CALL-E POST /v1/calls returned no call id")
        return RunRef(run_id=str(call_id), plan_id=plan.plan_id)

    def get(self, run: RunRef) -> RunView:
        self._require_config()
        data = self._request("GET", f"/v1/calls/{run.run_id}", _GET_TIMEOUT)
        return RunView(
            run_id=run.run_id,
            status=str(data.get("status") or "unknown"),
            structured_result=data.get("structured_result") or {},
            transcript=data.get("transcript") or "",
            summary=data.get("summary") or "",
        )
