from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.orm import JobRow
from app.models.schemas import Job, JobStatus
from app.rate_limit import require_operator_within_rate

router = APIRouter(prefix="/v1")


def _job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        ticket_id=row.ticket_id,
        status=JobStatus(row.status),
        idempotency_key=row.idempotency_key,
        result=row.result,
        error=row.error,
        phase=row.phase or "queued",
        telemetry=row.telemetry or {},
    )


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, session: Session = Depends(get_session)) -> Job:
    row = session.get(JobRow, job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return _job(row)


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(
    job_id: str,
    session: Session = Depends(get_session),
    _actor: str = Depends(require_operator_within_rate),
) -> Job:
    row = session.get(JobRow, job_id)
    if not row:
        raise HTTPException(404, "job not found")
    if row.status != JobStatus.completed.value:
        row.cancelled = True
        row.status = JobStatus.cancelled.value
        row.phase = "cancelled"
    return _job(row)
