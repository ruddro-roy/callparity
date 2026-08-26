from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_conf import mask_e164
from app.models.orm import ActionCardRow, ClaimRow, EdgeRow, JobRow, TicketRow, TranscriptPointer
from app.models.schemas import ActionCard, Claim, GraphEdge, Job, JobStatus
from app.ports.calle import CallTask, CallePort, RunRef
from app.services.events import publish
from app.services.extractor import extract_claims
from app.services.idempotency import derive_idempotency_key, sha256_text
from app.services.merger import merge_graph
from app.services.planner import compile_refutation
from app.services.redis_client import store_pointer

log = structlog.get_logger("parity")


def _ticket_dict(row: TicketRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "domain": row.domain,
        "fact": row.fact,
        "entities": row.entities,
        "parties": row.parties,
        "sla_usd_per_hour": row.sla_usd_per_hour,
    }


def _persist_claims(session: Session, claims: list[Claim]) -> None:
    for claim in claims:
        session.merge(
            ClaimRow(
                id=claim.id,
                ticket_id=claim.ticket_id,
                source_party=claim.source_party.value,
                predicate=claim.predicate,
                entity_ids=claim.entity_ids,
                slot=claim.slot,
                polarity=claim.polarity.value,
                confidence=claim.confidence,
                evidence_span=claim.evidence_span,
                call_run_id=claim.call_run_id,
            )
        )


def _store_transcript(session: Session, ticket_id: str, body: str) -> str:
    """Store the spoken words behind a sha256 pointer. Empty stores nothing."""
    if not body:
        return ""
    ptr = sha256_text(body)
    store_pointer(ptr, body)
    session.merge(TranscriptPointer(sha256=ptr, ticket_id=ticket_id, body=body))
    return ptr


def _persist_graph(session: Session, ticket_id: str, edges: list[GraphEdge], card: ActionCard) -> None:
    session.query(EdgeRow).filter(EdgeRow.ticket_id == ticket_id).delete()
    for edge in edges:
        session.add(
            EdgeRow(
                id=f"edge_{uuid.uuid4().hex[:10]}",
                ticket_id=ticket_id,
                hypothesis_id=edge.hypothesis_id,
                status=edge.status.value,
                a_span=edge.a_span,
                b_span=edge.b_span,
                action=edge.action.value if edge.action else None,
                predicate=edge.predicate,
            )
        )
    session.add(
        ActionCardRow(
            id=f"act_{uuid.uuid4().hex[:10]}",
            ticket_id=ticket_id,
            action=card.action.value,
            rationale=card.rationale,
        )
    )


def _set_phase(session: Session, job_id: str | None, ticket_id: str, phase: str, extra: dict | None = None) -> None:
    if job_id:
        row = session.get(JobRow, job_id)
        if row:
            if row.cancelled:
                raise InterruptedError("job cancelled")
            row.phase = phase
            row.status = JobStatus.running.value
            session.flush()
    payload = {"type": "phase", "phase": phase, "ticket_id": ticket_id}
    if extra:
        payload.update(extra)
    publish(ticket_id, payload)
    delay = 0.0
    try:
        import os

        delay = max(0.0, float(os.environ.get("PLAYBACK_DELAY_MS", "180")) / 1000.0)
    except ValueError:
        delay = 0.18
    if delay:
        time.sleep(delay)


