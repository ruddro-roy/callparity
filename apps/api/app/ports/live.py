from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.ports.calle import CallTask, Plan, RunRef, RunView

log = structlog.get_logger("calle.live")

E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def require_e164_phones(phones: list[str] | None) -> list[str]:
    """Refuse empty or non-E.164 destinations. Never invent a number."""
    if not phones:
        raise ValueError("empty to_phones: refuse live POST /v1/calls")
    cleaned = [p.strip() for p in phones if p and str(p).strip()]
    if not cleaned:
        raise ValueError("empty to_phones: refuse live POST /v1/calls")
    bad = [p for p in cleaned if not E164.match(p)]
    if bad:
        raise ValueError(f"to_phones must be E.164, got {bad!r}")
    return cleaned


class LiveCalleSdk:
    """CALL-E Developer API adapter: plan_call → run_call → get_call_run.

    Maps to POST /v1/calls and GET /v1/calls/{call_id}. Requires CALLE_API_TOKEN.
    """

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or ""

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def ping(self) -> bool:
        if not self.base_url:
            return False
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/healthz", headers=self._headers())
                if resp.status_code < 500:
                    return True
                resp = client.get(f"{self.base_url}/v1/calls", headers=self._headers())
                return resp.status_code < 500
        except httpx.HTTPError:
            return False

    def plan(self, task: CallTask) -> Plan:
        if not self.token:
            raise RuntimeError(
                "CALLE_API_TOKEN is not set. Live calls require a CALL-E account token. "
                "Set USE_FIXTURES=true or provide CALLE_API_TOKEN."
            )
        phones: list[str] = []
        if task.consent:
            phones = require_e164_phones(task.to_phones)
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
            to_phones=phones,
        )

    def run(self, plan: Plan) -> RunRef:
        if not self.token:
            raise RuntimeError("CALLE_API_TOKEN is not set; refuse live run_call")
        if not plan.ready_to_run or not plan.authorized:
            raise PermissionError("plan is not authorized")
        phones = require_e164_phones(plan.to_phones)
        body: dict[str, Any] = {
            "to_phones": phones,
            "goal": plan.goal,
            "result_schema": plan.result_schema,
            "ticket_id": plan.ticket_id,
            "party_role": plan.party_role,
            "consent_disclosed": True,
        }
        log.info("calle_run_call", ticket_id=plan.ticket_id, party=plan.party_role, plan_id=plan.plan_id)
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.base_url}/v1/calls", json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        call_id = data.get("id") or data.get("call_id") or data.get("run_id")
        if not call_id:
            raise RuntimeError("CALL-E POST /v1/calls returned no call id")
        return RunRef(run_id=str(call_id), plan_id=plan.plan_id)

    def get(self, run: RunRef) -> RunView:
        if not self.token:
            raise RuntimeError("CALLE_API_TOKEN is not set; refuse get_call_run")
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{self.base_url}/v1/calls/{run.run_id}", headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        return RunView(
            run_id=run.run_id,
            status=str(data.get("status") or "unknown"),
            structured_result=data.get("structured_result") or data.get("result") or {},
            transcript=data.get("transcript") or "",
            summary=data.get("summary") or "",
        )
