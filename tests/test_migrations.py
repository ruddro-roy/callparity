"""The Alembic history must reproduce exactly what create_all builds.

prepare_database() keeps SQLite (tests, local) on create_all while Postgres
migrates through Alembic, so the two paths must produce the same schema or
the offline databases would drift from production. These tests also prove the
startup convergence rules: an empty database migrates to head, a database
created by create_all before migrations existed is stamped and upgraded in
place, and re-running is a no-op.
"""

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory
from app.db import (
    INITIAL_REVISION,
    _alembic_config,
    init_db,
    prepare_database,
    reset_engine,
    run_migrations,
)
from app.models.orm import Base, TicketRow

EXPECTED_TABLES = {
    "tickets",
    "claims",
    "graph_edges",
    "action_cards",
    "jobs",
    "transcript_pointers",
    "import_audit",
}


def schema_snapshot(engine) -> dict:
    """Normalized structural dump: columns, PKs, indexes, unique constraints."""
    inspector = sa.inspect(engine)
    snapshot = {}
    for table in sorted(inspector.get_table_names()):
        if table == "alembic_version":
            continue
        snapshot[table] = {
            "columns": [
                (col["name"], str(col["type"]), col["nullable"])
                for col in inspector.get_columns(table)
            ],
            "primary_key": inspector.get_pk_constraint(table)["constrained_columns"],
            "indexes": sorted(
                (idx["name"], tuple(idx["column_names"]), bool(idx["unique"]))
                for idx in inspector.get_indexes(table)
            ),
            "unique_constraints": sorted(
                (uc["name"], tuple(uc["column_names"]))
                for uc in inspector.get_unique_constraints(table)
            ),
        }
    return snapshot


def upgrade_head(engine) -> None:
    cfg = _alembic_config()
    cfg.attributes["connection"] = engine
    command.upgrade(cfg, "head")


def head_revision() -> str:
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def stamped_revision(engine) -> str | None:
    inspector = sa.inspect(engine)
    if not inspector.has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the app engine at an empty throwaway SQLite file."""
    db = tmp_path / "migrations.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db}")
    reset_engine()
    yield db
    reset_engine()


def test_migration_schema_matches_create_all(tmp_path):
    created = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(created)

    migrated = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}")
    upgrade_head(migrated)

    created_schema = schema_snapshot(created)
    migrated_schema = schema_snapshot(migrated)
    assert set(created_schema) == EXPECTED_TABLES
    assert migrated_schema == created_schema


def test_run_migrations_from_empty_database_reaches_head(fresh_db):
    from app.db import get_engine

    run_migrations()
    engine = get_engine()
    assert EXPECTED_TABLES <= set(sa.inspect(engine).get_table_names())
    assert stamped_revision(engine) == head_revision()

    # A retry after a crash mid-deploy must be a clean no-op.
    run_migrations()
    assert stamped_revision(engine) == head_revision()


def test_run_migrations_stamps_pre_alembic_schema_and_keeps_data(fresh_db):
    from app.db import get_engine, session_factory

    init_db()  # the pre-migrations world: create_all, no alembic_version
    with session_factory()() as session:
        session.add(
            TicketRow(
                id="FR-1842",
                domain="cold_chain_freight",
                fact="parity check",
                entities={},
                parties=[],
                sla_usd_per_hour=0,
            )
        )
        session.commit()

    run_migrations()

    engine = get_engine()
    assert stamped_revision(engine) == head_revision()
    with session_factory()() as session:
        assert session.get(TicketRow, "FR-1842") is not None


def test_initial_revision_constant_matches_history():
    script = ScriptDirectory.from_config(_alembic_config())
    root_revisions = [rev for rev in script.walk_revisions() if rev.down_revision is None]
    assert [rev.revision for rev in root_revisions] == [INITIAL_REVISION]


def test_prepare_database_keeps_sqlite_on_create_all(fresh_db):
    from app.db import get_engine

    prepare_database()
    engine = get_engine()
    assert EXPECTED_TABLES <= set(sa.inspect(engine).get_table_names())
    assert stamped_revision(engine) is None
