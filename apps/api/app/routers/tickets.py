from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import get_calle, get_live_reader
from app.models.orm import ImportAuditRow, TicketRow, TranscriptPointer
from app.models.schemas import Job, ParityImportRequest, Ticket, TicketCreate
from app.ports.calle import CallePort, RunView
from app.ports.live import CalleApiError
from app.ratelimit import rate_limited
from app.security import require_operator
from app.services.events import encode, snapshot
from app.services.extractor import extract_claims
from app.services.idempotency import sha256_text
from app.services.jobs import enqueue_parity
from app.services.parity import import_parity_from_calls, latest_card
from app.services.planner import compile_refutation

router = APIRouter(prefix="/v1")


# dependencies=[rate_limited] on the mutating routes runs the limiter before
# require_operator, so unauthenticated floods are IP-limited, not just 401ed.
@router.post("/tickets", status_code=201, dependencies=[Depends(rate_limited)])
def create_ticket(
    payload: TicketCreate,
    session: Session = Depends(get_session),
    _actor: str = Depends(require_operator),
) -> Ticket:
    if session.get(TicketRow, payload.id):
        raise HTTPException(409, "ticket exists")
    session.add(
        TicketRow(
            id=payload.id,
            domain=payload.domain,
            fact=payload.fact,
            entities=payload.entities,
            parties=[p.model_dump() for p in payload.parties],
            sla_usd_per_hour=payload.sla_usd_per_hour,
        )
    )
    return payload


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(TicketRow, ticket_id)
    if not row:
        raise HTTPException(404, "ticket not found")
    card = latest_card(session, ticket_id)
    ptrs = session.query(TranscriptPointer).filter(TranscriptPointer.ticket_id == ticket_id).all()
    return {
        "ticket": Ticket(
            id=row.id,
            domain=row.domain,
            fact=row.fact,
            entities=row.entities,
            parties=row.parties,
            sla_usd_per_hour=row.sla_usd_per_hour,
        ).model_dump(mode="json"),
        "action": card.model_dump(mode="json") if card else None,
        "graph": [e.model_dump(mode="json") for e in card.edges] if card else [],
        "transcript_pointers": [p.sha256 for p in ptrs],
        "spans": [p.body[:80] for p in ptrs],
    }


@router.post("/tickets/{ticket_id}/parity", dependencies=[Depends(rate_limited)])
def start_parity(
    ticket_id: str,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    calle: CallePort = Depends(get_calle),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _actor: str = Depends(require_operator),
) -> JSONResponse:
    if not session.get(TicketRow, ticket_id):
        raise HTTPException(404, "ticket not found")
    row = session.get(TicketRow, ticket_id)
    for party in row.parties:
        if not party.get("consent"):
            raise HTTPException(403, f"consent required for party {party.get('role')}")
    job = enqueue_parity(session, ticket_id, calle, idempotency_key, background)
    return JSONResponse(status_code=202, content=job.model_dump(mode="json"))


@router.post(
    "/tickets/{ticket_id}/parity/import",
    response_model=Job,
    dependencies=[Depends(rate_limited)],
)
def import_parity(
    ticket_id: str,
    payload: ParityImportRequest,
    session: Session = Depends(get_session),
    reader: CallePort = Depends(get_live_reader),
    actor: str = Depends(require_operator),
) -> Job:
    """Run parity on two existing CALL-E call records. Never places a call."""
    row = session.get(TicketRow, ticket_id)
    if not row:
        raise HTTPException(404, "ticket not found")
    for party in row.parties:
        if not party.get("consent"):
            raise HTTPException(403, f"consent required for party {party.get('role')}")
    try:
        job = import_parity_from_calls(
            session, ticket_id, payload.call_id_a, payload.call_id_b, reader
        )
    except CalleApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.add(
        ImportAuditRow(
            id=f"aud_{uuid.uuid4().hex[:12]}",
            ticket_id=ticket_id,
            actor=actor,
            call_id_a=payload.call_id_a,
            call_id_b=payload.call_id_b,
            action=(job.result or {}).get("action", {}).get("action", ""),
            job_id=job.id,
        )
    )
    return job


@router.post("/tickets/{ticket_id}/preview", dependencies=[Depends(rate_limited)])
def preview_parity(
    ticket_id: str,
    session: Session = Depends(get_session),
    _actor: str = Depends(require_operator),
) -> dict:
    row = session.get(TicketRow, ticket_id)
    if not row:
        raise HTTPException(404, "ticket not found")
    from app.fixtures.fr1842 import FR1842_A, FR1888_A, FR1900_A

    table = {"FR-1842": FR1842_A, "FR-1900": FR1900_A, "FR-1888": FR1888_A}
    payload = table.get(ticket_id)
    if payload is None:
        raise HTTPException(400, "no preview fixture for ticket")
    view = RunView(
        run_id="preview_a",
        status="preview",
        structured_result=payload["structured_result"],
        transcript=payload["transcript"],
        summary=payload["summary"],
    )
    claims_a = extract_claims(ticket_id, "A", view)
    compiled = compile_refutation(
        {"id": row.id, "entities": row.entities, "parties": row.parties},
        claims_a,
    )
    return {
        "preview": True,
        "plan_b": compiled,
        "claims_a": [c.model_dump(mode="json") for c in claims_a],
        "transcript_pointers": {"a": sha256_text(view.transcript)},
        "spans": {"a": [c.evidence_span for c in claims_a]},
    }


@router.get("/tickets/{ticket_id}/events")
async def ticket_events(ticket_id: str) -> StreamingResponse:
    async def gen():
        last = 0
        idle = 0
        while idle < 80:
            events = snapshot(ticket_id)
            progressed = False
            while last < len(events):
                yield encode(events[last])
                last += 1
                progressed = True
                idle = 0
            if events and events[-1].get("type") in {"job_complete", "job_failed"}:
                break
            if not progressed:
                yield encode({"type": "ping"})
                idle += 1
            await asyncio.sleep(0.2)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/webhooks/calle")
async def calle_webhook(
    request: Request,
    x_calle_signature: str | None = Header(default=None, alias="X-Calle-Signature"),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict:
    from app.config import get_settings
    from app.services.webhook import verify_calle_signature

    body = await request.body()
    settings = get_settings()
    sig = x_calle_signature or x_signature
    if not verify_calle_signature(body, sig, settings.calle_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    import json as _json
    try:
        payload = _json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    return {"accepted": True, "run_id": payload.get("run_id")}