def run_parity_loop(
    session: Session,
    ticket_id: str,
    calle: CallePort,
    idempotency_key: str | None,
    job_id: str | None = None,
) -> Job:
    ticket = session.get(TicketRow, ticket_id)
    if ticket is None:
        raise KeyError(ticket_id)

    key = idempotency_key or derive_idempotency_key(ticket_id, "AB")
    existing = session.query(JobRow).filter(JobRow.idempotency_key == key).one_or_none()
    if existing and existing.status == JobStatus.completed.value and existing.result:
        return Job(
            id=existing.id,
            ticket_id=existing.ticket_id,
            status=JobStatus.completed,
            idempotency_key=existing.idempotency_key,
            result=existing.result,
            phase=existing.phase or "merged",
            telemetry=existing.telemetry or {},
        )

    if job_id is None:
        job_id = existing.id if existing else f"job_{uuid.uuid4().hex[:12]}"
        if existing is None:
            session.add(
                JobRow(
                    id=job_id,
                    ticket_id=ticket_id,
                    status=JobStatus.running.value,
                    idempotency_key=key,
                    phase="start",
                )
            )
            session.flush()
        else:
            existing.status = JobStatus.running.value

    party_a = next(p for p in ticket.parties if p["role"] == "A")
    party_b = next(p for p in ticket.parties if p["role"] == "B")
    if not party_a.get("consent") or not party_b.get("consent"):
        raise PermissionError("consent required for both parties")

    log.info(
        "parity_start",
        ticket_id=ticket_id,
        job_id=job_id,
        party_a=mask_e164(party_a["phone_e164"]),
        party_b=mask_e164(party_b["phone_e164"]),
    )

    pallet = (ticket.entities or {}).get("pallet_id", "the pallet")
    _set_phase(session, job_id, ticket_id, "a_planning", {"rail": "A"})
    task_a = CallTask(
        ticket_id=ticket_id,
        party_role="A",
        to_phones=[party_a["phone_e164"]],
        goal=f"Confirm location and staging of pallet {pallet}. Ask observable dock facts only.",
        result_schema={"type": "object"},
        consent=True,
    )
    plan_a = calle.plan(task_a)
    _set_phase(session, job_id, ticket_id, "a_talking", {"rail": "A"})
    run_a = calle.run(plan_a)
    view_a = calle.get(RunRef(run_id=run_a.run_id, plan_id=plan_a.plan_id))
    ptr_a = _store_transcript(session, ticket_id, view_a.transcript)

    claims_a = extract_claims(ticket_id, "A", view_a)
    _persist_claims(session, claims_a)
    _set_phase(
        session,
        job_id,
        ticket_id,
        "a_claims",
        {"rail": "A", "claims": [c.model_dump(mode="json") for c in claims_a]},
    )

    compiled = compile_refutation(_ticket_dict(ticket), claims_a)
    _set_phase(session, job_id, ticket_id, "b_planning", {"rail": "B", "plan_b": compiled["goal"]})
    task_b = CallTask(
        ticket_id=ticket_id,
        party_role="B",
        to_phones=compiled["to_phones"],
        goal=compiled["goal"],
        result_schema=compiled["result_schema"],
        consent=True,
    )
    plan_b = calle.plan(task_b)
    _set_phase(session, job_id, ticket_id, "b_talking", {"rail": "B"})
    run_b = calle.run(plan_b)
    view_b = calle.get(RunRef(run_id=run_b.run_id, plan_id=plan_b.plan_id))
    ptr_b = _store_transcript(session, ticket_id, view_b.transcript)

    claims_b = extract_claims(ticket_id, "B", view_b)
    _persist_claims(session, claims_b)
    _set_phase(session, job_id, ticket_id, "b_claims", {"rail": "B", "claims": [c.model_dump(mode="json") for c in claims_b]})

    edges, card = merge_graph(ticket_id, claims_a, claims_b)
    _persist_graph(session, ticket_id, edges, card)

    settings = get_settings()
    result = {
        "graph": [e.model_dump(mode="json") for e in edges],
        "action": card.model_dump(mode="json"),
        "plan_b": {
            k: compiled[k]
            for k in ("goal", "selected_questions", "dropped_questions", "abstain", "untested")
        },
        "transcript_pointers": {"a": ptr_a, "b": ptr_b},
        "spans": {
            "a": [c.evidence_span for c in claims_a],
            "b": [c.evidence_span for c in claims_b],
        },
        "claims_a": [c.model_dump(mode="json") for c in claims_a],
        "claims_b": [c.model_dump(mode="json") for c in claims_b],
        "mode": "fixture" if settings.use_fixtures else "live",
    }
    job_row = session.get(JobRow, job_id)
    job_row.status = JobStatus.completed.value
    job_row.phase = "merged"
    job_row.result = result
    session.flush()
    log.info("parity_complete", ticket_id=ticket_id, job_id=job_id, action=card.action.value)
    return Job(
        id=job_id,
        ticket_id=ticket_id,
        status=JobStatus.completed,
        idempotency_key=key,
        result=result,
        phase="merged",
        telemetry={
            "mode": result["mode"],
            "claims_a": len(claims_a),
            "claims_b": len(claims_b),
            "edges": len(edges),
        },
    )


def latest_card(session: Session, ticket_id: str) -> ActionCard | None:
    row = (
        session.query(ActionCardRow)
        .filter(ActionCardRow.ticket_id == ticket_id)
        .order_by(ActionCardRow.created_at.desc())
        .first()
    )
    if not row:
        return None
    edges = session.query(EdgeRow).filter(EdgeRow.ticket_id == ticket_id).all()
    return ActionCard(
        action=row.action,
        ticket_id=ticket_id,
        rationale=row.rationale,
        created_at=row.created_at,
        edges=[
            GraphEdge(
                hypothesis_id=e.hypothesis_id,
                status=e.status,
                a_span=e.a_span,
                b_span=e.b_span,
                action=e.action,
                predicate=e.predicate,
            )
            for e in edges
        ],
    )
