from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.db import get_engine, migrate_db, reset_engine
from app.models.orm import Base
from sqlalchemy import Engine, create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = REPO_ROOT / "apps" / "api" / "alembic.ini"


def _schema_signature(engine: Engine) -> dict[str, dict]:
    inspector = inspect(engine)
    return {
        table_name: {
            "columns": [
                (
                    column["name"],
                    column["type"].compile(dialect=engine.dialect),
                    column["nullable"],
                    column["default"],
                    column["primary_key"],
                )
                for column in inspector.get_columns(table_name)
            ],
            "primary_key": tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            ),
            "indexes": sorted(
                (
                    index["name"],
                    tuple(index["column_names"]),
                    index["unique"],
                )
                for index in inspector.get_indexes(table_name)
            ),
            "unique_constraints": sorted(
                (
                    constraint["name"] or "",
                    tuple(constraint["column_names"]),
                )
                for constraint in inspector.get_unique_constraints(table_name)
            ),
            "foreign_keys": sorted(
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            ),
            "check_constraints": sorted(
                (
                    constraint["name"] or "",
                    constraint["sqltext"],
                )
                for constraint in inspector.get_check_constraints(table_name)
            ),
        }
        for table_name in sorted(Base.metadata.tables)
    }


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["configure_logger"] = False
    return config


def _configure_database(monkeypatch, database_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    reset_engine()


def test_initial_migration_matches_create_all_schema(tmp_path):
    metadata_engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'metadata.db'}")
    migrated_engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}")
    Base.metadata.create_all(metadata_engine)

    config = _alembic_config()
    with migrated_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    assert _schema_signature(migrated_engine) == _schema_signature(metadata_engine)

    with migrated_engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        assert compare_metadata(migration_context, Base.metadata) == []
        applied_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert applied_revision == ScriptDirectory.from_config(config).get_current_head()

    metadata_engine.dispose()
    migrated_engine.dispose()


def test_migrate_db_stamps_a_matching_legacy_schema(tmp_path, monkeypatch):
    _configure_database(monkeypatch, tmp_path / "legacy.db")
    try:
        Base.metadata.create_all(get_engine())

        migrate_db()

        with get_engine().connect() as connection:
            applied_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert applied_revision == ScriptDirectory.from_config(
            _alembic_config()
        ).get_current_head()
    finally:
        reset_engine()


def test_migrate_db_rejects_a_partial_legacy_schema(tmp_path, monkeypatch):
    _configure_database(monkeypatch, tmp_path / "partial.db")
    try:
        Base.metadata.tables["tickets"].create(get_engine())

        with pytest.raises(RuntimeError, match="unversioned schema"):
            migrate_db()
    finally:
        reset_engine()
