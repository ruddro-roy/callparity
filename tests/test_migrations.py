import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.migrations import LegacySchemaMismatchError, upgrade_schema
from app.models.orm import Base
from sqlalchemy import create_engine, inspect, text

EXPECTED_TABLES = frozenset(
    {
        "action_cards",
        "claims",
        "graph_edges",
        "import_audit",
        "jobs",
        "tickets",
        "transcript_pointers",
    }
)


def _engine_for(path):
    return create_engine(f"sqlite+pysqlite:///{path}")


def _metadata_changes(engine):
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_server_default": True, "compare_type": True},
        )
        return compare_metadata(context, Base.metadata)


def test_initial_migration_matches_create_all_schema(tmp_path):
    engine = _engine_for(tmp_path / "migrated.db")

    upgrade_schema(engine)

    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}
    assert _metadata_changes(engine) == []
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"

    engine.dispose()


def test_migration_adopts_matching_legacy_schema(tmp_path):
    engine = _engine_for(tmp_path / "legacy.db")
    Base.metadata.create_all(engine)

    upgrade_schema(engine)

    assert _metadata_changes(engine) == []
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"

    engine.dispose()


def test_migration_rejects_drifted_legacy_schema(tmp_path):
    engine = _engine_for(tmp_path / "drifted.db")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE claims"))

    with pytest.raises(LegacySchemaMismatchError):
        upgrade_schema(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()
    engine.dispose()
