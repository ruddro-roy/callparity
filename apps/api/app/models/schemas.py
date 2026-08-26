from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PartyRole(str, Enum):
    A = "A"
    B = "B"


class Polarity(str, Enum):
    asserted = "asserted"
    denied = "denied"
    unknown = "unknown"


class EdgeStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    UNTESTED = "UNTESTED"
    UNREACHABLE = "UNREACHABLE"
    ABSTAIN = "ABSTAIN"


class ActionKind(str, Enum):
    RESTAGE_AND_RECALL = "RESTAGE_AND_RECALL"
    RELEASE_TRUCK = "RELEASE_TRUCK"
    HOLD_FOR_HUMAN = "HOLD_FOR_HUMAN"
    REDIAL_A = "REDIAL_A"
    REDIAL_B = "REDIAL_B"


class Party(BaseModel):
    role: PartyRole
    label: str
    phone_e164: str
    consent: bool = False


class Ticket(BaseModel):
    id: str
    domain: str
    fact: str
    entities: dict[str, Any] = Field(default_factory=dict)
    parties: list[Party]
    sla_usd_per_hour: float = 0


class TicketCreate(Ticket):
    pass


class Claim(BaseModel):
    id: str
    ticket_id: str
    source_party: PartyRole
    predicate: str
    entity_ids: list[str] = Field(default_factory=list)
    slot: dict[str, Any] = Field(default_factory=dict)
    polarity: Polarity = Polarity.asserted
    confidence: float = 0.0
    evidence_span: str = ""
    evidence: dict[str, str] | None = None
    call_run_id: str = ""

    @model_validator(mode="after")
    def _quote_evidence(self) -> "Claim":
        if self.evidence is None and self.evidence_span:
            object.__setattr__(self, "evidence", {"quote": self.evidence_span})
        elif self.evidence and self.evidence.get("quote") and not self.evidence_span:
            object.__setattr__(self, "evidence_span", self.evidence["quote"])
        return self


class RefutationQuestion(BaseModel):
    id: str
    question: str
    covers: list[str] = Field(default_factory=list)
    gain: float = 0.0
    leak: float = 0.0
    net: float = 0.0
    leak_kinds: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    hypothesis_id: str
    status: EdgeStatus
    a_span: str = ""
    b_span: str = ""
    action: ActionKind | None = None
    predicate: str = ""


class ActionCard(BaseModel):
    action: ActionKind
    ticket_id: str
    rationale: str
    edges: list[GraphEdge] = Field(default_factory=list)
    created_at: datetime | None = None


class ParityImportRequest(BaseModel):
    """Two existing CALL-E call ids: A answered as the warehouse, B as the driver."""

    call_id_a: str
    call_id_b: str

    @field_validator("call_id_a", "call_id_b")
    @classmethod
    def _require_call_id(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("call_id must be a non-empty CALL-E call id")
        return value


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Job(BaseModel):
    id: str
    ticket_id: str
    status: JobStatus
    idempotency_key: str
    result: dict[str, Any] | None = None
    error: str | None = None
    phase: str = "queued"
    telemetry: dict[str, Any] = Field(default_factory=dict)


class Healthz(BaseModel):
    status: str
    postgres: str
    redis: str
    calle: str
    mode: str
