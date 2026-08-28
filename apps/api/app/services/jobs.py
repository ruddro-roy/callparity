from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_factory
from app.models.orm import JobRow
from app.models.schemas import Job, JobStatus
from app.ports.calle import CallePort
from app.services.events import publish
from app.services.idempotency import derive_idempotency_key
from app.services.parity import run_parity_loop
from app.services.redis_client import acquire_lock

log = structlog.get_logger("jobs")
_in_flight: set[str] = set()

# Written onto rows a dead process left behind; the workbench shows it
# verbatim, so it must tell the operator that a fresh run is safe.
INTERRUPTED_ERROR = (
    "interrupted by a restart before completion; run parity again to start a fresh job"
)

_NON_TERMINAL = (JobStatus.queued.value, JobStatus.running.value)


def reconcile_interrupted_jobs(session: Session) -> list[str]:
    """Converge job rows orphaned by a crash or redeploy into a terminal state.

    Jobs execute as background tasks that live and die with this process, so
    at startup any row still queued or running has no owner. Left alone it
    would replay forever as a spinning job through the idempotency lookup,
    wedging its ticket. Each orphan becomes failed with a clear error, and
    its idempotency key is released by suffixing the job id (unique by
    construction, and the row keeps telling the story of what happened), so
    a deliberate operator retry starts a fresh run under the original key.
    Nothing re-executes automatically: in live mode that would redial humans.
    Terminal rows are untouched, which makes a second boot a no-op.
    """
    orphans = session.query(JobRow).filter(JobRow.status.in_(_NON_TERMINAL)).all()
    for row in orphans:
        row.status = JobStatus.failed.value
        row.error = INTERRUPTED_ERROR
        row.phase = "failed"
        # 90 + "#interrupted:" + 16-char job id stays within String(128).
        row.idempotency_key = f"{row.idempotency_key[:90]}#interrupted:{row.id}"
    session.commit()
    if orphans:
        log.warning("jobs_reconciled", count=len(orphans), job_ids=[row.id for row in orphans])
    return [row.id for row in orphans]


def _to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        ticket_id=row.ticket_id,
        status=JobStatus(row.status),
        idempotency_key=row.idempotency_key,
        result=row.result,
        error=row.error,
        phase=row.phase,
        telemetry=row.telemetry or {},
    )


def enqueue_parity(
    session: Session,
    ticket_id: str,
    calle: CallePort,
    header_key: str | None,
    background: BackgroundTasks,
    claim_set: list[dict] | None = None,
) -> Job:
    derived = derive_idempotency_key(ticket_id, "AB", claim_set)
    key = header_key or derived
    existing = session.query(JobRow).filter(JobRow.idempotency_key == key).one_or_none()
    if existing:
        return _to_job(existing)

    if not acquire_lock(f"idemp:{key}", ttl=30):
        again = session.query(JobRow).filter(JobRow.idempotency_key == key).one_or_none()
        if again:
            return _to_job(again)

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    row = JobRow(
        id=job_id,
        ticket_id=ticket_id,
        status=JobStatus.queued.value,
        idempotency_key=key,
        phase="queued",
        telemetry={"mode": get_settings().calle_mode},
    )
    session.add(row)
    session.flush()
    session.commit()
    publish(ticket_id, {"type": "job_queued", "job_id": job_id, "phase": "queued"})
    background.add_task(_run_job_task, job_id, ticket_id, key)
    return _to_job(row)


async def _run_job_task(job_id: str, ticket_id: str, key: str) -> None:
    if key in _in_flight:
        return
    _in_flight.add(key)
    try:
        await asyncio.to_thread(_execute_job, job_id, ticket_id)
    finally:
        _in_flight.discard(key)


def _execute_job(job_id: str, ticket_id: str) -> None:
    from app.deps import get_calle

    SessionLocal = session_factory()
    session = SessionLocal()
    calle = get_calle()
    try:
        row = session.get(JobRow, job_id)
        if row is None or row.cancelled:
            return
        row.status = JobStatus.running.value
        row.phase = "start"
        session.commit()
        started = time.perf_counter()
        job = run_parity_loop(session, ticket_id, calle, row.idempotency_key, job_id=job_id)
        session.commit()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        row = session.get(JobRow, job_id)
        if row:
            tel = dict(row.telemetry or {})
            tel["latency_ms"] = elapsed_ms
            tel["mode"] = get_settings().calle_mode
            if job.result:
                tel["claims_a"] = len(job.result.get("claims_a") or [])
                tel["claims_b"] = len(job.result.get("claims_b") or [])
                tel["edges"] = len(job.result.get("graph") or [])
            row.telemetry = tel
            row.phase = "merged"
            session.commit()
            publish(ticket_id, {"type": "job_complete", "job_id": job_id, "telemetry": tel})
    except Exception as exc:  # noqa: BLE001
        log.exception("job_failed", job_id=job_id, error=str(exc))
        session.rollback()
        row = session.get(JobRow, job_id)
        if row:
            row.status = JobStatus.failed.value
            row.error = str(exc)
            row.phase = "failed"
            session.commit()
            publish(ticket_id, {"type": "job_failed", "job_id": job_id, "error": str(exc)})
    finally:
        session.close()
