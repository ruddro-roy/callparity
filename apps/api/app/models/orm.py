from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TicketRow(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    domain: Mapped[str] = mapped_column(String(128))
    fact: Mapped[str] = mapped_column(Text)
    entities: Mapped[dict] = mapped_column(JSON)
    parties: Mapped[list] = mapped_column(JSON)
    sla_usd_per_hour: Mapped[float] = mapped_column(Float, default=0)


class ClaimRow(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    source_party: Mapped[str] = mapped_column(String(8))
    predicate: Mapped[str] = mapped_column(String(128))
    entity_ids: Mapped[list] = mapped_column(JSON)
    slot: Mapped[dict] = mapped_column(JSON)
    polarity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    evidence_span: Mapped[str] = mapped_column(Text)
    call_run_id: Mapped[str] = mapped_column(String(64))


class EdgeRow(Base):
    __tablename__ = "graph_edges"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    a_span: Mapped[str] = mapped_column(Text, default="")
    b_span: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicate: Mapped[str] = mapped_column(String(128), default="")


class ActionCardRow(Base):
    __tablename__ = "action_cards"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    phase: Mapped[str] = mapped_column(String(64), default="queued")
    telemetry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranscriptPointer(Base):
    __tablename__ = "transcript_pointers"
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    body: Mapped[str] = mapped_column(Text)


class ImportAuditRow(Base):
    """Who imported which CALL-E call ids, the action emitted, and the job id.

    actor is the operator-token fingerprint, never the raw token. call ids are
    CALL-E identifiers, not phone numbers, so no dialable value is persisted.
    """

    __tablename__ = "import_audit"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    call_id_a: Mapped[str] = mapped_column(String(128))
    call_id_b: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
