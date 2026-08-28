"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-28 12:27:09.059250
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "action_cards",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_action_cards_ticket_id", "action_cards", ["ticket_id"], unique=False
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("source_party", sa.String(length=8), nullable=False),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.Column("entity_ids", sa.JSON(), nullable=False),
        sa.Column("slot", sa.JSON(), nullable=False),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
        sa.Column("call_run_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_ticket_id", "claims", ["ticket_id"], unique=False)
    op.create_table(
        "graph_edges",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("a_span", sa.Text(), nullable=False),
        sa.Column("b_span", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_graph_edges_ticket_id", "graph_edges", ["ticket_id"], unique=False
    )
    op.create_table(
        "import_audit",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("call_id_a", sa.String(length=128), nullable=False),
        sa.Column("call_id_b", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_audit_actor", "import_audit", ["actor"], unique=False)
    op.create_index("ix_import_audit_job_id", "import_audit", ["job_id"], unique=False)
    op.create_index(
        "ix_import_audit_ticket_id", "import_audit", ["ticket_id"], unique=False
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=False),
        sa.Column("telemetry", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobs_idempotency_key", "jobs", ["idempotency_key"], unique=True
    )
    op.create_index("ix_jobs_ticket_id", "jobs", ["ticket_id"], unique=False)
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=128), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("parties", sa.JSON(), nullable=False),
        sa.Column("sla_usd_per_hour", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transcript_pointers",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("sha256"),
    )
    op.create_index(
        "ix_transcript_pointers_ticket_id",
        "transcript_pointers",
        ["ticket_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_transcript_pointers_ticket_id", table_name="transcript_pointers")
    op.drop_table("transcript_pointers")
    op.drop_table("tickets")
    op.drop_index("ix_jobs_ticket_id", table_name="jobs")
    op.drop_index("ix_jobs_idempotency_key", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_import_audit_ticket_id", table_name="import_audit")
    op.drop_index("ix_import_audit_job_id", table_name="import_audit")
    op.drop_index("ix_import_audit_actor", table_name="import_audit")
    op.drop_table("import_audit")
    op.drop_index("ix_graph_edges_ticket_id", table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("ix_claims_ticket_id", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_action_cards_ticket_id", table_name="action_cards")
    op.drop_table("action_cards")
